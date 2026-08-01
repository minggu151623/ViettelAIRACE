from __future__ import annotations

import json

import pytest

from airace.pseudo_reconstruct import reconstruct_pseudo_labels


def test_reconstruct_drops_only_explicit_calibration_dummy(tmp_path):
    inputs = tmp_path / "input"
    source = tmp_path / "source"
    output = tmp_path / "output"
    inputs.mkdir()
    source.mkdir()
    (inputs / "1.txt").write_text("Sốt cao", encoding="utf-8")
    (source / "1.json").write_text(
        json.dumps(
            [
                {
                    "text": "Sốt cao",
                    "type": "TRIỆU_CHỨNG",
                    "assertions": [],
                    "position": [0, 7],
                },
                {
                    "text": "x",
                    "type": "TRIỆU_CHỨNG",
                    "assertions": [],
                    "position": [1_010_000, 1_010_001],
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = reconstruct_pseudo_labels(
        inputs, source, output, expected_kept=1, expected_dropped=1
    )

    assert report["kept_real_rows"] == 1
    assert report["dropped_calibration_rows"] == 1
    assert json.loads((output / "1.json").read_text(encoding="utf-8"))[0]["text"] == "Sốt cao"


def test_reconstruct_fails_closed_on_non_dummy_invalid_row(tmp_path):
    inputs = tmp_path / "input"
    source = tmp_path / "source"
    inputs.mkdir()
    source.mkdir()
    (inputs / "1.txt").write_text("Sốt cao", encoding="utf-8")
    (source / "1.json").write_text(
        json.dumps(
            [{"text": "đau", "type": "TRIỆU_CHỨNG", "position": [0, 3]}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid real row"):
        reconstruct_pseudo_labels(
            inputs, source, tmp_path / "output", expected_kept=None, expected_dropped=None
        )
