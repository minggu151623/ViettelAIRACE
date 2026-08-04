from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from airace.repeated_passage_rebuild import build_repeated_passage_submission


if __name__ == "__main__":
    report = build_repeated_passage_submission(
        input_dir=ROOT / "turn2/input",
        baseline_dir=ROOT / "turn2/output_v24_rxnorm_exact_brand_identity",
        output_dir=ROOT / "turn2/output_v27_repeated_passage_multiview_rebuild",
        baseline_zip=ROOT / "turn2/output_v24_rxnorm_exact_brand_identity.zip",
        h69_report_path=ROOT / "experiments/H69_rxnorm_exact_brand_identity/results/report.json",
        zip_path=ROOT / "turn2/output_v27_repeated_passage_multiview_rebuild.zip",
        report_path=ROOT / "experiments/H72_repeated_passage_multiview_rebuild/results/report.json",
    )
    print(report["status"])
    print(report["zip_sha256"])
    print(
        f"changed_records={report['changed_records']} "
        f"span_type_symmetric_difference={report['span_type_symmetric_difference']}"
    )
