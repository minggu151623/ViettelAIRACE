from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .who_icd_rebuild import load_who_icd10


RXNORM_RELATIONS = frozenset(
    {
        "isa",
        "inverse_isa",
        "has_ingredient",
        "ingredient_of",
        "has_precise_ingredient",
        "precise_ingredient_of",
        "has_tradename",
        "tradename_of",
        "has_dose_form",
        "dose_form_of",
        "consists_of",
        "constitutes",
        "has_part",
        "part_of",
    }
)


@dataclass(frozen=True)
class ConceptNode:
    identifier: str
    ontology: str
    canonical: str
    aliases: tuple[str, ...]
    semantic_type: str


@dataclass(frozen=True, order=True)
class ConceptEdge:
    source: str
    target: str
    relation: str


@dataclass
class OntologyGraph:
    nodes: dict[str, ConceptNode]
    edges: tuple[ConceptEdge, ...]

    def adjacency(self, relation: str | None = None) -> dict[str, set[str]]:
        values: dict[str, set[str]] = defaultdict(set)
        for edge in self.edges:
            if relation is None or edge.relation == relation:
                values[edge.source].add(edge.target)
        return values

    def icd_siblings(self, identifier: str) -> tuple[str, ...]:
        """Return same-parent ICD nodes for graph-derived hard negatives."""

        parents = self.adjacency("icd_parent").get(identifier, set())
        children = self.adjacency("icd_child")
        siblings: set[str] = set()
        for parent in parents:
            siblings.update(children.get(parent, set()))
        siblings.discard(identifier)
        return tuple(sorted(siblings))

    def manifest(self) -> dict[str, object]:
        node_hash = hashlib.sha256()
        for identifier in sorted(self.nodes):
            node_hash.update(
                json.dumps(
                    asdict(self.nodes[identifier]),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            node_hash.update(b"\n")
        edge_hash = hashlib.sha256()
        relation_counts: dict[str, int] = defaultdict(int)
        for edge in self.edges:
            edge_hash.update(f"{edge.source}\t{edge.relation}\t{edge.target}\n".encode())
            relation_counts[edge.relation] += 1
        ontology_counts: dict[str, int] = defaultdict(int)
        for node in self.nodes.values():
            ontology_counts[node.ontology] += 1
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "nodes_by_ontology": dict(sorted(ontology_counts.items())),
            "edges_by_relation": dict(sorted(relation_counts.items())),
            "node_sha256": node_hash.hexdigest(),
            "edge_sha256": edge_hash.hexdigest(),
        }


def _normalise_aliases(values: Iterable[str]) -> tuple[str, ...]:
    aliases = {" ".join(value.casefold().split()) for value in values if value.strip()}
    return tuple(sorted(aliases))


def build_who_graph(path: str | Path | None = None) -> OntologyGraph:
    codes = load_who_icd10(path)
    nodes = {
        f"ICD:{code}": ConceptNode(
            identifier=f"ICD:{code}",
            ontology="WHO_ICD10_2019",
            canonical=title,
            aliases=_normalise_aliases((title,)),
            semantic_type="DIAGNOSIS",
        )
        for code, title in codes.items()
    }
    edges: set[ConceptEdge] = set()
    for code in codes:
        if "." not in code:
            continue
        parent = code[:3]
        if parent not in codes:
            continue
        child_id, parent_id = f"ICD:{code}", f"ICD:{parent}"
        edges.add(ConceptEdge(child_id, parent_id, "icd_parent"))
        edges.add(ConceptEdge(parent_id, child_id, "icd_child"))
    return OntologyGraph(nodes=nodes, edges=tuple(sorted(edges)))


def build_rxnorm_graph(
    catalog_path: str | Path,
    relation_path: str | Path,
) -> OntologyGraph:
    catalog = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
    terms: dict[str, set[str]] = defaultdict(set)
    typed_terms: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
    priority = {
        "IN": 0,
        "PIN": 1,
        "MIN": 2,
        "BN": 3,
        "SCD": 4,
        "SBD": 5,
        "SCDF": 6,
        "SBDF": 7,
        "SCDG": 8,
        "SBDG": 9,
        "GPCK": 10,
        "BPCK": 11,
    }
    for value in catalog["aliases"].values():
        rxcui, tty, term = value["rxcui"], value["tty"], value["term"]
        terms[rxcui].add(term)
        typed_terms[rxcui].append((priority.get(tty, 99), term.casefold(), tty))
    for value in catalog["products"]:
        rxcui, tty, term = value["rxcui"], value["tty"], value["term"]
        terms[rxcui].add(term)
        typed_terms[rxcui].append((priority.get(tty, 99), term.casefold(), tty))
    nodes: dict[str, ConceptNode] = {}
    valid_ids = set(terms)
    for rxcui, aliases in terms.items():
        _, canonical, tty = min(typed_terms[rxcui])
        identifier = f"RX:{rxcui}"
        nodes[identifier] = ConceptNode(
            identifier=identifier,
            ontology="RXNORM_CPC_2026_07",
            canonical=canonical,
            aliases=_normalise_aliases(aliases),
            semantic_type=tty,
        )
    edges: set[ConceptEdge] = set()
    with Path(relation_path).open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            fields = line.rstrip("\n").split("|")
            if len(fields) < 11 or fields[10] != "RXNORM":
                continue
            source, target, relation = fields[0], fields[4], fields[7]
            if relation not in RXNORM_RELATIONS or source not in valid_ids or target not in valid_ids:
                continue
            edges.add(ConceptEdge(f"RX:{source}", f"RX:{target}", f"rx_{relation}"))
    return OntologyGraph(nodes=nodes, edges=tuple(sorted(edges)))


def combine_graphs(*graphs: OntologyGraph) -> OntologyGraph:
    nodes: dict[str, ConceptNode] = {}
    edges: set[ConceptEdge] = set()
    for graph in graphs:
        overlap = nodes.keys() & graph.nodes.keys()
        if overlap:
            raise ValueError(f"duplicate concept identifiers: {sorted(overlap)[:3]}")
        nodes.update(graph.nodes)
        edges.update(graph.edges)
    return OntologyGraph(nodes=nodes, edges=tuple(sorted(edges)))


def build_project_graph(resource_dir: str | Path | None = None) -> OntologyGraph:
    root = Path(resource_dir) if resource_dir else Path(__file__).resolve().parent / "resources"
    return combine_graphs(
        build_who_graph(root / "icd10_2019" / "icd102019syst_codes.txt"),
        build_rxnorm_graph(
            root / "rxnorm_catalog.json",
            root / "rxnorm_20260706" / "rrf" / "RXNREL.RRF",
        ),
    )


def write_manifest(graph: OntologyGraph, path: str | Path) -> dict[str, object]:
    manifest = graph.manifest()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest

