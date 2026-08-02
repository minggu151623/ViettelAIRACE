from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from .candidate_set_utility import jaccard, paired_bootstrap
from .ontology_graph import build_project_graph


KS = tuple(range(1, 11))
ALPHAS = (0.1, 1.0, 10.0, 100.0)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def score_features(scores: np.ndarray, identifiers: list[str]) -> np.ndarray:
    values = np.asarray(scores, dtype=np.float64)
    if values.shape != (10,) or len(identifiers) != 10:
        raise ValueError("score-shape features require exactly ten ranked candidates")
    margins = values[:-1] - values[1:]
    shifted = values - values.max()
    probabilities = np.exp(shifted) / np.exp(shifted).sum()
    entropy = -float(np.sum(probabilities * np.log(np.maximum(probabilities, 1e-15))))
    top_code = identifiers[0].removeprefix("ICD:")
    top_family = top_code[:3]
    family = [float(value.removeprefix("ICD:")[:3] == top_family) for value in identifiers]
    specificity = float(len("".join(character for character in top_code if character.isalnum())) > 3)
    return np.asarray(
        [*values, *margins, float(values.mean()), float(values.std()), entropy, specificity, *family],
        dtype=np.float64,
    )


def _diagnosis_scores(
    rows: list[dict[str, Any]],
    concept_ids: list[str],
    concept_embeddings: np.ndarray,
    query_embeddings: np.ndarray,
    reported: dict[int, list[str]],
) -> tuple[dict[int, np.ndarray], int]:
    pool = np.asarray([i for i, value in enumerate(concept_ids) if value.startswith("ICD:")])
    pool_ids = [concept_ids[i] for i in pool]
    score_map: dict[int, np.ndarray] = {}
    reproduced = 0
    diagnosis = [row for row in rows if row["type"] == "CHẨN_ĐOÁN"]
    for offset in range(0, len(diagnosis), 64):
        batch = diagnosis[offset:offset + 64]
        indices = [row["id"] for row in batch]
        matrix = query_embeddings[indices] @ concept_embeddings[pool].T
        for local, row in enumerate(batch):
            scores = matrix[local]
            selected = np.argpartition(scores, -10)[-10:]
            selected = sorted(selected, key=lambda i: (-float(scores[i]), pool_ids[i]))
            ranking = [pool_ids[i] for i in selected]
            reproduced += int(ranking == reported[row["id"]])
            score_map[row["id"]] = np.asarray([scores[i] for i in selected], dtype=np.float64)
    return score_map, reproduced


def _utilities(row: dict[str, Any], ranking: list[str]) -> np.ndarray:
    return np.asarray([jaccard(ranking[:k], row["gold_concepts"]) for k in KS])


def _fit_predict(
    train_x: np.ndarray,
    train_y: np.ndarray,
    target_x: np.ndarray,
    alpha: float,
) -> np.ndarray:
    scaler = StandardScaler().fit(train_x)
    transformed_train = scaler.transform(train_x)
    transformed_target = scaler.transform(target_x)
    predictions = []
    for action in range(len(KS)):
        model = Ridge(alpha=alpha).fit(transformed_train, train_y[:, action])
        predictions.append(model.predict(transformed_target))
    return np.column_stack(predictions)


def _select_actions(predicted_utility: np.ndarray) -> np.ndarray:
    # np.argmax implements the preregistered smaller-k tie break.
    return np.argmax(predicted_utility, axis=1) + 1


def _realized(utilities: np.ndarray, actions: np.ndarray) -> list[float]:
    return [float(utilities[i, action - 1]) for i, action in enumerate(actions)]


