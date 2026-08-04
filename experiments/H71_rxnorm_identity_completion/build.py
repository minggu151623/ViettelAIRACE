from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from airace.rxnorm_identity_completion import build_identity_completion_submission


if __name__ == "__main__":
    report = build_identity_completion_submission(
        input_dir=ROOT / "turn2/input",
        baseline_dir=ROOT / "turn2/output_v24_rxnorm_exact_brand_identity",
        output_dir=ROOT / "turn2/output_v26_rxnorm_identity_completion",
        conso_path=ROOT / "airace/resources/rxnorm_20260706/rrf/RXNCONSO.RRF",
        zip_path=ROOT / "turn2/output_v26_rxnorm_identity_completion.zip",
        report_path=ROOT / "experiments/H71_rxnorm_identity_completion/results/report.json",
    )
    print(report["status"])
    print(report["zip_sha256"])
    print(f"changed_rows={report['changed_rows']} changed_records={report['changed_records']}")
