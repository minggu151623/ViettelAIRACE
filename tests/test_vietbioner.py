import json
from pathlib import Path

from airace.vietbioner import prepare_vietbioner_transfer


ROOT = Path(__file__).resolve().parents[1]


def test_vietbioner_transfer_keeps_only_diagnostic_procedure(tmp_path) -> None:
    report = prepare_vietbioner_transfer(ROOT / "external" / "VietBioNER", tmp_path)
    assert report["mapping"] == {"DiagnosticProcedure": "TÊN_XÉT_NGHIỆM"}
    assert report["splits"]["train"]["examples"] == 706
    assert report["splits"]["train"]["diagnostic_procedure_entities"] == 191

    for split in ("train", "valid", "test"):
        for line in (tmp_path / f"{split}.jsonl").read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            for entity in row["entities"]:
                start, end = entity["position"]
                assert entity["type"] == "TÊN_XÉT_NGHIỆM"
                assert row["text"][start:end] == entity["text"]
