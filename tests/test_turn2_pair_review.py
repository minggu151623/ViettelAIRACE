import json
from pathlib import Path

from airace.proposals import Proposal, dump_proposals
from airace.turn2_pair_review import collect_pair_rows, merge_pair_review
from airace.assertions import infer_assertions
from airace.schema import Entity


def test_collect_pair_rows_requires_vietmed_and_one_bami(tmp_path: Path) -> None:
    inputs, source = tmp_path / "input", tmp_path / "source"
    inputs.mkdir(); source.mkdir()
    text = "Bệnh nhân đau đầu."
    (inputs / "1.txt").write_text(text, encoding="utf-8")
    (source / "1.json").write_text("[]", encoding="utf-8")
    start = text.index("đau đầu")
    dirs = []
    for name, confidence in (("vietmed_ner", .95), ("bami_v3", .70)):
        directory = tmp_path / name; dirs.append(directory)
        dump_proposals([
            Proposal("đau đầu", "TRIỆU_CHỨNG", (start, start + 7), confidence, name)
        ], directory / "1.json")
    rows = collect_pair_rows(inputs, source, dirs)
    assert len(rows) == 1
    assert rows[0]["sources"] == ["bami_v3", "vietmed_ner"]


def test_merge_pair_review_adds_only_accepted(tmp_path: Path) -> None:
    inputs, source, output = tmp_path / "input", tmp_path / "source", tmp_path / "output"
    inputs.mkdir(); source.mkdir()
    text = "đau đầu và ho"
    (inputs / "1.txt").write_text(text, encoding="utf-8")
    (source / "1.json").write_text("[]", encoding="utf-8")
    review = {
        "rows": [
            {"record": "1", "text": "đau đầu", "type": "TRIỆU_CHỨNG", "position": [0, 7], "accepted": True},
            {"record": "1", "text": "ho", "type": "TRIỆU_CHỨNG", "position": [12, 14], "accepted": False},
        ]
    }
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
    report = merge_pair_review(inputs, source, review_path, output)
    values = json.loads((output / "1.json").read_text(encoding="utf-8"))
    assert report["additions"] == 1
    assert [value["text"] for value in values] == ["đau đầu"]


def test_phu_nhan_is_a_negation_cue() -> None:
    text = "Bệnh nhân phủ nhận buồn nôn/nôn."
    start = text.index("buồn nôn")
    entity = Entity("buồn nôn", "TRIỆU_CHỨNG", position=(start, start + 8))
    assert infer_assertions(entity, text) == ["isNegated"]
