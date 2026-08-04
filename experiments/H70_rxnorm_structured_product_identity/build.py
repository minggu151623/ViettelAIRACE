from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from airace.rxnorm_exact_brand import load_unique_active_brands
from airace.rxnorm_structured_product import build_structured_product_submission


if __name__ == "__main__":
    conso = ROOT / "airace/resources/rxnorm_20260706/rrf/RXNCONSO.RRF"
    report = build_structured_product_submission(
        input_dir=ROOT / "turn2/input",
        baseline_dir=ROOT / "turn2/output_v24_rxnorm_exact_brand_identity",
        output_dir=ROOT / "turn2/output_v25_rxnorm_structured_product_identity",
        conso_path=conso,
        unique_brands=load_unique_active_brands(conso),
        zip_path=ROOT / "turn2/output_v25_rxnorm_structured_product_identity.zip",
        report_path=ROOT / "experiments/H70_rxnorm_structured_product_identity/results/report.json",
    )
    print(report["status"])
    print(report["zip_sha256"])
    print(f"changed_rows={report['changed_rows']} changed_records={report['changed_records']}")
