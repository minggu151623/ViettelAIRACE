from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from airace.additive_consensus_rescue import build_additive_consensus_rescue


if __name__ == "__main__":
    report = build_additive_consensus_rescue(
        input_dir=ROOT / "turn2/input",
        h69_dir=ROOT / "turn2/output_v24_rxnorm_exact_brand_identity",
        h73_dir=ROOT / "turn2/output_v28_type_routed_repeated_passage_rebuild",
        output_dir=ROOT / "turn2/output_v31_additive_consensus_rescue",
        zip_path=ROOT / "turn2/output_v31_additive_consensus_rescue.zip",
        report_path=ROOT / "experiments/H76_additive_consensus_rescue/results/report.json",
    )
    print(report["status"])
    print(report["zip"])
    print(report["zip_sha256"])
    print(f"additions={report['additions']} changed_records={report['changed_records']}")
