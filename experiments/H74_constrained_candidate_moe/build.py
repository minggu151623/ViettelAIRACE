from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from airace.constrained_candidate_moe import build_constrained_candidate_moe_submission


if __name__ == "__main__":
    report = build_constrained_candidate_moe_submission(
        input_dir=ROOT / "turn2" / "input",
        h69_dir=ROOT / "turn2" / "output_v24_rxnorm_exact_brand_identity",
        h71_dir=ROOT / "turn2" / "output_v26_rxnorm_identity_completion",
        output_dir=ROOT / "turn2" / "output_v29_constrained_candidate_moe",
        zip_path=ROOT / "turn2" / "output_v29_constrained_candidate_moe.zip",
        report_path=ROOT / "experiments" / "H74_constrained_candidate_moe" / "results" / "report.json",
    )
    print(report["status"])
    print(report["zip"])
    print(report["zip_sha256"])
    print(f"changed_rows={report['changed_rows']} changed_records={report['changed_records']}")
