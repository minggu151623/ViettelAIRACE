import json
from pathlib import Path

from airace.proposals import Proposal, dump_proposals
from airace.turn2_ensemble import build_turn2_ensemble


def test_ensemble_requires_three_exact_sources_and_keeps_baseline(tmp_path: Path) -> None:
    inputs = tmp_path / "input"
    source = tmp_path / "source"
    output = tmp_path / "output"
    inputs.mkdir()
    source.mkdir()
    text = "Bệnh nhân sốt và viêm phổi."
    (inputs / "1.txt").write_text(text, encoding="utf-8")
    (source / "1.json").write_text(
        json.dumps([
            {
                "text": "sốt",
                "type": "TRIỆU_CHỨNG",
                "assertions": [],
                "position": [10, 13],
            }
        ], ensure_ascii=False),
        encoding="utf-8",
    )
    start = text.index("viêm phổi")
    proposal_dirs = []
    for name in ("a", "b", "c"):
        directory = tmp_path / name
        proposal_dirs.append(directory)
        dump_proposals([
            Proposal(
                "viêm phổi",
                "CHẨN_ĐOÁN",
                (start, start + len("viêm phổi")),
                0.9,
                name,
            )
        ], directory / "1.json")

    report = build_turn2_ensemble(inputs, source, proposal_dirs, output)
    values = json.loads((output / "1.json").read_text(encoding="utf-8"))
    assert report["additions"] == 1
    assert [value["text"] for value in values] == ["sốt", "viêm phổi"]
    assert values[1]["candidates"] == []


def test_ensemble_rejects_drug_even_with_three_sources(tmp_path: Path) -> None:
    inputs = tmp_path / "input"
    source = tmp_path / "source"
    output = tmp_path / "output"
    inputs.mkdir()
    source.mkdir()
    (inputs / "1.txt").write_text("aspirin", encoding="utf-8")
    (source / "1.json").write_text("[]", encoding="utf-8")
    proposal_dirs = []
    for name in ("a", "b", "c"):
        directory = tmp_path / name
        proposal_dirs.append(directory)
        dump_proposals([
            Proposal("aspirin", "THUỐC", (0, 7), 0.9, name)
        ], directory / "1.json")

    report = build_turn2_ensemble(inputs, source, proposal_dirs, output)
    assert report["additions"] == 0
    assert report["rejected"]["ineligible_type"] == 1
