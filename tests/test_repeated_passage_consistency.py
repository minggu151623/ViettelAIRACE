from pathlib import Path

from airace.repeated_passage_consistency import (Occurrence, RelativeEntity,
                                                 eligible_entities, repeated_lines,
                                                 select_non_overlapping)


def test_repeated_lines_require_distinct_records(tmp_path: Path):
    line = "Một dòng lâm sàng đủ dài để được xem là đoạn lặp nguyên văn."
    (tmp_path / "1.txt").write_text(line + "\n" + line, encoding="utf-8")
    (tmp_path / "2.txt").write_text(line, encoding="utf-8")
    groups = repeated_lines(tmp_path)
    assert len(groups[line]) == 3


def test_entity_requires_two_occurrences_and_families():
    text = "đau đầu kéo dài"
    entity = RelativeEntity(0, 7, "TRIỆU_CHỨNG")
    occurrences = [Occurrence(1, 0, len(text)), Occurrence(2, 0, len(text))]
    evidence = {entity: {"occurrences": set(occurrences),
                         "families": {"bami", "vietmed"},
                         "units": {("bami", occurrences[0]), ("vietmed", occurrences[1])}}}
    selected, ties = eligible_entities(text, occurrences, evidence)
    assert selected == [entity]
    assert ties == 0


def test_interval_decoder_prefers_stronger_entity():
    text = "đau đầu kéo dài"
    short = RelativeEntity(0, 7, "TRIỆU_CHỨNG")
    long = RelativeEntity(0, 16, "TRIỆU_CHỨNG")
    occurrence = Occurrence(1, 0, len(text))
    evidence = {
        short: {"occurrences": {occurrence}, "families": {"bami", "vietmed"},
                "units": {("bami", occurrence), ("vietmed", occurrence)}},
        long: {"occurrences": {occurrence}, "families": {"bami"},
               "units": {("bami", occurrence)}},
    }
    assert select_non_overlapping(text, [short, long], evidence) == [short]
