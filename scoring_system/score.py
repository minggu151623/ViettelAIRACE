from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ASSERTION_TYPES = {"CHẨN_ĐOÁN", "THUỐC", "TRIỆU_CHỨNG"}
CANDIDATE_TYPES = {"CHẨN_ĐOÁN", "THUỐC"}
NUMBERED_JSON = re.compile(r"^(\d+)\.json$")


class ScoreError(ValueError):
    """Raised for an invalid or incomplete scoring input."""


@dataclass(frozen=True)
class Entity:
    text: str
    type: str
    position: tuple[int, int]
    assertions: frozenset[str]
    candidates: frozenset[str]


@dataclass(frozen=True)
class Pair:
    truth: Entity | None
    prediction: Entity | None


def parse_entity(raw: Any, source: str, index: int) -> Entity:
    if not isinstance(raw, dict):
        raise ScoreError(f"{source}: entity {index} must be an object")
    missing = [key for key in ("text", "type", "position") if key not in raw]
    if missing:
        raise ScoreError(f"{source}: entity {index} misses {', '.join(missing)}")
    position = raw["position"]
    if (
        not isinstance(position, list)
        or len(position) != 2
        or any(not isinstance(value, int) or isinstance(value, bool) for value in position)
        or position[0] < 0
        or position[1] <= position[0]
    ):
        raise ScoreError(
            f"{source}: entity {index} position must be [start, end] with 0 <= start < end"
        )
    if not isinstance(raw["text"], str) or not isinstance(raw["type"], str):
        raise ScoreError(f"{source}: entity {index} text and type must be strings")

    def string_set(field: str) -> frozenset[str]:
        value = raw.get(field, [])
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ScoreError(f"{source}: entity {index} {field} must be a list of strings")
        return frozenset(value)

    return Entity(
        text=raw["text"],
        type=raw["type"],
        position=(position[0], position[1]),
        assertions=string_set("assertions"),
        candidates=string_set("candidates"),
    )


def parse_document(raw: Any, source: str) -> list[Entity]:
    if not isinstance(raw, list):
        raise ScoreError(f"{source}: top-level JSON value must be a list")
    return [parse_entity(entity, source, index) for index, entity in enumerate(raw)]


def read_directory(path: Path) -> dict[str, list[Entity]]:
    documents: dict[str, list[Entity]] = {}
    for file_path in sorted(path.glob("*.json")):
        match = NUMBERED_JSON.fullmatch(file_path.name)
        if not match:
            continue
        sample_id = match.group(1)
        try:
            raw = json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ScoreError(f"cannot read {file_path}: {exc}") from exc
        documents[sample_id] = parse_document(raw, str(file_path))
    return documents


def read_zip(path: Path) -> dict[str, list[Entity]]:
    documents: dict[str, list[Entity]] = {}
    try:
        with zipfile.ZipFile(path) as archive:
            for member in archive.namelist():
                filename = Path(member).name
                match = NUMBERED_JSON.fullmatch(filename)
                if not match:
                    continue
                sample_id = match.group(1)
                if sample_id in documents:
                    raise ScoreError(f"{path}: duplicate sample {filename}")
                raw = json.loads(archive.read(member).decode("utf-8"))
                documents[sample_id] = parse_document(raw, f"{path}!{member}")
    except (OSError, zipfile.BadZipFile, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScoreError(f"cannot read {path}: {exc}") from exc
    return documents


def read_documents(path: Path) -> dict[str, list[Entity]]:
    if path.is_dir():
        documents = read_directory(path)
    elif path.is_file() and path.suffix.lower() == ".zip":
        documents = read_zip(path)
    else:
        raise ScoreError(f"input must be a directory or .zip file: {path}")
    if not documents:
        raise ScoreError(f"no numbered JSON samples found in {path}")
    return documents


def resolve_input_path(path: Path, *, prediction: bool = False) -> Path:
    """Resolve paths from both the project root and the scoring_system directory."""
    if path.exists():
        return path
    if prediction and path.suffix.lower() == ".zip":
        sibling_archive = path.parent.parent / path.name
        if sibling_archive.is_file():
            return sibling_archive
    local_path = Path(__file__).resolve().parent / path
    if local_path.exists():
        return local_path
    return path


def word_errors(reference: str, hypothesis: str) -> tuple[int, int]:
    """Return Levenshtein word errors and reference word count."""
    reference_words = reference.split()
    hypothesis_words = hypothesis.split()
    previous = list(range(len(hypothesis_words) + 1))
    for row, reference_word in enumerate(reference_words, 1):
        current = [row]
        for column, hypothesis_word in enumerate(hypothesis_words, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (reference_word != hypothesis_word),
                )
            )
        previous = current
    return previous[-1], len(reference_words)


