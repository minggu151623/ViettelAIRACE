from __future__ import annotations

import hashlib
import json
import re
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
RESOURCE_DIR = ROOT / "resources"
LEXICON_PATH = RESOURCE_DIR / "default_lexicon.json"
MANIFEST_PATH = RESOURCE_DIR / "manifest.json"


def load_lexicon() -> dict[str, Any]:
    return json.loads(LEXICON_PATH.read_text(encoding="utf-8"))


def prepare_resources(download_rxnorm: bool = False, resource_dir: Path | None = None) -> dict[str, Any]:
    directory = resource_dir or RESOURCE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "icd": {
            "name": "WHO ICD-10 2019",
            "version": "2019",
            "status": "alias fallback bundled; download separately before production",
            "url": "https://icdcdn.who.int/icd10/index.html"
        },
        "rxnorm": {
            "name": "RxNorm Current Prescribable Content",
            "release": "2026-07-06",
            "filename": "RxNorm_full_prescribe_07062026.zip",
            "url": "https://download.nlm.nih.gov/rxnorm/RxNorm_full_prescribe_07062026.zip",
            "status": "bundled seed mappings"
        }
    }
    if download_rxnorm:
        target = directory / "RxNorm_full_prescribe_07062026.zip"
        download_target = target.with_suffix(".download")
        urllib.request.urlretrieve(manifest["rxnorm"]["url"], download_target)
        if not zipfile.is_zipfile(download_target):
            preview = download_target.read_text(encoding="utf-8", errors="ignore")[:160].replace("\n", " ")
            download_target.unlink(missing_ok=True)
            raise RuntimeError(
                "RxNorm download did not return a ZIP archive; "
                f"server response starts with: {preview!r}"
            )
        download_target.replace(target)
        manifest["rxnorm"]["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
        manifest["rxnorm"]["status"] = "downloaded"
        extracted = directory / "rxnorm_20260706"
        with zipfile.ZipFile(target) as archive:
            archive.extractall(extracted)
        index = build_rxnorm_index(extracted)
        (directory / "rxnorm_index.json").write_text(
            json.dumps(index, ensure_ascii=False), encoding="utf-8"
        )
        catalog = build_rxnorm_catalog(extracted)
        (directory / "rxnorm_catalog.json").write_text(
            json.dumps(catalog, ensure_ascii=False), encoding="utf-8"
        )
        manifest["rxnorm"]["index_entries"] = len(index)
        manifest["rxnorm"]["alias_entries"] = len(catalog["aliases"])
        manifest["rxnorm"]["product_entries"] = len(catalog["products"])
        manifest["rxnorm"]["brand_to_generic_entries"] = len(catalog["brand_to_generic"])
        manifest["rxnorm"]["catalog_sha256"] = hashlib.sha256(
            (directory / "rxnorm_catalog.json").read_bytes()
        ).hexdigest()
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def build_rxnorm_index(extracted_dir: Path) -> dict[str, list[str]]:
    """Build a compact ingredient/strength index from RXNCONSO.RRF.

    The Current Prescribable Content release is RRF with pipe-delimited rows.
    We intentionally retain only RXCUI values relevant to terms in the bundled
    drug lexicon, keeping inference fast and the artifact small.
    """
    lex = load_lexicon()
    ingredients = {str(k).split("|", 1)[0].casefold() for k in lex.get("drug_codes", {})}
    index: dict[str, set[str]] = {}
    files = list(extracted_dir.rglob("RXNCONSO.RRF"))
    for path in files:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                cols = line.rstrip("\n").split("|")
                if len(cols) < 15 or cols[1] != "ENG":
                    continue
                rxcui, term = cols[0], cols[14].casefold()
                matched = [ing for ing in ingredients if ing in term]
                if not matched:
                    continue
                strength_tokens = set(re.findall(r"\d+(?:\.\d+)?\s*(?:mg|g|mcg|ml)", term))
                for ingredient in matched:
                    if strength_tokens:
                        for strength in strength_tokens:
                            key = f"{ingredient}|{strength}"
                            index.setdefault(key, set()).add(rxcui)
                    else:
                        index.setdefault(f"{ingredient}|", set()).add(rxcui)
    return {key: sorted(values) for key, values in index.items()}


def build_rxnorm_catalog(extracted_dir: Path) -> dict[str, Any]:
    """Create a compact public-domain RxNorm search catalog."""
    alias_ttys = {"IN", "PIN", "MIN", "BN"}
    product_ttys = {"SCD", "SBD", "SCDF", "SBDF", "SCDG", "SBDG", "GPCK", "BPCK"}
    aliases: dict[str, dict[str, str]] = {}
    products: dict[tuple[str, str], dict[str, str]] = {}
    preferred_alias_by_rxcui: dict[str, tuple[int, str]] = {}
    files = list(extracted_dir.rglob("RXNCONSO.RRF"))
    for path in files:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                cols = line.rstrip("\n").split("|")
                if len(cols) < 15 or cols[1] != "ENG" or cols[11] != "RXNORM":
                    continue
                rxcui, tty, term = cols[0], cols[12], cols[14]
                norm = re.sub(r"\s+", " ", term.casefold()).strip()
                if tty in alias_ttys:
                    current = aliases.get(norm)
                    priority = {"IN": 0, "PIN": 1, "MIN": 2, "BN": 3}
                    if current is None or priority[tty] < priority[current["tty"]]:
                        aliases[norm] = {"rxcui": rxcui, "tty": tty, "term": term}
                    current_term = preferred_alias_by_rxcui.get(rxcui)
                    if current_term is None or priority[tty] < current_term[0]:
                        preferred_alias_by_rxcui[rxcui] = (priority[tty], norm)
                elif tty in product_ttys:
                    products[(rxcui, tty)] = {
                        "rxcui": rxcui, "tty": tty, "term": term, "norm": norm
                    }
    # A brand alias (BN) often has no injectable product bearing the brand
    # string, while its generic ingredient does.  Retain only the direct
    # RxNorm brand-to-generic relation; no clinical inference is made here.
    brand_to_generic_ids: dict[str, str] = {}
    for path in extracted_dir.rglob("RXNREL.RRF"):
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                cols = line.rstrip("\n").split("|")
                if len(cols) < 11 or cols[10] != "RXNORM":
                    continue
                first, second, relation = cols[0], cols[4], cols[7]
                if relation == "tradename_of":
                    brand_to_generic_ids[second] = first
                elif relation == "has_tradename":
                    brand_to_generic_ids[first] = second
    brand_to_generic = {
        brand: preferred_alias_by_rxcui[generic][1]
        for brand, generic in brand_to_generic_ids.items()
        if generic in preferred_alias_by_rxcui
    }
    return {
        "aliases": aliases,
        "products": list(products.values()),
        "brand_to_generic": brand_to_generic,
    }
