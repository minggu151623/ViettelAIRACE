from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from airace.repeated_passage_rebuild import build_repeated_passage_submission


if __name__ == "__main__":
    report = build_repeated_passage_submission(
        input_dir=ROOT / "turn2/input",
        baseline_dir=ROOT / "turn2/output_v24_rxnorm_exact_brand_identity",
        output_dir=ROOT / "turn2/output_v28_type_routed_repeated_passage_rebuild",
        baseline_zip=ROOT / "turn2/output_v24_rxnorm_exact_brand_identity.zip",
        h69_report_path=ROOT / "experiments/H69_rxnorm_exact_brand_identity/results/report.json",
        zip_path=ROOT / "turn2/output_v28_type_routed_repeated_passage_rebuild.zip",
        report_path=ROOT / "experiments/H73_type_routed_repeated_passage_rebuild/results/report.json",
        target_types={"CHẨN_ĐOÁN", "TRIỆU_CHỨNG"},
        hypothesis="H73_type_routed_repeated_passage_rebuild",
    )
    print(report["status"])
    print(report["zip_sha256"])
    print(
        f"changed_records={report['changed_records']} "
        f"span_type_symmetric_difference={report['span_type_symmetric_difference']}"
    )
