"""H67 Stage 1: independent ontology supervision and identity gates.

The only positive labels constructed here come from official RxNorm CPC
same-code terms and WHO ICD-10 titles translated as isolated ontology names.
No Turn2 prediction, H38 row, or H24 weak link is read.  The script stops
before graph training whenever a locked gate fails.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import random
import re
import subprocess
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


SEED = 6701
ICD_FAMILY_RE = re.compile(r"^[A-Z][0-9]{2}")
NUM_RE = re.compile(r"\d+(?:[.,/]\d+)?")
MARKER_RE = re.compile(
    r"\b(?:left|right|bilateral|unspecified|without|without|no|not|negative|absence)\b",
    re.I,
)
VALID_RX_TTY = {"IN", "PIN", "MIN", "SCD", "SBD", "BN", "SY", "PSN"}
VALID_RX_RELA = {
    "has_ingredient",
    "has_active_ingredient",
    "has_precise_ingredient",
    "ingredient_of",
    "precise_ingredient_of",
}


def ensure_import(name: str, package: str | None = None) -> None:
    if importlib.util.find_spec(name) is None:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", package or name])


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text)).replace("_", " ")
    return " ".join(text.casefold().split())


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def chunks(values: list[str], n: int) -> Iterable[list[str]]:
    for i in range(0, len(values), n):
        yield values[i : i + n]


def split_families(keys: Iterable[str]) -> dict[str, str]:
    families = sorted(set(keys))
    rng = random.Random(SEED)
    rng.shuffle(families)
    n = len(families)
    cut1, cut2 = int(n * 0.70), int(n * 0.85)
    return {fam: ("train" if i < cut1 else "dev" if i < cut2 else "test") for i, fam in enumerate(families)}


def parse_rxnorm(root: Path) -> tuple[dict[str, list[str]], dict[str, str], dict[str, str]]:
    conso = root / "RXNCONSO.RRF"
    if not conso.exists():
        found = list(root.rglob("RXNCONSO.RRF"))
        if not found:
            raise FileNotFoundError("RXNCONSO.RRF not found")
        conso = found[0]
    terms: dict[str, list[str]] = defaultdict(list)
    aui_to_cui: dict[str, str] = {}
    tty_by_cui: dict[str, str] = {}
    with conso.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            cols = line.rstrip("\n").split("|")
            if len(cols) < 17 or cols[1] != "ENG" or cols[16] not in {"", "N"}:
                continue
            cui, aui, sab, tty, text = cols[0], cols[7], cols[11], cols[12], cols[14].strip()
            if not cui or not text or tty not in VALID_RX_TTY or sab not in {"RXNORM", "MTHSPL"}:
                continue
            key = norm(text)
            if key and key not in {norm(x) for x in terms[cui]}:
                terms[cui].append(text)
            if aui:
                aui_to_cui[aui] = cui
            tty_by_cui[cui] = tty
    # Official CPC relation rows map AUI-to-AUI; map each product to its
    # active ingredient family without treating parent/child as synonyms.
    family_members: dict[str, set[str]] = defaultdict(set)
    rel = root / "RXNREL.RRF"
    if not rel.exists():
        found = list(root.rglob("RXNREL.RRF"))
        if found:
            rel = found[0]
    if rel.exists():
        with rel.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                cols = line.rstrip("\n").split("|")
                if len(cols) < 11:
                    continue
                rela = cols[7]
                if rela not in VALID_RX_RELA:
                    continue
                src, dst = aui_to_cui.get(cols[1]), aui_to_cui.get(cols[5])
                if src and dst and src != dst:
                    # Direction can be inverse in the RRF; grouping by the
                    # ingredient CUI is stable after adding both directions.
                    family_members[src].add(dst)
                    family_members[dst].add(src)
    aliases: dict[str, list[str]] = {}
    family: dict[str, str] = {}
    for cui, values in terms.items():
        aliases[cui] = sorted(set(values), key=lambda x: (norm(x), x))
        ingredients = sorted(x for x in family_members.get(cui, set()) if x in terms)
        family[cui] = "rx:" + "+".join(ingredients) if ingredients else "rx:" + cui
    return aliases, family, tty_by_cui


def parse_icd(path: Path) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            cols = line.rstrip("\n").split(";")
            if len(cols) < 9 or cols[0] != "4":
                continue
            code, title = cols[6].strip(), cols[8].strip()
            if not code or not title or not ICD_FAMILY_RE.match(code):
                continue
            out[code] = {"code": code, "title": title, "family": code[:3]}
    return out


def load_translator(model_id: str, cache_dir: Path, nllb: bool = False):
    ensure_import("transformers")
    import torch  # type: ignore
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer  # type: ignore

    tok = AutoTokenizer.from_pretrained(model_id, cache_dir=str(cache_dir))
    model = AutoModelForSeq2SeqLM.from_pretrained(
        model_id, cache_dir=str(cache_dir), torch_dtype=torch.float16
    ).to("cuda")
    model.eval()
    if nllb:
        tok.src_lang = "eng_Latn"
    return tok, model


def translate_all(texts: list[str], model_id: str, cache_dir: Path, nllb: bool = False) -> list[str]:
    import torch  # type: ignore

    tok, model = load_translator(model_id, cache_dir, nllb=nllb)
    forced = tok.convert_tokens_to_ids("vie_Latn") if nllb else None
    results: list[str] = []
    for batch in chunks(texts, 32):
        inputs = tok(batch, return_tensors="pt", padding=True, truncation=True, max_length=96).to("cuda")
        kwargs = {"max_new_tokens": 96, "num_beams": 2, "early_stopping": True}
        if forced is not None:
            kwargs["forced_bos_token_id"] = forced
        with torch.no_grad():
            generated = model.generate(**inputs, **kwargs)
        results.extend(tok.batch_decode(generated, skip_special_tokens=True))
    del model, tok
    torch.cuda.empty_cache()
    return results


def preserve_markers(source: str, translated: str) -> bool:
    s, t = norm(source), norm(translated)
    for num in NUM_RE.findall(s):
        if num not in t:
            return False
    markers = set(x.casefold() for x in MARKER_RE.findall(source))
    if "left" in markers and not re.search(r"\b(?:trái|bên trái)\b", t):
        return False
    if "right" in markers and not re.search(r"\b(?:phải|bên phải)\b", t):
        return False
    if "bilateral" in markers and not re.search(r"hai bên|song phương", t):
        return False
    if "unspecified" in markers and not re.search(r"không xác định|không rõ", t):
        return False
    if markers & {"without", "no", "not", "negative", "absence"} and not re.search(
        r"không|không có|âm tính|vắng", t
    ):
        return False
    return bool(t)


def mean_pool(hidden, mask):
    m = mask.unsqueeze(-1).to(hidden.dtype)
    return (hidden * m).sum(1) / m.sum(1).clamp_min(1)


def encode_texts(model, tok, texts: list[str], batch: int = 64) -> Any:
    import torch  # type: ignore

    all_vec = []
    with torch.no_grad():
        for b in chunks(texts, batch):
            inp = tok(b, return_tensors="pt", padding=True, truncation=True, max_length=96).to("cuda")
            out = model(**inp)
            hidden = getattr(out, "last_hidden_state", None)
            if hidden is None:
                raise RuntimeError("embedding model missing last_hidden_state")
            vec = mean_pool(hidden, inp["attention_mask"])
            all_vec.append(torch.nn.functional.normalize(vec.float(), dim=-1).cpu())
    return torch.cat(all_vec, dim=0)


def retrieve_identity(
    aliases: list[dict[str, str]],
    titles: dict[str, str],
    families: dict[str, str],
    cache_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ensure_import("transformers")
    import torch  # type: ignore
    from transformers import AutoModel, AutoTokenizer  # type: ignore

    code_ids = sorted(titles)
    title_texts = [titles[c] for c in code_ids]
    qtok = AutoTokenizer.from_pretrained("Qwen/Qwen3-Embedding-0.6B", cache_dir=str(cache_dir), trust_remote_code=True)
    qmodel = AutoModel.from_pretrained(
        "Qwen/Qwen3-Embedding-0.6B", cache_dir=str(cache_dir), trust_remote_code=True, torch_dtype=torch.float16
    ).to("cuda")
    qmodel.eval()
    b_tok = AutoTokenizer.from_pretrained("BAAI/bge-m3", cache_dir=str(cache_dir))
    b_model = AutoModel.from_pretrained("BAAI/bge-m3", cache_dir=str(cache_dir), torch_dtype=torch.float16).to("cuda")
    b_model.eval()
    q_titles = encode_texts(qmodel, qtok, title_texts)
    b_titles = encode_texts(b_model, b_tok, title_texts)
    by_family: dict[str, list[int]] = defaultdict(list)
    for i, code in enumerate(code_ids):
        by_family[families[code]].append(i)
    q_alias = encode_texts(qmodel, qtok, [a["text"] for a in aliases])
    b_alias = encode_texts(b_model, b_tok, [a["text"] for a in aliases])
    accepted: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    for i, alias in enumerate(aliases):
        inds = by_family.get(families[alias["code"]], [])
        if not inds:
            continue
        def rank(vec, matrix):
            scores = torch.mv(matrix[inds], vec)
            order = torch.argsort(scores, descending=True)
            top = float(scores[order[0]])
            second = float(scores[order[1]]) if len(order) > 1 else top - 1.0
            return code_ids[inds[int(order[0])]], top, top - second
        qtop, qscore, qmargin = rank(q_alias[i], q_titles)
        btop, bscore, bmargin = rank(b_alias[i], b_titles)
        ok = qtop == alias["code"] and btop == alias["code"] and qmargin >= 0.08 and bmargin >= 0.08
        row = {**alias, "qwen_top": qtop, "qwen_margin": qmargin, "bge_top": btop, "bge_margin": bmargin}
        if ok:
            accepted.append(row)
        if len(audit) < 300 and alias.get("view") in {"opus", "nllb"}:
            audit.append({"code": alias["code"], "view": alias["view"], "accepted": ok, "qwen_top": qtop, "bge_top": btop, "qwen_margin": qmargin, "bge_margin": bmargin})
    del qmodel, qtok, b_model, b_tok, q_titles, b_titles, q_alias, b_alias
    torch.cuda.empty_cache()
    audit_acc = sum(int(x["accepted"]) for x in audit) / max(1, len(audit))
    return accepted, {
        "audit_n": len(audit),
        "audit_identity_accuracy": audit_acc,
        "accepted_by_view": Counter(x["view"] for x in accepted),
        "accepted_by_split": Counter(x["split"] for x in accepted),
    }


def iter_public_sentences(root: Path) -> Iterable[tuple[str, str]]:
    """Yield normalized public Vietnamese sentence text with stable IDs."""
    for path in sorted(root.rglob("*.conll")) + sorted(root.rglob("*.txt")):
        if ".git" in path.parts or path.name.lower().startswith("readme"):
            continue
        tokens: list[str] = []
        idx = 0
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for line in lines + [""]:
            if not line.strip():
                if tokens:
                    yield f"{path.name}:{idx}", norm(" ".join(tokens))
                    idx += 1
                    tokens = []
                continue
            cols = line.split()
            if len(cols) >= 2:
                tokens.append(cols[0])


def public_anchors(root: Path, aliases: list[dict[str, Any]]) -> dict[str, Any]:
    unique: dict[str, set[str]] = defaultdict(set)
    for a in aliases:
        unique[norm(a["text"])].add(a["code"])
    # Token-window matching avoids a quadratic substring scan over every
    # public sentence while preserving exact alias boundaries.
    by_first: dict[str, list[tuple[tuple[str, ...], str, str]]] = defaultdict(list)
    lengths: set[int] = set()
    for alias, codes in unique.items():
        if len(codes) != 1 or not alias:
            continue
        toks = tuple(alias.split())
        lengths.add(len(toks))
        by_first[toks[0]].append((toks, next(iter(codes)), alias))
    anchors: set[tuple[str, str, str]] = set()
    for sid, sentence in iter_public_sentences(root):
        toks = sentence.split()
        for i, first in enumerate(toks):
            for pat, code, alias in by_first.get(first, []):
                if tuple(toks[i : i + len(pat)]) == pat:
                    anchors.add((sid, alias, code))
    return {"count": len(anchors), "unique_passages": len({a[0] for a in anchors}), "sample": sorted(anchors)[:20]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ontology-root", type=Path, required=True)
    ap.add_argument("--public-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--alias-out", type=Path, required=True)
    ap.add_argument("--model-cache", type=Path, default=Path("/content/h67_models"))
    args = ap.parse_args()
    started = time.time()
    report: dict[str, Any] = {
        "hypothesis": "H67_ontology_exact_graph_linker",
        "stage": "stage_1_independent_ontology_supervision",
        "protocol": "locked",
        "seed": SEED,
        "errors": [],
        "checks": {},
    }
    try:
        args.model_cache.mkdir(parents=True, exist_ok=True)
        rx_aliases, rx_family, rx_tty = parse_rxnorm(args.ontology_root / "rxnorm")
        rx_rows = [
            {"ontology": "RXNORM", "code": c, "text": text, "family": rx_family[c], "split": ""}
            for c, values in rx_aliases.items()
            for text in values
        ]
        rx_split = split_families(rx_family.values())
        for row in rx_rows:
            row["split"] = rx_split[row["family"]]
        icd_path = args.ontology_root / "who" / "icd102019syst_codes.txt"
        if not icd_path.exists():
            found = list((args.ontology_root / "who").rglob("icd102019syst_codes.txt"))
            if not found:
                raise FileNotFoundError("WHO ICD code table not found")
            icd_path = found[0]
        icd = parse_icd(icd_path)
        icd_split = split_families(x["family"] for x in icd.values())
        for item in icd.values():
            item["split"] = icd_split[item["family"]]
        report["checks"]["family_split"] = {
            "icd": Counter(x["split"] for x in icd.values()),
            "rxnorm": Counter(row["split"] for row in rx_rows),
            "icd_families": len(icd_split),
            "rxnorm_families": len(rx_split),
            "seed": SEED,
        }
        # Translation is restricted to isolated ontology names and performed
        # before the identity filter; target Turn2 text is not read.
        icd_codes = sorted(icd)
        titles = [icd[c]["title"] for c in icd_codes]
        opus = translate_all(titles, "Helsinki-NLP/opus-mt-en-vi", args.model_cache)
        nllb = translate_all(titles, "facebook/nllb-200-distilled-600M", args.model_cache, nllb=True)
        trans_rows: list[dict[str, str]] = []
        for code, src, op, nb in zip(icd_codes, titles, opus, nllb):
            if preserve_markers(src, op):
                trans_rows.append({"ontology": "ICD", "code": code, "text": op.strip(), "view": "opus", "family": icd[code]["family"], "split": icd[code]["split"]})
            if preserve_markers(src, nb):
                trans_rows.append({"ontology": "ICD", "code": code, "text": nb.strip(), "view": "nllb", "family": icd[code]["family"], "split": icd[code]["split"]})
        # Translate-derived normalized collision rate is measured before the
        # dual-retriever promotion filter, and colliding rows are rejected.
        collision_codes: dict[str, set[str]] = defaultdict(set)
        for row in trans_rows:
            collision_codes[norm(row["text"])].add(row["code"])
        collisions = {k for k, v in collision_codes.items() if len(v) > 1}
        trans_rows = [r for r in trans_rows if norm(r["text"]) not in collisions]
        report["checks"]["translation_inventory"] = {
            "icd_codes": len(icd_codes),
            "opus_rows": sum(r["view"] == "opus" for r in trans_rows),
            "nllb_rows": sum(r["view"] == "nllb" for r in trans_rows),
            "cross_code_collision_aliases": len(collisions),
            "collision_rate": len(collisions) / max(1, len(collision_codes)),
        }
        accepted_icd, identity = retrieve_identity(
            trans_rows,
            {c: icd[c]["title"] for c in icd_codes},
            {c: icd[c]["family"] for c in icd_codes},
            args.model_cache,
        )
        for row in accepted_icd:
            row["ontology"] = "ICD"
        accepted = rx_rows + accepted_icd
        anchors = public_anchors(args.public_root, accepted)
        report["checks"]["rxnorm_alias_quality"] = {
            "active_codes": len(rx_aliases),
            "accepted_same_code_alias_pairs": len(rx_rows),
            "ingredient_families": len(rx_split),
            "tty_counts": Counter(rx_tty.values()),
        }
        report["checks"]["icd_alias_quality"] = {
            "accepted_multilingual_aliases": len(accepted_icd),
            "accepted_by_view": dict(identity["accepted_by_view"]),
            "accepted_by_split": dict(identity["accepted_by_split"]),
            "identity_audit_n": identity["audit_n"],
            "identity_accuracy": identity["audit_identity_accuracy"],
            "collision_rate": report["checks"]["translation_inventory"]["collision_rate"],
        }
        report["checks"]["public_context_anchor"] = anchors
        gates = {
            "rxnorm_alias_pairs_ge_20000": len(rx_rows) >= 20000,
            "icd_aliases_ge_3000": len(accepted_icd) >= 3000,
            "identity_audit_n_ge_300": identity["audit_n"] >= 300,
            "identity_accuracy_ge_0.95": identity["audit_identity_accuracy"] >= 0.95,
            "collision_rate_le_0.005": report["checks"]["translation_inventory"]["collision_rate"] <= 0.005,
            "public_anchors_ge_500": anchors["count"] >= 500,
        }
        report["gates"] = gates
        if not all(gates.values()):
            raise RuntimeError("Stage 1 independent ontology gate failed")
        args.alias_out.parent.mkdir(parents=True, exist_ok=True)
        with args.alias_out.open("w", encoding="utf-8") as f:
            for row in accepted:
                f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        report["status"] = "PASS_STAGE_1"
    except Exception as exc:
        report["status"] = "FAIL_STAGE_1"
        report["errors"].append(f"{type(exc).__name__}: {exc}")
    finally:
        report["elapsed_seconds"] = round(time.time() - started, 3)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps({"status": report.get("status"), "elapsed_seconds": report["elapsed_seconds"], "errors": report["errors"], "gates": report.get("gates")}, ensure_ascii=False))
    return 0 if report.get("status") == "PASS_STAGE_1" else 2


if __name__ == "__main__":
    raise SystemExit(main())