def build_report(
    dataset_path: str | Path,
    ranking_path: str | Path,
    concept_path: str | Path,
    query_path: str | Path,
    *,
    expected_hashes: dict[str, str],
    expected_node_sha256: str,
) -> dict[str, Any]:
    paths = {
        "dataset": Path(dataset_path),
        "ranking": Path(ranking_path),
        "concepts": Path(concept_path),
        "queries": Path(query_path),
    }
    actual_hashes = {name: sha256_file(path) for name, path in paths.items()}
    if actual_hashes != expected_hashes:
        raise ValueError(f"input hash mismatch: {actual_hashes}")

    dataset = json.loads(paths["dataset"].read_text(encoding="utf-8"))
    ranking_report = json.loads(paths["ranking"].read_text(encoding="utf-8"))
    reported = {row["id"]: row["top10"] for row in ranking_report["predictions"]}
    graph = build_project_graph()
    manifest = graph.manifest()
    if manifest["node_sha256"] != expected_node_sha256:
        raise ValueError("ontology node SHA-256 mismatch")
    concept_ids = sorted(graph.nodes)
    concepts = np.load(paths["concepts"]).astype(np.float32)
    queries = np.load(paths["queries"]).astype(np.float32)
    concepts /= np.maximum(np.linalg.norm(concepts, axis=1, keepdims=True), 1e-12)
    queries /= np.maximum(np.linalg.norm(queries, axis=1, keepdims=True), 1e-12)
    score_map, reproduced = _diagnosis_scores(
        dataset["rows"], concept_ids, concepts, queries, reported
    )
    if reproduced != 420:
        raise ValueError(f"only {reproduced}/420 diagnosis rankings reproduced")

    fold_rows = {
        fold: [row for row in dataset["rows"] if row["type"] == "CHẨN_ĐOÁN" and row["fold"] == fold]
        for fold in ("train", "dev", "test")
    }
    if {key: len(value) for key, value in fold_rows.items()} != {"train": 345, "dev": 28, "test": 47}:
        raise ValueError("diagnosis split census mismatch")

    def matrices(rows: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
        features, utilities = [], []
        for row in rows:
            ranking = reported[row["id"]]
            features.append(score_features(score_map[row["id"]], ranking))
            utilities.append(_utilities(row, ranking))
        return np.vstack(features), np.vstack(utilities)

    train_x, train_y = matrices(fold_rows["train"])
    dev_x, dev_y = matrices(fold_rows["dev"])
    alpha_results = []
    for alpha in ALPHAS:
        predictions = _fit_predict(train_x, train_y, dev_x, alpha)
        actions = _select_actions(predictions)
        realized = _realized(dev_y, actions)
        alpha_results.append(
            {
                "alpha": alpha,
                "dev_jaccard": float(np.mean(realized)),
                "mean_k": float(np.mean(actions)),
                "action_counts": {str(k): int(np.sum(actions == k)) for k in KS},
            }
        )
    selected = min(alpha_results, key=lambda row: (-row["dev_jaccard"], row["alpha"]))
    selected_alpha = float(selected["alpha"])
    dev_predictions = _fit_predict(train_x, train_y, dev_x, selected_alpha)
    dev_actions = _select_actions(dev_predictions)
    dev_challenger = _realized(dev_y, dev_actions)
    dev_baseline = [float(value) for value in dev_y[:, 0]]
    bootstrap = paired_bootstrap(dev_baseline, dev_challenger, seed=4601, resamples=10_000)
    gates = {
        "macro_jaccard_delta_at_least_0_02": bootstrap["point_delta"] >= 0.02,
        "paired_bootstrap_95_percent_lower_bound_above_0": bootstrap["ci95_low"] > 0,
        "mean_predicted_k_at_most_3": float(np.mean(dev_actions)) <= 3.0,
    }
    dev_pass = all(gates.values())

    report: dict[str, Any] = {
        "hypothesis": "H46_score_shape_cardinality",
        "label_warning": "weak_pseudo_labels_not_organizer_ground_truth",
        "input_hashes": actual_hashes,
        "ontology_node_sha256": manifest["node_sha256"],
        "ranking_reproduction": f"{reproduced}/420",
        "feature_dimension": int(train_x.shape[1]),
        "alpha_results": alpha_results,
        "selected_alpha": selected_alpha,
        "dev": {
            "rows": len(dev_y),
            "baseline_top1_jaccard": float(np.mean(dev_baseline)),
            "adaptive_jaccard": float(np.mean(dev_challenger)),
            "delta": float(np.mean(dev_challenger) - np.mean(dev_baseline)),
            "mean_k": float(np.mean(dev_actions)),
            "action_counts": {str(k): int(np.sum(dev_actions == k)) for k in KS},
            "paired_bootstrap": bootstrap,
            "gates": gates,
        },
        "test": {"status": "opened" if dev_pass else "canceled_by_preregistered_dev_gate"},
        "decision": "DEV_PASS" if dev_pass else "REJECT_BEFORE_TEST",
        "artifact_policy": "NO_SUBMISSION_ZIP",
    }
    if dev_pass:
        test_x, test_y = matrices(fold_rows["test"])
        test_predictions = _fit_predict(train_x, train_y, test_x, selected_alpha)
        test_actions = _select_actions(test_predictions)
        test_challenger = _realized(test_y, test_actions)
        test_baseline = [float(value) for value in test_y[:, 0]]
        test_bootstrap = paired_bootstrap(
            test_baseline, test_challenger, seed=4601, resamples=10_000
        )
        report["test"].update(
            {
                "rows": len(test_y),
                "baseline_top1_jaccard": float(np.mean(test_baseline)),
                "adaptive_jaccard": float(np.mean(test_challenger)),
                "delta": float(np.mean(test_challenger) - np.mean(test_baseline)),
                "mean_k": float(np.mean(test_actions)),
                "paired_bootstrap": test_bootstrap,
            }
        )
        report["decision"] = (
            "PASS"
            if test_bootstrap["point_delta"] >= 0.02 and test_bootstrap["ci95_low"] > 0
            else "REJECT_ON_TEST"
        )
    return report


def write_report(report: dict[str, Any], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--ranking", required=True)
    parser.add_argument("--concepts", required=True)
    parser.add_argument("--queries", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = build_report(
        args.dataset,
        args.ranking,
        args.concepts,
        args.queries,
        expected_hashes={
            "dataset": "c4237bb90e2e46563f4887907271a512b21b5c2b81cc182865215068d76ed7b6",
            "ranking": "87dbc1391dd1ab58693efec6933b34c73f53ca6f6f9d13730925125b9cf2e41b",
            "concepts": "4b08669bbdfaca23ab987aa29c924bd7ce1e66b92f1303d5a91e35bb6c6f22d7",
            "queries": "29d8cc6a36ca1f0fe4e097153c1eb9e517c35887b637bfeab69e52867aa4bba5",
        },
        expected_node_sha256="40c3dd800ee9897f8a41b13f1e277d89bf310471f7279004fd8f8b3a74ee5e08",
    )
    write_report(report, args.output)


if __name__ == "__main__":
    main()
