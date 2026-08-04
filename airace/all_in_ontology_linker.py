from __future__ import annotations

import hashlib
import json
import time
import unicodedata
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from .ontology_graph import build_project_graph
from .ontology_qwen import cached_ollama_embeddings, format_query
from .package_output import package_output
from .schema import entities_from_json
from .serialization import dumps_btc
from .validator import validate_entities, validate_output_dir


EXPECTED_H69_SHA256 = "12090622102ab333f3f697161953f1fdd1a799488ea0656a9fc0582c16462369"
EXPECTED_H74_SHA256 = "6dbd1cce2351a57be944cd0cab5963a40c884a49af169433c415695812d847e4"
LINK_TYPES = {"CHẨN_ĐOÁN", "THUỐC"}


def normalize_mention(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _batch_rank(
    query_embeddings: np.ndarray,
    query_types: list[str],
    concept_embeddings: np.ndarray,
    concept_ids: list[str],
    *,
    top_k: int = 10,
) -> list[list[str]]:
    result: list[list[str] | None] = [None] * len(query_types)
    for kind, prefix in (("CHẨN_ĐOÁN", "ICD:"), ("THUỐC", "RX:")):
        query_indices = [index for index, value in enumerate(query_types) if value == kind]
        pool = np.asarray(
            [index for index, identifier in enumerate(concept_ids) if identifier.startswith(prefix)],
            dtype=np.int64,
        )
        concepts = concept_embeddings[pool]
        for offset in range(0, len(query_indices), 32):
            indices = query_indices[offset : offset + 32]
            scores = query_embeddings[indices] @ concepts.T
            count = min(top_k, scores.shape[1])
            selected = np.argpartition(scores, -count, axis=1)[:, -count:]
            for batch_row, (row_index, local) in enumerate(zip(indices, selected)):
                ordered = sorted(
                    local,
                    key=lambda index: (-float(scores[batch_row, index]), concept_ids[pool[index]]),
                )
                result[row_index] = [concept_ids[pool[index]] for index in ordered]
    if any(value is None for value in result):
        raise AssertionError("missing type-restricted ranking")
    return [value for value in result if value is not None]


def _chat_json(
    prompt: str,
    schema: dict[str, Any],
    *,
    seed: int,
    model: str = "qwen3:8b",
    endpoint: str = "http://127.0.0.1:11434/api/chat",
) -> dict[str, Any]:
    payload = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,
            "format": schema,
            "options": {"temperature": 0.0, "seed": seed, "num_ctx": 32768},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint, data=payload, headers={"Content-Type": "application/json"}
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=900) as response:
                body = json.load(response)
            return json.loads(body["message"]["content"])
        except Exception as error:  # noqa: BLE001 - retry local inference transport/JSON
            last_error = error
            time.sleep(2**attempt)
    raise RuntimeError("Qwen reranker failed after three attempts") from last_error


def _review_schema(count: int) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "reviews": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "selected": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    "required": ["id", "selected", "confidence"],
                },
            }
        },
        "required": ["reviews"],
    }


def _prompt(batch: list[dict[str, Any]], *, skeptical: bool) -> str:
    stance = (
        "Bạn là kiểm toán viên ontology hoài nghi. Chỉ đổi mã khi concept thay thế rõ ràng chính xác hơn mã hiện tại."
        if skeptical
        else "Bạn là chuyên gia coding ICD-10 và RxNorm, chọn concept đúng nhất theo mention và ngữ cảnh."
    )
    return (
        stance
        + "\nMỗi item có danh sách options đóng. selected PHẢI là đúng một code trong options hoặc ABSTAIN. "
        "Không sinh code mới. Ưu tiên mã cụ thể khi text cung cấp subtype; dùng mã unspecified khi text không đủ chi tiết. "
        "Với thuốc có brand, giữ brand identity; với ingredient rõ ràng, dùng ingredient. "
        "Đánh giá ĐỦ mọi item và trả đúng JSON schema cực ngắn; không viết giải thích.\n\n"
        + json.dumps(batch, ensure_ascii=False)
    )


