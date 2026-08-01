from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .normalize import normalize_key
from .resources import load_lexicon
from .schema import Entity


@dataclass
class CandidateResult:
    ids: list[str]
    score: float
    reason: str


class CandidateResolver:
    def __init__(
        self,
        lexicon: dict | None = None,
        resource_dir: Path | None = None,
        use_catalog: bool = True,
        strict_strength: bool = False,
    ) -> None:
        self.lexicon = lexicon or load_lexicon()
        self.use_catalog = use_catalog
        self.strict_strength = strict_strength
        self.drug_codes = {
            normalize_key(k.split("|", 1)[0]): (k.split("|", 1)[1] if "|" in k else "", v)
            for k, v in self.lexicon.get("drug_codes", {}).items()
        }
        self.drug_index: dict[str, list[str]] = {}
        self.rx_aliases: dict[str, dict[str, str]] = {}
        self.rx_products: list[dict[str, str]] = []
        self.brand_to_generic: dict[str, str] = {}
        self._products_by_alias: dict[str, list[dict[str, str]]] = {}
        package_index = Path(__file__).resolve().parent / "resources" / "rxnorm_index.json"
        if self.use_catalog and package_index.exists():
            try:
                self.drug_index = json.loads(package_index.read_text(encoding="utf-8"))
            except Exception:
                self.drug_index = {}
        catalog_path = Path(__file__).resolve().parent / "resources" / "rxnorm_catalog.json"
        if self.use_catalog and catalog_path.exists():
            try:
                catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
                self.rx_aliases = catalog.get("aliases", {})
                self.rx_products = catalog.get("products", [])
                self.brand_to_generic = catalog.get("brand_to_generic", {})
            except Exception:
                self.rx_aliases, self.rx_products, self.brand_to_generic = {}, [], {}
        self.diagnoses = {
            normalize_key(k): list(v) for k, v in self.lexicon.get("diagnoses", {}).items()
        }

    def _diagnosis(self, entity: Entity, text: str) -> CandidateResult:
        key = normalize_key(entity.text)
        ids = self.diagnoses.get(key)
        if ids is None:
            # Longest known phrase contained in a noisy mention.
            matches = [(len(k), v) for k, v in self.diagnoses.items() if k in key or key in k]
            ids = max(matches, default=(0, []), key=lambda x: x[0])[1]
        if "trào ngược" in key and re.search(r"viêm\s+thực\s+quản", text, re.IGNORECASE):
            ids = ["K21.0"]
            return CandidateResult(ids, 0.98, "context: reflux with esophagitis")
        return CandidateResult(ids, 0.86 if ids else 0.0, "diagnosis dictionary" if ids else "no exact ICD alias")

    def _drug(self, entity: Entity, raw_text: str = "") -> CandidateResult:
        key = normalize_key(entity.text)
        key = re.sub(r"(?<!\w)laxis(?!\w)", "lasix", key)
        strength_match = re.search(
            r"(\d+(?:[.,]\d+)?(?:\s*-\s*\d+(?:[.,]\d+)?)?)\s*(mg|g|mcg|ml)\b",
            key,
        )
        strength = f"{strength_match.group(1)} {strength_match.group(2)}" if strength_match else ""
        strength = strength.replace(",", ".")
        strength = re.sub(r"(?<=\d)\.0+(?=\s|$)", "", strength)
        # Route is often written immediately after the drug span in the raw
        # note (the span must not absorb it). Inspect only a small local window
        # for candidate resolution; strength still comes solely from the span.
        start, end = entity.position
        route_context = key
        if raw_text and 0 <= start <= end <= len(raw_text):
            route_context = normalize_key(raw_text[max(0, start - 12): min(len(raw_text), end + 32)])
        route = ""
        if re.search(r"\biv\b|tiêm|tiem|tĩnh\s*mạch|tinh\s*mach|inject", route_context):
            route = "injection"
        elif re.search(r"\bpo\b|\buống\b|uong|oral", route_context):
            route = "oral"
        direct_curated: list[str] = []
        # Common brand alias absent from the local CPC alias subset. The
        # strength-specific RxCUI is the exact 3 mg warfarin tablet.
        if re.search(r"(?<!\w)coumadin(?!\w)", key) and strength == "3 mg":
            direct_curated = ["855318"]
        elif re.search(r"(?<!\w)vicodin(?!\w)", key) and not strength:
            # Vicodin's common 300 mg acetaminophen / 5 mg hydrocodone tablet.
            direct_curated = ["856987"]
        for raw_key, values in self.lexicon.get("drug_codes", {}).items():
            raw_ingredient, separator, raw_strength = raw_key.partition("|")
            if normalize_key(raw_ingredient) not in key:
                continue
            if separator and normalize_key(raw_strength) != strength:
                continue
            direct_curated = list(values)[:1]
            break
        ingredient = ""
        for known in self.lexicon.get("drugs", []):
            if normalize_key(known) in key:
                if len(known) > len(ingredient):
                    ingredient = normalize_key(known)
        alias_row: dict[str, str] | None = None
        if self.use_catalog and self.rx_aliases:
            matches = []
            words = re.findall(r"[a-z0-9'-]+", key)
            for start in range(len(words)):
                for size in range(1, min(5, len(words) - start) + 1):
                    alias = " ".join(words[start:start + size])
                    row = self.rx_aliases.get(alias)
                    if row:
                        matches.append((len(alias), {"IN": 4, "PIN": 3, "MIN": 2, "BN": 1}.get(row["tty"], 0), alias, row))
            if matches:
                _, _, ingredient, alias_row = max(matches)
                # A bare brand plus a numeric dose does not establish generic
                # dose form (Dilaudid 3 mg could be several formulations).
                # Expand a brand to its ingredient only when explicit route
                # evidence lets us prove a matching generic product.
                if alias_row["tty"] == "BN" and route:
                    ingredient = self.brand_to_generic.get(alias_row["rxcui"], ingredient)
        ids: list[str] = direct_curated
        # A mention containing only a generic ingredient (for example
        # ``aspirin``) should map to the RxNorm IN/PIN/MIN concept.  The
        # compact product index is deliberately broad and its first value is
        # lexicographic, not clinically meaningful; using it here previously
        # selected unrelated combination products.  Retain branded names as
        # their exact BN concept and retain a manually curated product only
        # where the supplied strength matches exactly.
        if (
            not ids
            and not strength
            and alias_row
            and alias_row["tty"] in {"IN", "PIN", "MIN", "BN"}
        ):
            ids = [alias_row["rxcui"]]
        if ingredient:
            # Curated mappings that match the organiser's examples take
            # precedence. The broad CPC index is only a fallback and must never
            # emit hundreds of RxCUIs because Jaccard strongly penalizes extras.
            exact = (
                self.lexicon.get("drug_codes", {}).get(f"{ingredient}|{strength}")
                or self.drug_index.get(f"{ingredient}|{strength}")
            ) if strength else None
            # The generic index has no route/form guarantee.  When a route is
            # explicit, product selection below must prove that route instead
            # of falling back to its arbitrary first identifier.
            if exact and not ids and not route:
                ids = list(exact)[:1]
            elif not strength and not ids:
                curated_ingredient = next(
                    (
                        list(values)[:1]
                        for raw_key, values in self.lexicon.get("drug_codes", {}).items()
                        if normalize_key(raw_key.split("|", 1)[0]) == ingredient
                        and "|" not in raw_key
                    ),
                    [],
                )
                exact_ingredient = curated_ingredient or self.drug_index.get(f"{ingredient}|")
                if exact_ingredient:
                    ids = list(exact_ingredient)[:1]
        if not ids and ingredient:
            if strength:
                mention = set(re.findall(r"[a-z0-9.]+", key))
                wanted_strength = strength.casefold()
                forms = {
                    "po": "oral", "xl": "extended", "xr": "extended",
                    "er": "extended", "sr": "extended", "iv": "injection",
                }
                expanded = mention | {forms[t] for t in mention if t in forms}
                tty_bonus = {"SCD": 8, "SBD": 7, "SCDF": 5, "SBDF": 4, "SCDG": 3, "SBDG": 2}
                ranked: list[tuple[float, str]] = []
                products = self._products_by_alias.get(ingredient)
                if products is None:
                    products = [
                        product for product in self.rx_products
                        if re.search(r"(?<!\w)" + re.escape(ingredient) + r"(?!\w)", product["norm"])
                    ]
                    self._products_by_alias[ingredient] = products
                for product in products:
                    norm = product["norm"]
                    if route and route not in norm:
                        continue
                    product_strengths = {
                        f"{number} {unit}".casefold()
                        for number, unit in re.findall(
                            r"(\d+(?:\.\d+)?)\s*(mg|g|mcg|ml|unit)(?:/ml)?\b",
                            norm,
                        )
                    }
                    # RxNorm injection SCDs commonly express a concentration
                    # plus fill volume. Add the clinically stated total dose
                    # (e.g. 4 ML * 10 MG/ML = 40 MG) without discarding the
                    # concentration itself.
                    for volume, dose, unit in re.findall(
                        r"(\d+(?:\.\d+)?)\s*ml\s+.*?(\d+(?:\.\d+)?)\s*(mg|g|mcg)/ml\b",
                        norm,
                    ):
                        total = float(volume) * float(dose)
                        total_text = f"{total:g} {unit}".casefold()
                        product_strengths.add(total_text)
                    if wanted_strength not in product_strengths:
                        continue
                    product_tokens = set(re.findall(r"[a-z0-9.]+", norm))
                    overlap = len(expanded & product_tokens) / max(1, len(expanded | product_tokens))
                    score = 100 + tty_bonus.get(product["tty"], 0) + 20 * overlap
                    ranked.append((score, product["rxcui"]))
                if ranked:
                    ranked.sort(key=lambda item: (-item[0], int(item[1])))
                    ids = [ranked[0][1]]
            if (
                not ids
                and alias_row is not None
                and not route
                and not (self.strict_strength and strength)
            ):
                ids = [alias_row["rxcui"]]
        if not ids and ingredient and not route and not (self.strict_strength and strength):
            curated_ingredient = next(
                (
                    list(values)[:1]
                    for raw_key, values in self.lexicon.get("drug_codes", {}).items()
                    if normalize_key(raw_key.split("|", 1)[0]) == ingredient
                    and "|" not in raw_key
                ),
                [],
            )
            exact_ingredient = curated_ingredient or self.drug_index.get(f"{ingredient}|")
            if exact_ingredient:
                ids = list(exact_ingredient)[:1]
        return CandidateResult(ids, 0.95 if ids and strength else 0.72 if ids else 0.0, "drug dictionary" if ids else "no exact RxCUI alias")

    def resolve(self, entity: Entity, raw_text: str) -> Entity:
        if entity.type == "CHẨN_ĐOÁN":
            result = self._diagnosis(entity, raw_text)
        elif entity.type == "THUỐC":
            result = self._drug(entity, raw_text)
        else:
            return entity
        entity.candidates = result.ids
        return entity
