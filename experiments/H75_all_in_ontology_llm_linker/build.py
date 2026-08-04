from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from airace.all_in_ontology_linker import build_all_in_ontology_linker_submission


if __name__ == "__main__":
    report = build_all_in_ontology_linker_submission(
        input_dir=ROOT / "turn2/input",
        h69_dir=ROOT / "turn2/output_v24_rxnorm_exact_brand_identity",
        h74_dir=ROOT / "turn2/output_v29_constrained_candidate_moe",
        output_dir=ROOT / "turn2/output_v30_all_in_ontology_llm_linker",
        zip_path=ROOT / "turn2/output_v30_all_in_ontology_llm_linker.zip",
        report_path=ROOT / "experiments/H75_all_in_ontology_llm_linker/results/report.json",
        cache_dir=ROOT / "experiments/H75_all_in_ontology_llm_linker/cache",
        h74_report_path=ROOT / "experiments/H74_constrained_candidate_moe/results/report.json",
        resource_dir=ROOT / "airace/resources",
    )
    print(report["status"])
    print(report["zip"])
    print(report["zip_sha256"])
    print(f"changed_rows={report['changed_rows']} changed_records={report['changed_records']}")
