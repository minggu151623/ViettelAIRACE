import json
from pathlib import Path

from airace.ontology_graph import build_rxnorm_graph, build_who_graph, combine_graphs


def test_who_graph_builds_parent_child_and_siblings(tmp_path: Path) -> None:
    source = tmp_path / "who.txt"
    source.write_text(
        "3;N;X;01;A00;A00.-;A00;A00;Cholera;;;;;;;;\n"
        "4;T;X;01;A00;A00.0;A00.0;A000;Cholera one;;;;;;;;\n"
        "4;T;X;01;A00;A00.1;A00.1;A001;Cholera two;;;;;;;;\n",
        encoding="utf-8",
    )
    graph = build_who_graph(source)
    assert graph.adjacency("icd_parent")["ICD:A00.0"] == {"ICD:A00"}
    assert graph.icd_siblings("ICD:A00.0") == ("ICD:A00.1",)


def test_rxnorm_graph_restricts_relations_to_catalog_nodes(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps(
            {
                "aliases": {
                    "aspirin": {"rxcui": "1", "tty": "IN", "term": "Aspirin"},
                    "brand": {"rxcui": "2", "tty": "BN", "term": "Brand"},
                },
                "products": [],
                "brand_to_generic": {},
            }
        ),
        encoding="utf-8",
    )
    relations = tmp_path / "RXNREL.RRF"
    relations.write_text(
        "1||||2|||has_tradename|||RXNORM|||||\n"
        "1||||999|||has_ingredient|||RXNORM|||||\n"
        "1||||2|||unregistered_relation|||RXNORM|||||\n",
        encoding="utf-8",
    )
    graph = build_rxnorm_graph(catalog, relations)
    assert len(graph.nodes) == 2
    assert [(edge.source, edge.target, edge.relation) for edge in graph.edges] == [
        ("RX:1", "RX:2", "rx_has_tradename")
    ]


def test_combined_manifest_is_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "who.txt"
    source.write_text("3;N;X;01;A00;A00.-;A00;A00;Cholera;;;;;;;;\n", encoding="utf-8")
    first = combine_graphs(build_who_graph(source)).manifest()
    second = combine_graphs(build_who_graph(source)).manifest()
    assert first == second
    assert first["nodes_by_ontology"] == {"WHO_ICD10_2019": 1}

