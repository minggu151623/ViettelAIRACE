from pathlib import Path

from airace.target_adaptive_pretrain import target_windows


class _Tokenizer:
    def __call__(self, text: str, **_: object) -> dict:
        values = [ord(char) for char in text]
        return {
            "input_ids": [values],
            "attention_mask": [[1] * len(values)],
        }


def test_target_windows_use_numeric_record_order_and_no_labels(tmp_path: Path) -> None:
    (tmp_path / "10.txt").write_text("b", encoding="utf-8")
    (tmp_path / "2.txt").write_text("a", encoding="utf-8")
    windows = target_windows(_Tokenizer(), tmp_path)
    assert [row["input_ids"] for row in windows] == [[ord("a")], [ord("b")]]
    assert all(set(row) == {"input_ids", "attention_mask"} for row in windows)