def build_all_in_ontology_linker_submission(
    input_dir: str | Path,
    h69_dir: str | Path,
    h74_dir: str | Path,
    output_dir: str | Path,
    zip_path: str | Path,
    report_path: str | Path,
    cache_dir: str | Path,
    h74_report_path: str | Path,
    resource_dir: str | Path,
) -> dict[str, Any]:
    inputs, h69, h74 = Path(input_dir), Path(h69_dir), Path(h74_dir)
    output, target_zip = Path(output_dir), Path(zip_path)
    report_target, cache = Path(report_path), Path(cache_dir)
    if sha256(h69.with_suffix(".zip")) != EXPECTED_H69_SHA256:
        raise ValueError("H69 SHA-256 mismatch")
    if sha256(h74.with_suffix(".zip")) != EXPECTED_H74_SHA256:
        raise ValueError("H74 SHA-256 mismatch")
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError(f"output directory must be empty: {output}")
    cache.mkdir(parents=True, exist_ok=True)

    frozen_mentions = {
        (row["text"], row.get("rule", "H74"))
        for row in json.loads(Path(h74_report_path).read_text(encoding="utf-8"))["all_changes"]
    }
    frozen_texts = {normalize_mention(text) for text, _ in frozen_mentions}

    groups: dict[tuple[str, str], dict[str, Any]] = {}
    records = sorted(inputs.glob("*.txt"), key=lambda path: int(path.stem))
    for text_path in records:
        record = int(text_path.stem)
        raw = text_path.read_text(encoding="utf-8")
        values = json.loads((h74 / f"{record}.json").read_text(encoding="utf-8"))
        for index, entity in enumerate(entities_from_json(values)):
            if entity.type not in LINK_TYPES or normalize_mention(entity.text) in frozen_texts:
                continue
            if len(entity.candidates or []) > 1:
                continue
            key = (entity.type, normalize_mention(entity.text))
            group = groups.setdefault(
                key,
                {
                    "type": entity.type,
                    "mention": entity.text,
                    "normalized": key[1],
                    "current_votes": defaultdict(int),
                    "contexts": [],
                    "occurrences": [],
                },
            )
            current = tuple(entity.candidates or [])
            group["current_votes"][current] += 1
            if len(group["contexts"]) < 2:
                start, end = entity.position
                left, right = max(0, start - 100), min(len(raw), end + 100)
                group["contexts"].append(raw[left:start] + "⟦" + raw[start:end] + "⟧" + raw[end:right])
            group["occurrences"].append((record, index))

    jobs = []
    for job_id, ((kind, normalized), group) in enumerate(sorted(groups.items())):
        current = max(group["current_votes"], key=lambda value: (group["current_votes"][value], value))
        group["id"] = job_id
        group["current"] = list(current)
        group["current_votes"] = {"|".join(key): value for key, value in group["current_votes"].items()}
        jobs.append(group)

    graph = build_project_graph(resource_dir)
    concept_ids = sorted(graph.nodes)
    concept_embeddings = np.load(
        Path(resource_dir).parents[1]
        / "experiments/H24_ontology_graph_classifier/cache/qwen3_concepts.npy",
        mmap_mode="r",
    ).astype(np.float32)
    concept_embeddings /= np.maximum(np.linalg.norm(concept_embeddings, axis=1, keepdims=True), 1e-12)
    query_embeddings, query_meta = cached_ollama_embeddings(
        [format_query(job["mention"]) for job in jobs],
        cache / "turn2_queries.npy",
        batch_size=128,
    )
    rankings = _batch_rank(
        query_embeddings, [job["type"] for job in jobs], concept_embeddings, concept_ids
    )

    # The final-day all-in pass concentrates the expensive two-pass LLM audit on
    # mentions that can materially move the record-level score.  The retriever
    # still evaluates the complete mention inventory; only the closed-set LLM
    # reranker is budgeted.  IDs remain stable so every cached decision is
    # auditable against the full inventory.
    for job, ranked in zip(jobs, rankings):
        top_code = ranked[0].split(":", 1)[1]
        records_touched = len({record for record, _ in job["occurrences"]})
        job["impact_priority"] = (
            len(job["occurrences"]) * 4
            + records_touched * 3
            + (5 if not job["current"] else 0)
            + (3 if job["current"] != [top_code] else 0)
        )
    audited_ids = {
        job["id"]
        for job in sorted(
            jobs,
            key=lambda value: (
                -value["impact_priority"],
                -len({record for record, _ in value["occurrences"]}),
                -len(value["occurrences"]),
                value["id"],
            ),
        )[:260]
    }

    for job, ranked in zip(jobs, rankings):
        option_ids: list[str] = []
        for code in job["current"]:
            identifier = ("ICD:" if job["type"] == "CHẨN_ĐOÁN" else "RX:") + code
            if identifier in graph.nodes and identifier not in option_ids:
                option_ids.append(identifier)
        for identifier in ranked:
            if identifier not in option_ids:
                option_ids.append(identifier)
        option_ids = option_ids[:12]
        job["options"] = [
            {
                "code": identifier.split(":", 1)[1],
                "title": graph.nodes[identifier].canonical,
                "semantic_type": graph.nodes[identifier].semantic_type,
            }
            for identifier in option_ids
        ]

    pass_results: list[dict[int, dict[str, Any]]] = []
    for pass_index, (seed, skeptical) in enumerate(((7501, False), (7502, True)), start=1):
        pass_path = cache / f"pass_fast_{pass_index}.json"
        if pass_path.exists():
            stored = json.loads(pass_path.read_text(encoding="utf-8"))
            completed = {int(key): value for key, value in stored.items()}
        else:
            completed = {}
        audited_jobs = [job for job in jobs if job["id"] in audited_ids]
        if pass_index == 2:
            first_pass = pass_results[0]
            audited_jobs = [
                job
                for job in audited_jobs
                if str(first_pass[job["id"]]["selected"]) != "ABSTAIN"
                and str(first_pass[job["id"]]["selected"]) not in job["current"]
                and float(first_pass[job["id"]]["confidence"]) >= 0.85
            ]
        for offset in range(0, len(audited_jobs), 20):
            subset = [
                job for job in audited_jobs[offset : offset + 20] if job["id"] not in completed
            ]
            if not subset:
                continue
            payload = [
                {
                    "id": job["id"],
                    "type": job["type"],
                    "mention": job["mention"],
                    "contexts": job["contexts"],
                    "current": job["current"],
                    "options": job["options"],
                }
                for job in subset
            ]
            response = _chat_json(_prompt(payload, skeptical=skeptical), _review_schema(len(payload)), seed=seed)
            reviews = response.get("reviews", [])
            by_id = {int(review["id"]): review for review in reviews}
            expected = {job["id"] for job in subset}
            if set(by_id) != expected:
                raise RuntimeError(f"pass {pass_index} incomplete batch at {offset}")
            completed.update(by_id)
            pass_path.write_text(json.dumps(completed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(
                f"H75 pass={pass_index} completed={len(completed)}/{len(audited_jobs)}",
                flush=True,
            )
        pass_results.append(completed)

    selections: dict[tuple[str, str], str] = {}
    decisions: list[dict[str, Any]] = []
    for job in jobs:
        if job["id"] not in audited_ids:
            continue
        first = pass_results[0][job["id"]]
        second = pass_results[1].get(
            job["id"],
            {"selected": "ABSTAIN", "confidence": 0.0, "reason": "not promoted by pass 1"},
        )
        allowed = {option["code"] for option in job["options"]}
        selected = str(first["selected"])
        agreed = selected == str(second["selected"])
        confidence = min(float(first["confidence"]), float(second["confidence"]))
        current = job["current"]
        promote = (
            agreed
            and selected != "ABSTAIN"
            and selected in allowed
            and confidence >= 0.85
            and current != [selected]
        )
        if promote:
            selections[(job["type"], job["normalized"])] = selected
        decisions.append(
            {
                "id": job["id"],
                "type": job["type"],
                "mention": job["mention"],
                "current": current,
                "selected": selected,
                "agreed": agreed,
                "confidence": confidence,
                "promoted": promote,
                "occurrences": len(job["occurrences"]),
                "first_reason": first.get("reason", ""),
                "second_reason": second.get("reason", ""),
                "options": job["options"],
            }
        )

    changes: list[dict[str, Any]] = []
    for text_path in records:
        record = int(text_path.stem)
        raw = text_path.read_text(encoding="utf-8")
        base_values = json.loads((h69 / f"{record}.json").read_text(encoding="utf-8"))
        source = json.loads((h74 / f"{record}.json").read_text(encoding="utf-8"))
        entities = entities_from_json(source)
        for index, entity in enumerate(entities):
            key = (entity.type, normalize_mention(entity.text))
            selected = selections.get(key)
            if selected is not None and entity.candidates != [selected]:
                old = list(entity.candidates or [])
                entity.candidates = [selected]
                changes.append(
                    {
                        "record": record,
                        "entity_index": index,
                        "text": entity.text,
                        "type": entity.type,
                        "position": list(entity.position),
                        "old_candidates": old,
                        "new_candidates": [selected],
                    }
                )
        transformed = [entity.to_dict() for entity in entities]
        for base, after in zip(base_values, transformed):
            for field in set(base) | set(after):
                if field != "candidates" and base.get(field) != after.get(field):
                    raise AssertionError(f"frozen field changed: {field}")
        validate_entities(entities, raw)
        (output / f"{record}.json").write_text(dumps_btc(transformed), encoding="utf-8")

    changed_records = len({row["record"] for row in changes})
    selected_codes = {row["new_candidates"][0] for row in changes}
    graph_codes = {identifier.split(":", 1)[1] for identifier in graph.nodes}
    validation = validate_output_dir(inputs, output, position_mode="raw")
    gates = {
        "changed_rows_ge_80": len(changes) >= 80,
        "changed_records_ge_40": changed_records >= 40,
        "all_selected_codes_in_graph": selected_codes <= graph_codes,
        "all_100_records_validate": validation["ok"] and validation["records"] == 100,
    }
    if not all(gates.values()):
        raise RuntimeError(f"H75 promotion gates failed: {gates}")

    package_output(output, target_zip, inputs, position_mode="raw")
    repeat_zip = report_target.parent / "repeat.zip"
    package_output(output, repeat_zip, inputs, position_mode="raw")
    deterministic = target_zip.read_bytes() == repeat_zip.read_bytes()
    repeat_zip.unlink()
    if not deterministic:
        raise RuntimeError("ZIP packaging is not deterministic")
    report = {
        "hypothesis": "H75_all_in_ontology_llm_linker",
        "status": "PASS_HIGH_RISK_AWAITING_SUBMISSION_APPROVAL",
        "zip": str(target_zip),
        "zip_sha256": sha256(target_zip),
        "zip_bytes": target_zip.stat().st_size,
        "jobs": len(jobs),
        "promoted_unique_mentions": len(selections),
        "changed_rows": len(changes),
        "changed_records": changed_records,
        "changes_by_type": dict(sorted(_count(row["type"] for row in changes).items())),
        "query_embedding_metadata": query_meta,
        "gates": {**gates, "deterministic_zip_bytes": deterministic},
        "validation": validation,
        "changes": changes,
        "decisions": decisions,
    }
    report_target.parent.mkdir(parents=True, exist_ok=True)
    report_target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def _count(values: Any) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for value in values:
        counts[value] += 1
    return dict(counts)