def text_similarity(reference: str, hypothesis: str) -> float:
    errors, word_count = word_errors(reference, hypothesis)
    if word_count == 0:
        return 1.0 if not hypothesis.split() else 0.0
    return 1.0 - errors / word_count


def span_overlap(left: Entity, right: Entity) -> int:
    return max(0, min(left.position[1], right.position[1]) - max(left.position[0], right.position[0]))


def align_entities(truth: list[Entity], prediction: list[Entity]) -> list[Pair]:
    """Greedily select the best non-conflicting same-type overlapping pairs."""
    edges: list[tuple[tuple[float, float, int], int, int]] = []
    for truth_index, truth_entity in enumerate(truth):
        for prediction_index, prediction_entity in enumerate(prediction):
            if truth_entity.type != prediction_entity.type:
                continue
            overlap = span_overlap(truth_entity, prediction_entity)
            if overlap == 0:
                continue
            overlap_ratio = overlap / max(
                truth_entity.position[1] - truth_entity.position[0],
                prediction_entity.position[1] - prediction_entity.position[0],
            )
            exact_span = float(truth_entity.position == prediction_entity.position)
            edges.append(
                ((exact_span, overlap_ratio, overlap), truth_index, prediction_index)
            )

    matched_truth: set[int] = set()
    matched_prediction: set[int] = set()
    pairs: list[Pair] = []
    for _, truth_index, prediction_index in sorted(edges, reverse=True):
        if truth_index in matched_truth or prediction_index in matched_prediction:
            continue
        matched_truth.add(truth_index)
        matched_prediction.add(prediction_index)
        pairs.append(Pair(truth[truth_index], prediction[prediction_index]))

    pairs.extend(Pair(entity, None) for i, entity in enumerate(truth) if i not in matched_truth)
    pairs.extend(
        Pair(None, entity) for i, entity in enumerate(prediction) if i not in matched_prediction
    )
    return pairs


def jaccard(truth: Iterable[str], prediction: Iterable[str]) -> float:
    truth_set, prediction_set = set(truth), set(prediction)
    if not truth_set:
        return 1.0 if not prediction_set else 0.0
    return len(truth_set & prediction_set) / len(truth_set | prediction_set)


def mean(values: list[float], empty: float = 1.0) -> float:
    return sum(values) / len(values) if values else empty


def score_sample(truth: list[Entity], prediction: list[Entity]) -> dict[str, float | int]:
    pairs = align_entities(truth, prediction)
    text_values: list[float] = []
    assertion_values: list[float] = []
    candidate_weighted_sum = 0.0
    candidate_weight = 0

    for pair in pairs:
        matched = pair.truth is not None and pair.prediction is not None
        text_values.append(
            text_similarity(pair.truth.text, pair.prediction.text) if matched else 0.0
        )

        entity_type = pair.truth.type if pair.truth is not None else pair.prediction.type
        if entity_type in ASSERTION_TYPES:
            assertion_values.append(
                jaccard(pair.truth.assertions, pair.prediction.assertions) if matched else 0.0
            )
        if entity_type in CANDIDATE_TYPES:
            weight = len(pair.truth.candidates) + 1 if pair.truth is not None else 1
            candidate_weight += weight
            if matched:
                candidate_weighted_sum += weight * jaccard(
                    pair.truth.candidates, pair.prediction.candidates
                )

    return {
        "text_score": mean(text_values),
        "assertions_score": mean(assertion_values),
        "candidate_weighted_sum": candidate_weighted_sum,
        "candidate_weight": candidate_weight,
        "ground_truth_entities": len(truth),
        "prediction_entities": len(prediction),
        "scored_entities": len(pairs),
    }


