from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .candidates import CandidateResolver
from .audit import build_audit
from .inference import infer_directory
from .metrics import evaluate_dirs
from .package_output import package_output
from .resources import prepare_resources
from .validator import validate_output_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m airace")
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare-resources")
    prep.add_argument("--download-rxnorm", action="store_true")
    prep.add_argument("--resource-dir", default=None)
    inf = sub.add_parser("infer")
    inf.add_argument("--input", default="input")
    inf.add_argument("--output", default="output")
    inf.add_argument("--report", default="reports/inference.json")
    inf.add_argument("--model-checkpoint", default=None)
    inf.add_argument(
        "--profile",
        choices=["baseline", "baseline_strength", "section_only", "precision", "recall"],
        default="precision",
    )
    llm = sub.add_parser("llm-infer")
    llm.add_argument("--input", default="input")
    llm.add_argument("--output", default="output_llm")
    llm.add_argument("--report", default="reports/llm_inference.json")
    llm.add_argument("--model", default="qwen3:8b")
    llm.add_argument("--no-merge-rules", action="store_true")
    llm.add_argument("--no-resume", action="store_true")
    llm.add_argument(
        "--prompt-profile",
        choices=["broad", "structured"],
        default="broad",
    )
    llm.add_argument(
        "--records",
        default=None,
        help="Comma-separated record ids for bounded validation.",
    )
    silver = sub.add_parser("prepare-silver")
    silver.add_argument("--input", default="input")
    silver.add_argument("--qwen", default="output_qwen3_hybrid")
    silver.add_argument("--output", default="labels/silver_consensus.jsonl")
    silver.add_argument("--consensus-output", default="output_v3_consensus")
    silver.add_argument("--report", default="reports/silver_consensus.json")
    silver.add_argument(
        "--holdout-labels",
        default="labels/manual_validation.jsonl",
        help="Reviewed records excluded from silver training labels.",
    )
    assemble = sub.add_parser("assemble-consensus")
    assemble.add_argument("--input", default="input")
    assemble.add_argument("--consensus", default="output_v3_consensus")
    assemble.add_argument("--holdout-labels", default="labels/manual_validation.jsonl")
    assemble.add_argument("--output", default="output_v3_consensus_full")
    assemble.add_argument("--report", default="reports/v3_consensus_full.json")
    preserve = sub.add_parser("assertion-preserve")
    preserve.add_argument("--input", default="input")
    preserve.add_argument("--source", default="output_qwen3_hybrid")
    preserve.add_argument("--output", default="output_v4_assertion_preserve")
    preserve.add_argument("--report", default="reports/v4_assertion_preserve.json")
    icd_aliases = sub.add_parser("prepare-icd-aliases")
    icd_aliases.add_argument("--source", default="output_v4_assertion_preserve")
    icd_aliases.add_argument(
        "--output", default="airace/resources/icd10cm_aliases_v5.json"
    )
    icd_aliases.add_argument("--model", default="qwen3:8b")
    icd_aliases.add_argument("--batch-size", type=int, default=32)
    icd_aliases.add_argument("--min-confidence", type=float, default=0.72)
    v5 = sub.add_parser("v5-reconcile")
    v5.add_argument("--input", default="input")
    v5.add_argument("--source", default="output_v4_assertion_preserve")
    v5.add_argument(
        "--aliases", default="airace/resources/icd10cm_aliases_v5.json"
    )
    v5.add_argument("--output", default="output_v5_icd_consensus")
    v5.add_argument("--report", default="reports/v5_icd_consensus.json")
    v5.add_argument(
        "--no-icd",
        action="store_true",
        help="Apply only strong-noise filtering; preserve all Qwen candidate lists.",
    )
    btc = sub.add_parser("format-btc")
    btc.add_argument("--input", default="input")
    btc.add_argument("--source", required=True)
    btc.add_argument("--output", required=True)
    vietmed = sub.add_parser("vietmed-infer")
    vietmed.add_argument("--input", default="input")
    vietmed.add_argument("--output", default="output_v6_vietmed")
    vietmed.add_argument("--report", default="reports/v6_vietmed.json")
    vietmed.add_argument(
        "--model",
        default=(
            "/Users/mac/.cache/huggingface/hub/"
            "models--leduckhai--VietMed-NER/snapshots/"
            "cccffb7de14423114f7d4bafc9f736b9d866e446/"
            "xlm-roberta-base-VietMed-NER"
        ),
    )
    vietmed.add_argument("--reference", default="output_v5_precision_btc")
    vietmed.add_argument("--no-reference", action="store_true")
    vietmed.add_argument("--batch-size", type=int, default=16)
    vietmed.add_argument("--min-confidence", type=float, default=0.55)
    vietmed.add_argument("--device", choices=["auto", "cpu", "mps", "cuda"], default="auto")
    vietmed.add_argument(
        "--proposal-dir",
        default=None,
        help="Optional non-submission sidecars retaining confidence/source.",
    )
    proposal = sub.add_parser("proposal-infer")
    proposal.add_argument("--input", default="input")
    proposal.add_argument("--proposal-dir", required=True)
    proposal.add_argument("--checkpoint", required=True)
    proposal.add_argument("--report", default=None)
    proposal.add_argument("--source", default="token_model")
    proposal.add_argument("--device", choices=["auto", "cpu", "mps", "cuda"], default="auto")
    proposal.add_argument("--max-length", type=int, default=256)
    proposal.add_argument("--stride", type=int, default=64)
    rebuild = sub.add_parser("v6-rebuild")
    rebuild.add_argument("--input", default="input")
    rebuild.add_argument("--source", default="output_v5_precision_btc")
    rebuild.add_argument("--output", default="output_v6_rxnorm_only")
    rebuild.add_argument("--report", default="reports/v6_rxnorm_only.json")
    rebuild.add_argument("--structural-cleanup", action="store_true")
    critic = sub.add_parser("qwen-critic")
    critic.add_argument("--input", default="input")
    critic.add_argument("--source", default="output_v6_structural")
    critic.add_argument("--output", default="output_v6_critic")
    critic.add_argument("--report", default="reports/v6_critic.json")
    critic.add_argument("--model", default="qwen3:8b")
    critic.add_argument(
        "--records",
        default=None,
        help="Comma-separated record ids for a bounded validation run.",
    )
    ablation = sub.add_parser("ablation")
    ablation.add_argument(
        "--mode",
        choices=["assertion_only", "boundary_only", "drug_boundary_only"],
        required=True,
    )
    ablation.add_argument("--input", default="input")
    ablation.add_argument("--source", default="output_v6_structural")
    ablation.add_argument("--output", required=True)
    ablation.add_argument("--report", default=None)
    hybrid = sub.add_parser("specialist-hybrid")
    hybrid.add_argument("--input", default="input")
    hybrid.add_argument("--learned", required=True)
    hybrid.add_argument("--legacy", default="output_v6_structural_btc")
    hybrid.add_argument("--output", required=True)
    hybrid.add_argument("--report", default=None)
    ensemble = sub.add_parser("teacher-student-ensemble")
    ensemble.add_argument("--input", default="input")
    ensemble.add_argument("--student", required=True)
    ensemble.add_argument("--baseline", default="output_v6_structural_btc")
    ensemble.add_argument("--teacher-checkpoint", required=True)
    ensemble.add_argument("--output", required=True)
    ensemble.add_argument("--report", default=None)
    position = sub.add_parser("position-project")
    position.add_argument("--input", default="input")
    position.add_argument("--source", default="output_v6_structural_btc")
    position.add_argument("--output", required=True)
    position.add_argument("--report", default=None)
    evidence = sub.add_parser("evidence-rebuild")
    evidence.add_argument("--input", default="input")
    evidence.add_argument("--source", default="output_v6_structural_btc")
    evidence.add_argument("--output", required=True)
    evidence.add_argument("--report", default=None)
    evidence.add_argument("--refresh-assertions", action="store_true")
    evidence.add_argument("--refresh-rxnorm", action="store_true")
    evidence.add_argument("--split-numeric-labs", action="store_true")
    evidence.add_argument(
        "--all-evidence",
        action="store_true",
        help="Enable assertion, RxNorm, and numeric-lab interventions.",
    )
    evidence.add_argument(
        "--position-mode",
        choices=["raw", "crlf"],
        default="raw",
    )
    silver.add_argument(
        "--teacher",
        default="cbc-528a/BamiBERT-ViMedNER",
    )
    sub.add_parser("annotate").add_argument("--input", default="input")
    # annotate needs a few additional options while retaining the requested command.
    ann = sub.choices["annotate"]
    ann.add_argument("--pred", default="output")
    ann.add_argument("--out", default="labels/annotations.jsonl")
    ann.add_argument(
        "--records",
        default=None,
        help="Optional comma-separated record ids for a blinded calibration queue.",
    )
    ann.add_argument("--manifest", default=None)
    ann.add_argument(
        "--split", choices=["development", "holdout", "all"], default="all"
    )
    blind_prepare = sub.add_parser("blind-prepare")
    blind_prepare.add_argument("--input", default="turn2/input")
    blind_prepare.add_argument(
        "--manifest",
        default="experiments/H21_blind_promotion_gate/calibration_manifest.json",
    )
    blind_prepare.add_argument("--queue-size", type=int, default=18)
    blind_prepare.add_argument("--holdout-size", type=int, default=6)
    blind_eval = sub.add_parser("blind-evaluate")
    blind_eval.add_argument("--input", default="turn2/input")
    blind_eval.add_argument(
        "--manifest",
        default="experiments/H21_blind_promotion_gate/calibration_manifest.json",
    )
    blind_eval.add_argument("--labels", required=True)
    blind_eval.add_argument("--baseline", default="turn2/output_v6_expanded_pair")
    blind_eval.add_argument("--challenger", required=True)
    blind_eval.add_argument(
        "--split", choices=["development", "holdout", "all"], default="development"
    )
    blind_eval.add_argument("--report", required=True)
    blind_eval.add_argument("--bootstrap-iterations", type=int, default=10_000)
    train = sub.add_parser("train")
    train.add_argument("--labels", default="labels/annotations.jsonl")
    train.add_argument("--output", default="models/phobert-medical")
    train.add_argument(
        "--base-model",
        default="cbc-528a/BamiBERT-ViMedNER",
    )
    train.add_argument("--epochs", type=int, default=5)
    train.add_argument("--max-length", type=int, default=256)
    train.add_argument("--stride", type=int, default=64)
    train.add_argument("--learning-rate", type=float, default=3e-5)
    train.add_argument("--validation-ratio", type=float, default=0.2)
    train.add_argument("--validation-labels", default=None)
    train.add_argument("--batch-size", type=int, default=4)
    train.add_argument("--gradient-accumulation", type=int, default=4)
    train.add_argument("--class-weighting", action="store_true")
    transfer = sub.add_parser("prepare-vietbioner-transfer")
    transfer.add_argument("--source", default="external/VietBioNER")
    transfer.add_argument("--output", default="data/vietbioner_transfer")
    ev = sub.add_parser("evaluate")
    ev.add_argument("--gold", required=True)
    ev.add_argument("--pred", required=True)
    reviewed = sub.add_parser("review-evaluate")
    reviewed.add_argument("--labels", default="labels/manual_validation.jsonl")
    reviewed.add_argument("--pred", required=True)
    pack = sub.add_parser("package")
    pack.add_argument("--output", default="output")
    pack.add_argument("--zip", dest="zip_path", default="output.zip")
    pack.add_argument("--input", default="input")
    pack.add_argument("--position-mode", choices=["raw", "crlf"], default="raw")
    val = sub.add_parser("validate")
    val.add_argument("--input", default="input")
    val.add_argument("--output", default="output")
    val.add_argument("--position-mode", choices=["raw", "crlf"], default="raw")
    audit = sub.add_parser("audit")
    audit.add_argument("--baseline", default="output")
    audit.add_argument("--precision", default="output_v2_precision")
    audit.add_argument("--recall", default="output_v2_recall")
    audit.add_argument("--report", default="reports/v2_audit.json")
    t2_review = sub.add_parser("turn2-candidate-review")
    t2_review.add_argument("--input", default="turn2/input")
    t2_review.add_argument("--source", default="turn2/output")
    t2_review.add_argument("--output", default="experiments/H_turn2_llm_guarded_rebuild/candidate_review.json")
    t2_review.add_argument("--model", default="qwen3:8b")
    t2_review.add_argument("--batch-size", type=int, default=32)
    t2 = sub.add_parser("turn2-rebuild")
    t2.add_argument("--input", default="turn2/input")
    t2.add_argument("--source", default="turn2/output")
    t2.add_argument("--proposals", nargs="+", required=True)
    t2.add_argument("--candidate-review", default=None)
    t2.add_argument("--output", required=True)
    t2.add_argument("--report", default=None)
    t2_ensemble = sub.add_parser("turn2-ensemble")
    t2_ensemble.add_argument("--input", default="turn2/input")
    t2_ensemble.add_argument("--source", default="turn2/output_v2_llm_guarded")
    t2_ensemble.add_argument("--proposals", nargs="+", required=True)
    t2_ensemble.add_argument("--output", required=True)
    t2_ensemble.add_argument("--report", default=None)
    t2_ensemble.add_argument("--min-sources", type=int, default=3)
    pair_review = sub.add_parser("turn2-pair-review")
    pair_review.add_argument("--input", default="turn2/input")
    pair_review.add_argument("--source", default="turn2/output_v3_ensemble_core")
    pair_review.add_argument("--proposals", nargs="+", required=True)
    pair_review.add_argument("--output", required=True)
    pair_review.add_argument("--model", default="qwen3:8b")
    pair_review.add_argument("--batch-size", type=int, default=24)
    pair_merge = sub.add_parser("turn2-pair-merge")
    pair_merge.add_argument("--input", default="turn2/input")
    pair_merge.add_argument("--source", default="turn2/output_v3_ensemble_core")
    pair_merge.add_argument("--review", required=True)
    pair_merge.add_argument("--output", required=True)
    pair_merge.add_argument("--report", default=None)
    icd_review = sub.add_parser("turn2-who-icd-review")
    icd_review.add_argument("--input", default="turn2/input")
    icd_review.add_argument("--source", default="turn2/output_v4_pair_qwen")
    icd_review.add_argument("--output", required=True)
    icd_review.add_argument("--model", default="qwen3:8b")
    icd_review.add_argument("--batch-size", type=int, default=32)
    icd_merge = sub.add_parser("turn2-who-icd-merge")
    icd_merge.add_argument("--input", default="turn2/input")
    icd_merge.add_argument("--source", default="turn2/output_v4_pair_qwen")
    icd_merge.add_argument("--review", required=True)
    icd_merge.add_argument("--output", required=True)
    icd_merge.add_argument("--report", default=None)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "prepare-resources":
        result = prepare_resources(
            download_rxnorm=args.download_rxnorm,
            resource_dir=Path(args.resource_dir) if args.resource_dir else None,
        )
    elif args.command == "infer":
        result = infer_directory(
            args.input, args.output, args.report, args.model_checkpoint, args.profile
        )
    elif args.command == "llm-infer":
        from .llm_inference import infer_llm_directory

        result = infer_llm_directory(
            args.input,
            args.output,
            args.report,
            args.model,
            merge_rules=not args.no_merge_rules,
            resume=not args.no_resume,
            prompt_profile=args.prompt_profile,
            record_ids=set(args.records.split(",")) if args.records else None,
        )
    elif args.command == "prepare-silver":
        from .silver import prepare_silver_labels

        result = prepare_silver_labels(
            args.input,
            args.qwen,
            args.output,
            args.teacher,
            args.report,
            args.consensus_output,
            args.holdout_labels,
        )
    elif args.command == "assemble-consensus":
        from .silver import assemble_consensus_output

        result = assemble_consensus_output(
            args.input,
            args.consensus,
            args.holdout_labels,
            args.output,
            args.report,
        )
    elif args.command == "assertion-preserve":
        from .reconcile import preserve_qwen_with_current_assertions

        result = preserve_qwen_with_current_assertions(
            args.input,
            args.source,
            args.output,
            args.report,
        )
    elif args.command == "prepare-icd-aliases":
        from .icd_linker import prepare_icd_aliases

        result = prepare_icd_aliases(
            args.source,
            args.output,
            args.model,
            args.batch_size,
            args.min_confidence,
        )
    elif args.command == "v5-reconcile":
        from .icd_linker import reconcile_v5

        result = reconcile_v5(
            args.input,
            args.source,
            args.aliases,
            args.output,
            args.report,
            enable_icd=not args.no_icd,
        )
    elif args.command == "format-btc":
        from .serialization import format_directory_btc

        result = format_directory_btc(
            args.input,
            args.source,
            args.output,
        )
    elif args.command == "vietmed-infer":
        from .vietmed_detector import infer_vietmed_directory

        result = infer_vietmed_directory(
            args.input,
            args.output,
            args.report,
            args.model,
            None if args.no_reference else args.reference,
            args.batch_size,
            args.min_confidence,
            args.device,
            args.proposal_dir,
        )
    elif args.command == "proposal-infer":
        from .proposal_infer import infer_checkpoint_proposals

        result = infer_checkpoint_proposals(
            args.input,
            args.proposal_dir,
            args.checkpoint,
            args.report,
            source=args.source,
            device=args.device,
            max_length=args.max_length,
            stride=args.stride,
        )
    elif args.command == "v6-rebuild":
        from .v6_rebuild import rebuild_v6

        result = rebuild_v6(
            args.input,
            args.source,
            args.output,
            args.report,
            args.structural_cleanup,
        )
    elif args.command == "qwen-critic":
        from .qwen_critic import review_directory

        result = review_directory(
            args.input,
            args.source,
            args.output,
            args.report,
            args.model,
            set(args.records.split(",")) if args.records else None,
        )
    elif args.command == "ablation":
        from .ablation import run_ablation

        result = run_ablation(
            args.input,
            args.source,
            args.output,
            args.mode,
            args.report,
        )
    elif args.command == "specialist-hybrid":
        from .hybrid import build_specialist_hybrid

        result = build_specialist_hybrid(
            args.input,
            args.learned,
            args.legacy,
            args.output,
            args.report,
        )
    elif args.command == "teacher-student-ensemble":
        from .ensemble import build_teacher_student_ensemble

        result = build_teacher_student_ensemble(
            args.input,
            args.student,
            args.baseline,
            args.teacher_checkpoint,
            args.output,
            args.report,
        )
    elif args.command == "position-project":
        from .coordinates import project_directory_to_crlf

        result = project_directory_to_crlf(
            args.input,
            args.source,
            args.output,
            args.report,
        )
    elif args.command == "evidence-rebuild":
        from .evidence_rebuild import rebuild_with_evidence

        result = rebuild_with_evidence(
            args.input,
            args.source,
            args.output,
            args.report,
            refresh_assertions=args.all_evidence or args.refresh_assertions,
            refresh_rxnorm=args.all_evidence or args.refresh_rxnorm,
            split_labs=args.all_evidence or args.split_numeric_labs,
            position_mode=args.position_mode,
        )
    elif args.command == "annotate":
        command = [
            sys.executable, "-m", "streamlit", "run",
            str(Path(__file__).with_name("annotation_app.py")),
            "--",
            "--input", args.input, "--pred", args.pred, "--out", args.out,
        ]
        if args.records:
            command.extend(["--records", args.records])
        if args.manifest:
            command.extend(["--manifest", args.manifest, "--split", args.split])
        raise SystemExit(subprocess.call(command))
    elif args.command == "blind-prepare":
        from .blind_eval import build_calibration_manifest

        result = build_calibration_manifest(
            args.input,
            args.manifest,
            queue_size=args.queue_size,
            holdout_size=args.holdout_size,
        )
    elif args.command == "blind-evaluate":
        from .blind_eval import evaluate_blind_challenger

        result = evaluate_blind_challenger(
            input_dir=args.input,
            manifest_path=args.manifest,
            labels_path=args.labels,
            baseline_dir=args.baseline,
            challenger_dir=args.challenger,
            split=args.split,
            output_path=args.report,
            bootstrap_iterations=args.bootstrap_iterations,
        )
    elif args.command == "train":
        from .train import train_model

        labels = Path(args.labels)
        if not labels.exists():
            print(f"Labels not found: {labels}. Run `python -m airace annotate` first.", file=sys.stderr)
            raise SystemExit(2)
        result = train_model(
            args.labels,
            args.output,
            args.base_model,
            args.epochs,
            args.max_length,
            args.learning_rate,
            args.stride,
            args.validation_ratio,
            args.batch_size,
            args.gradient_accumulation,
            validation_path=args.validation_labels,
            class_weighting=args.class_weighting,
        )
    elif args.command == "prepare-vietbioner-transfer":
        from .vietbioner import prepare_vietbioner_transfer

        result = prepare_vietbioner_transfer(args.source, args.output)
    elif args.command == "evaluate":
        result = evaluate_dirs(args.gold, args.pred)
    elif args.command == "review-evaluate":
        from .review import evaluate_reviewed

        result = evaluate_reviewed(args.labels, args.pred)
    elif args.command == "package":
        result = package_output(
            args.output,
            args.zip_path,
            args.input,
            position_mode=args.position_mode,
        )
    elif args.command == "validate":
        result = validate_output_dir(
            args.input,
            args.output,
            position_mode=args.position_mode,
        )
    elif args.command == "audit":
        result = build_audit(args.baseline, args.precision, args.recall, args.report)
    elif args.command == "turn2-candidate-review":
        from .turn2_llm_rebuild import build_candidate_review

        result = build_candidate_review(
            args.input, args.source, args.output, args.model, args.batch_size
        )
    elif args.command == "turn2-rebuild":
        from .turn2_llm_rebuild import rebuild_turn2

        result = rebuild_turn2(
            args.input,
            args.source,
            args.proposals,
            args.candidate_review,
            args.output,
            args.report,
        )
    elif args.command == "turn2-ensemble":
        from .turn2_ensemble import build_turn2_ensemble

        result = build_turn2_ensemble(
            args.input,
            args.source,
            args.proposals,
            args.output,
            args.report,
            min_sources=args.min_sources,
        )
    elif args.command == "turn2-pair-review":
        from .turn2_pair_review import review_pair_rows

        result = review_pair_rows(
            args.input,
            args.source,
            args.proposals,
            args.output,
            model=args.model,
            batch_size=args.batch_size,
        )
    elif args.command == "turn2-pair-merge":
        from .turn2_pair_review import merge_pair_review

        result = merge_pair_review(
            args.input,
            args.source,
            args.review,
            args.output,
            args.report,
        )
    elif args.command == "turn2-who-icd-review":
        from .who_icd_rebuild import build_who_icd_review

        result = build_who_icd_review(
            args.input,
            args.source,
            args.output,
            model=args.model,
            batch_size=args.batch_size,
        )
    elif args.command == "turn2-who-icd-merge":
        from .who_icd_rebuild import merge_who_icd_review

        result = merge_who_icd_review(
            args.input,
            args.source,
            args.review,
            args.output,
            args.report,
        )
    else:
        raise SystemExit(2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
