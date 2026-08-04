"""H66 Stage 1 source inventory/parser probe; executed remotely before translation."""
from __future__ import annotations

import gzip
import io
import json
import re
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path("/content/h66_sources")
ROOT.mkdir(parents=True, exist_ok=True)


def fetch(url: str, name: str) -> Path:
    path = ROOT / name
    if not path.exists():
        urllib.request.urlretrieve(url, path)
    return path


def ncbi_docs() -> list[dict]:
    p = fetch(
        "https://www.ncbi.nlm.nih.gov/CBBresearch/Dogan/DISEASE/NCBItrainset_corpus.zip",
        "ncbi_train.zip",
    )
    with zipfile.ZipFile(p) as z:
        raw = z.read("NCBItrainset_corpus.txt").decode("utf-8", "replace")
    docs = []
    block = []
    for line in raw.splitlines():
        if line.strip():
            block.append(line)
        elif block:
            docs.append(block)
            block = []
    if block:
        docs.append(block)
    out = []
    for lines in docs:
        title = next((x.split("|", 2)[2] for x in lines if "|t|" in x), "")
        abstract = next((x.split("|", 2)[2] for x in lines if "|a|" in x), "")
        text = title + (" " + abstract if abstract else "")
        ents = []
        for x in lines:
            parts = x.split("\t")
            if len(parts) >= 5 and parts[1].isdigit() and parts[2].isdigit():
                start, end = int(parts[1]), int(parts[2])
                if 0 <= start < end <= len(text):
                    ents.append((start, end, "CHẨN_ĐOÁN", text[start:end]))
        out.append({"text": text, "entities": ents, "source": "ncbi_disease"})
    return out


def medmentions_docs() -> list[dict]:
    corpus = fetch(
        "https://github.com/chanzuckerberg/MedMentions/raw/master/full/data/corpus_pubtator.txt.gz",
        "medmentions_corpus.txt.gz",
    )
    mapped = {
        "T047": "CHẨN_ĐOÁN", "T191": "CHẨN_ĐOÁN", "T037": "CHẨN_ĐOÁN",
        "T046": "CHẨN_ĐOÁN", "T048": "CHẨN_ĐOÁN", "T184": "TRIỆU_CHỨNG",
        "T033": "TRIỆU_CHỨNG", "T059": "TÊN_XÉT_NGHIỆM", "T121": "THUỐC",
        "T200": "THUỐC",
    }
    out = []
    with gzip.open(corpus, "rt", encoding="utf-8", errors="replace") as f:
        block = []
        for line in f:
            if line.strip():
                block.append(line.rstrip("\n"))
            elif block:
                parsed = _parse_mm(block, mapped)
                if parsed:
                    out.append(parsed)
                block = []
        if block:
            parsed = _parse_mm(block, mapped)
            if parsed:
                out.append(parsed)
    return out


def _parse_mm(lines: list[str], mapped: dict[str, str]) -> dict | None:
    passages = {}
    pmid = None
    for line in lines:
        if "|t|" in line or "|a|" in line:
            pmid, kind, value = line.split("|", 2)
            passages[kind] = value
    if not passages:
        return None
    title = passages.get("t", "")
    abstract = passages.get("a", "")
    text = title + (" " + abstract if abstract else "")
    entities = []
    offset_shift = len(title) + 1
    for line in lines:
        p = line.split("\t")
        if len(p) < 6 or not p[1].isdigit() or not p[2].isdigit():
            continue
        start, end = int(p[1]), int(p[2])
        # PubTator offsets refer to title+space+abstract in MedMentions.
        sem_types = p[5].split(";") if p[5] else []
        label = next((mapped.get(t.strip()) for t in sem_types if mapped.get(t.strip())), None)
        if label and 0 <= start < end <= len(text):
            entities.append((start, end, label, text[start:end]))
    return {"text": text, "entities": entities, "source": "medmentions", "pmid": pmid}


def sentence_windows(doc: dict) -> list[dict]:
    text = doc["text"]
    boundaries = [m.end() for m in re.finditer(r"(?<=[.!?])\s+", text)]
    starts = [0] + boundaries
    ends = boundaries + [len(text)]
    out = []
    for a, b in zip(starts, ends):
        chunk = text[a:b].strip()
        if not chunk:
            continue
        left = a + (len(text[a:b]) - len(text[a:b].lstrip()))
        ents = [(s - left, e - left, t, chunk[s-left:e-left]) for s, e, t, _ in doc["entities"] if left <= s < e <= left + len(chunk)]
        ents = [x for x in ents if 0 <= x[0] < x[1] <= len(chunk)]
        if ents:
            out.append({"text": chunk, "entities": ents, "source": doc["source"]})
    return out


def main() -> None:
    ncbi = ncbi_docs()
    mm = medmentions_docs()
    sentences = [s for d in ncbi + mm for s in sentence_windows(d)]
    counts = Counter(t for s in sentences for _, _, t, _ in s["entities"])
    print("H66_STAGE1_INVENTORY_JSON_BEGIN")
    print(json.dumps({
        "status": "PASS_SOURCE_INVENTORY" if len(sentences) >= 10000 and len(counts) >= 4 else "FAIL_STAGE_1_SOURCE_INVENTORY",
        "documents": {"ncbi_disease": len(ncbi), "medmentions": len(mm)},
        "sentences_with_entities": len(sentences),
        "mapped_mentions": dict(counts),
        "mapped_types": sorted(counts),
        "source_root": str(ROOT),
    }, ensure_ascii=False, sort_keys=True))
    print("H66_STAGE1_INVENTORY_JSON_END")


if __name__ == "__main__":
    main()
