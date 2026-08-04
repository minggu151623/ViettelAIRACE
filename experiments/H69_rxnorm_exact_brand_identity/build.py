from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from airace.rxnorm_exact_brand import build_exact_brand_submission


if __name__ == "__main__":
    report = build_exact_brand_submission(
        input_dir=ROOT / "turn2" / "input",
        baseline_dir=ROOT / "turn2" / "output_v10_multiview_consensus",
        output_dir=ROOT / "turn2" / "output_v24_rxnorm_exact_brand_identity",
        conso_path=ROOT / "airace" / "resources" / "rxnorm_20260706" / "rrf" / "RXNCONSO.RRF",
        zip_path=ROOT / "turn2" / "output_v24_rxnorm_exact_brand_identity.zip",
        report_path=ROOT / "experiments" / "H69_rxnorm_exact_brand_identity" / "results" / "report.json",
    )
    print(report["status"])
    print(report["zip"])
    print(report["zip_sha256"])
    print(f"changed_rows={report['changed_rows']} changed_records={report['changed_records']}")