def score_corpus(
    ground_truth: dict[str, list[Entity]], predictions: dict[str, list[Entity]]
) -> dict[str, Any]:
    truth_ids, prediction_ids = set(ground_truth), set(predictions)
    if truth_ids != prediction_ids:
        missing = sorted(truth_ids - prediction_ids, key=int)
        extra = sorted(prediction_ids - truth_ids, key=int)
        details = []
        if missing:
            details.append(f"missing predictions: {', '.join(missing)}")
        if extra:
            details.append(f"unknown predictions: {', '.join(extra)}")
        raise ScoreError("sample sets differ; " + "; ".join(details))

    sample_scores = {
        sample_id: score_sample(ground_truth[sample_id], predictions[sample_id])
        for sample_id in sorted(truth_ids, key=int)
    }
    text_score = mean([float(item["text_score"]) for item in sample_scores.values()])
    assertions_score = mean(
        [float(item["assertions_score"]) for item in sample_scores.values()]
    )
    candidate_numerator = sum(
        float(item["candidate_weighted_sum"]) for item in sample_scores.values()
    )
    candidate_denominator = sum(
        int(item["candidate_weight"]) for item in sample_scores.values()
    )
    candidates_score = (
        candidate_numerator / candidate_denominator if candidate_denominator else 1.0
    )
    wer = 1.0 - text_score
    final_score = 0.3 * (1.0 - wer) + 0.3 * assertions_score + 0.4 * candidates_score

    return {
        "final_score": final_score,
        "WER": wer,
        "J_assertion": assertions_score,
        "J_candidates": candidates_score,
        "text_score": text_score,
        "assertions_score": assertions_score,
        "candidates_score": candidates_score,
        "weights": {"text": 0.3, "assertions": 0.3, "candidates": 0.4},
        "sample_count": len(sample_scores),
        "candidate_weight_total": candidate_denominator,
        "per_sample": {
            sample_id: {
                key: value
                for key, value in item.items()
                if key not in {"candidate_weighted_sum"}
            }
            for sample_id, item in sample_scores.items()
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "prediction_input",
        nargs="?",
        type=Path,
        help="prediction directory or ZIP (positional shorthand for --predictions)",
    )
    parser.add_argument(
        "--predictions",
        dest="predictions_option",
        type=Path,
        help="prediction directory or ZIP",
    )
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=Path("scoring_system/ground_truth_predict"),
        help="ground-truth directory or ZIP",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("output/score.json"), help="result JSON path"
    )
    return parser


def primary_metrics(result: dict[str, Any]) -> dict[str, float]:
    """Return the four public metrics as percentages in the 0-100 range."""
    return {
        key: float(result[key]) * 100.0
        for key in ("final_score", "WER", "J_assertion", "J_candidates")
    }


def main() -> int:
    args = build_parser().parse_args()
    if args.prediction_input is not None and args.predictions_option is not None:
        print("error: use either a positional prediction ZIP/directory or --predictions, not both", file=sys.stderr)
        return 2
    predictions_path = args.prediction_input or args.predictions_option or Path("input/output.zip")
    try:
        result = score_corpus(
            read_documents(resolve_input_path(args.ground_truth)),
            read_documents(resolve_input_path(predictions_path, prediction=True)),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        metrics = primary_metrics(result)
        args.output.write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except ScoreError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"Saved result to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
