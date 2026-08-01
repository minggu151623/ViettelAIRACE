# H20 — Expanded learned-pair recall with Qwen adjudication

## Baseline

H19 candidate-only output. All H19 entities and fields are frozen.

## Hypothesis

The exact three-model core was externally positive, but it excluded the large
Bami-v15+Bami-v3 agreement bank and all pair-supported drugs. Two trained NER
models agreeing on an exact span/type provide a useful retrieval layer even
when their architectures are related. Qwen is used only as a bounded KEEP/DROP
adjudicator, never to invent text or offsets.

## Policy

- Retrieve exact two-model agreements with type/source-specific confidence
  floors fixed before review.
- Exclude every proposal overlapping an H19 entity; this experiment only adds
  disjoint mentions and cannot replace a known boundary.
- Qwen reviews each fixed span/type once at temperature zero. The frozen run
  showed that its numeric confidence copied the input model confidence and is
  therefore not calibrated. For diagnosis, symptom and test-name rows, use the
  categorical KEEP/DROP action. For drugs, use exact VietMed+Bami agreement;
  Qwen's drug decisions were inconsistent even for obvious names such as
  omeprazole and acetaminophen.
- A deterministic boundary sanitizer rejects known fused/truncated and generic
  rows before merge.
- Diagnose candidates use only H19's exact WHO table; drug candidates use the
  local RxNorm CPC resolver in strict-strength mode.
- Infer assertions with the frozen local scope engine.

No competition submission is performed by Codex.
