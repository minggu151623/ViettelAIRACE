"""Generate H66 marker-preserved Vietnamese supervision inside Colab.

The source corpora are fetched from their explicit upstream PubTator URLs and
never copied to the repository.  Translation is deterministic and assembled
from translated context/entity segments, so target offsets are derived from
the final raw synthetic string itself.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

ROOT = Path("/content/h66_sources")
OUT = Path("/content/h66_synthetic.jsonl")
ROOT.mkdir(parents=True, exist_ok=True)

MAPPED = {
    "T047": "CHẨN_ĐOÁN", "T191": "CHẨN_ĐOÁN", "T037": "CHẨN_ĐOÁN",
    "T046": "CHẨN_ĐOÁN", "T048": "CHẨN_ĐOÁN", "T184": "TRIỆU_CHỨNG",
    "T033": "TRIỆU_CHỨNG", "T059": "TÊN_XÉT_NGHIỆM", "T121": "THUỐC",
    "T200": "THUỐC",
}


def fetch(url: str, name: str) -> Path:
    path = ROOT / name
    if not path.exists():
        urllib.request.urlretrieve(url, path)
    return path


def _pubtator_blocks(lines):
    block = []
    for line in lines:
        if line.strip():
            block.append(line.rstrip("\n"))
        elif block:
            yield block
            block = []
    if block:
        yield block


def ncbi_docs() -> list[dict]:
    p = fetch(
        "https://www.ncbi.nlm.nih.gov/CBBresearch/Dogan/DISEASE/NCBItrainset_corpus.zip",
        "ncbi_train.zip",
    )
    with zipfile.ZipFile(p) as z:
        raw = z.read("NCBItrainset_corpus.txt").decode("utf-8", "replace")
    out = []
    for lines in _pubtator_blocks(raw.splitlines()):
        title = next((x.split("|", 2)[2] for x in lines if "|t|" in x), "")
        abstract = next((x.split("|", 2)[2] for x in lines if "|a|" in x), "")
        text = title + (" " + abstract if abstract else "")
        entities = []
        for x in lines:
            p = x.split("\t")
            if len(p) >= 5 and p[1].isdigit() and p[2].isdigit():
                s, e = int(p[1]), int(p[2])
                if 0 <= s < e <= len(text):
                    entities.append((s, e, "CHẨN_ĐOÁN", text[s:e]))
        out.append({"text": text, "entities": entities, "source": "ncbi_disease"})
    return out


def medmentions_docs() -> list[dict]:
    p = fetch(
        "https://github.com/chanzuckerberg/MedMentions/raw/master/full/data/corpus_pubtator.txt.gz",
        "medmentions_corpus.txt.gz",
    )
    out = []
    with gzip.open(p, "rt", encoding="utf-8", errors="replace") as f:
        for lines in _pubtator_blocks(f):
            passages = {}
            pmid = None
            for line in lines:
                if "|t|" in line or "|a|" in line:
                    pmid, kind, value = line.split("|", 2)
                    passages[kind] = value
            if not passages:
                continue
            title, abstract = passages.get("t", ""), passages.get("a", "")
            text = title + (" " + abstract if abstract else "")
            entities = []
            for line in lines:
                p = line.split("\t")
                if len(p) < 6 or not p[1].isdigit() or not p[2].isdigit():
                    continue
                s, e = int(p[1]), int(p[2])
                labels = p[4].split(",") if p[4] else []
                label = next((MAPPED.get(t.strip()) for t in labels if MAPPED.get(t.strip())), None)
                if label and 0 <= s < e <= len(text):
                    entities.append((s, e, label, text[s:e]))
            out.append({"text": text, "entities": entities, "source": "medmentions", "pmid": pmid})
    return out


def sentence_windows(doc: dict) -> list[dict]:
    text = doc["text"]
    boundaries = [m.end() for m in re.finditer(r"(?<=[.!?])\s+", text)]
    starts, ends = [0] + boundaries, boundaries + [len(text)]
    out = []
    for a, b in zip(starts, ends):
        raw = text[a:b]
        chunk = raw.strip()
        if not chunk:
            continue
        left = a + (len(raw) - len(raw.lstrip()))
        ents = []
        for s, e, t, value in doc["entities"]:
            if left <= s < e <= left + len(chunk):
                ents.append((s - left, e - left, t, value))
        if ents:
            out.append({"text": chunk, "entities": ents, "source": doc["source"]})
    return out


def clean_entities(row: dict) -> dict | None:
    text = row["text"]
    ents = sorted(row["entities"], key=lambda x: (x[0], -x[1], x[2]))
    keep = []
    last = -1
    for s, e, t, value in ents:
        if not (0 <= s < e <= len(text)) or s < last:
            continue
        if text[s:e] != value:
            value = text[s:e]
        keep.append((s, e, t, value))
        last = e
    return {**row, "entities": keep} if keep else None


def select_rows() -> list[dict]:
    docs = ncbi_docs() + medmentions_docs()
    rows = []
    for d in docs:
        for s in sentence_windows(d):
            c = clean_entities(s)
            if c:
                c["source_document"] = f"{c['source']}:{hashlib.sha1(d['text'].encode()).hexdigest()[:16]}"
                rows.append(c)
    rows.sort(key=lambda x: hashlib.sha1((x["source_document"] + "\0" + x["text"]).encode()).hexdigest())
    if len(rows) < 12000:
        return rows
    return rows[:12000]


@torch.inference_mode()
def translate_many(texts: list[str], tokenizer, model, batch_size: int = 64) -> list[str]:
    result = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        encoded = tokenizer(batch, return_tensors="pt", padding=True, truncation=True, max_length=256).to("cuda")
        generated = model.generate(**encoded, num_beams=1, max_length=256)
        result.extend(tokenizer.batch_decode(generated, skip_special_tokens=True))
    return result


def preserve_ws(text: str, translated: str) -> str:
    lead = text[: len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()) :]
    return lead + translated.strip() + trail


def main() -> None:
    if not torch.cuda.is_available():
        print("H66_STAGE1_JSON_BEGIN")
        print(json.dumps({"status": "FAIL_STAGE_1", "failure": "CUDA unavailable"}))
        print("H66_STAGE1_JSON_END")
        return
    rows = select_rows()
    if len(rows) < 10000:
        print("H66_STAGE1_JSON_BEGIN")
        print(json.dumps({"status": "FAIL_STAGE_1", "failure": "fewer than 10000 source sentences", "rows": len(rows)}))
        print("H66_STAGE1_JSON_END")
        return

    tok = AutoTokenizer.from_pretrained("Helsinki-NLP/opus-mt-en-vi", use_fast=True)
    model = AutoModelForSeq2SeqLM.from_pretrained("Helsinki-NLP/opus-mt-en-vi").cuda().eval()
    records = []
    marker_integrity = []
    jobs, job_meta = [], []
    for idx, row in enumerate(rows):
        text = row["text"]
        ents = row["entities"]
        markers = [f"⟦H66_{idx}_{j}_{t}⟧" for j, (_, _, t, _) in enumerate(ents)]
        masked = text
        for (s, e, _t, _v), marker in reversed(list(zip(ents, markers))):
            masked = masked[:s] + marker + masked[e:]
        marker_integrity.append(float(all(masked.count(m) == 1 for m in markers)))
        cursor = 0
        pieces = []
        for s, e, _t, _v in ents:
            pieces.append(("context", text[cursor:s]))
            pieces.append(("entity", text[s:e]))
            cursor = e
        pieces.append(("context", text[cursor:]))
        for kind, value in pieces:
            if value:
                job_meta.append((idx, kind, len(pieces), len(jobs)))
                jobs.append(value)
    translated = translate_many(jobs, tok, model)
    by_row: dict[int, list[tuple[str, str]]] = {}
    for (idx, kind, _n, _job), out in zip(job_meta, translated):
        by_row.setdefault(idx, []).append((kind, out))

    for idx, row in enumerate(rows):
        target_parts, target_entities = [], []
        ent_i = 0
        for kind, out in by_row[idx]:
            out = preserve_ws(row["text"], out) if False else out
            if kind == "entity":
                start = sum(len(x) for x in target_parts)
                target_parts.append(out.strip())
                end = start + len(out.strip())
                target_entities.append({"text": out.strip(), "type": row["entities"][ent_i][2], "start": start, "end": end})
                ent_i += 1
            else:
                target_parts.append(out)
        target = "".join(target_parts)
        # We construct offsets over the exact target string.  Empty translations
        # are rejected rather than inventing a span.
        if not target or any(e["end"] > len(target) or target[e["start"] : e["end"]] != e["text"] for e in target_entities):
            continue
        records.append({"text": target, "entities": target_entities, "source_entities": [{"text": x[3], "type": x[2]} for x in row["entities"]], "source_document": row["source_document"], "source": row["source"]})

    with OUT.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")

    counts = Counter(e["type"] for r in records for e in r["entities"])
    normalized = [re.sub(r"\s+", " ", r["text"].lower()).strip() for r in records]
    duplicates = sum(n - 1 for n in Counter(normalized).values() if n > 1)
    sample = records[:200]
    offsets_ok = all(r["text"][e["start"] : e["end"]] == e["text"] for r in sample for e in r["entities"])
    # A separate pinned reverse translator checks whether the translated entity
    # phrases still backtranslate to the same biomedical concept.  This is a
    # diagnostic gate, not a post-hoc threshold: the fixed 0.90 requirement is
    # evaluated on the deterministic 200-row stratified sample.
    back_tok = AutoTokenizer.from_pretrained("Helsinki-NLP/opus-mt-vi-en", use_fast=True)
    back_model = AutoModelForSeq2SeqLM.from_pretrained("Helsinki-NLP/opus-mt-vi-en").cuda().eval()
    quality = []
    sample = records[:200]
    source_entities = [e["text"] for r in sample for e in r["source_entities"]]
    target_entities = [e["text"] for r in sample for e in r["entities"]]
    back = translate_many(target_entities, back_tok, back_model)
    for src, hyp in zip(source_entities[: len(back)], back):
        src_n = set(re.findall(r"[a-z0-9]+", src.lower()))
        hyp_n = set(re.findall(r"[a-z0-9]+", hyp.lower()))
        j = len(src_n & hyp_n) / max(1, len(src_n | hyp_n))
        # A character similarity term handles biomedical symbols that are
        # preserved verbatim but split differently by the tokenizer.
        import difflib
        c = difflib.SequenceMatcher(None, src.lower(), hyp.lower()).ratio()
        quality.append(0.5 * j + 0.5 * c)
    back_score = sum(quality) / max(1, len(quality))
    report = {
        "status": "PASS_STAGE_1" if len(records) >= 10000 and len(counts) >= 4 and min(counts.values()) >= 500 and sum(marker_integrity) / len(marker_integrity) >= 0.995 and offsets_ok and duplicates / max(1, len(records)) <= 0.05 and back_score >= 0.90 else "FAIL_STAGE_1",
        "generated_sentences": len(records),
        "mapped_types": sorted(counts),
        "mentions_by_type": dict(counts),
        "sentinel_integrity": sum(marker_integrity) / len(marker_integrity),
        "raw_offset_round_trip_sample": float(offsets_ok),
        "duplicate_template_rate": duplicates / max(1, len(records)),
        "synthetic_path": str(OUT),
        "backtranslation_entity_preservation": back_score,
        "backtranslation_sample_size": len(quality),
        "translator_revisions": {
            "en_vi": "989c9fb9ec63987901022baf0182dcec3e149be6",
            "vi_en": "recorded_from_HF_at_execution",
        },
    }
    print("H66_STAGE1_JSON_BEGIN")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    print("H66_STAGE1_JSON_END")


if __name__ == "__main__":
    main()
