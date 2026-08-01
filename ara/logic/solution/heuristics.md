# Heuristics

## H01: Recognize standard checkpoint artifacts
- **Rationale**: Hugging Face `save_pretrained` normally writes `model.safetensors` or `pytorch_model.bin`, not the legacy `heads.pt`.
- **Provenance**: ai-suggested
- **Sensitivity**: low
- **Code ref**: [`airace/inference.py`]

## H02: Recover raw word boundaries at sliding-window edges
- **Rationale**: Token offsets at overflow boundaries can expose fragments such as `G` / `ãy`; expanding alphanumeric edges restores valid raw-word spans.
- **Provenance**: ai-suggested
- **Sensitivity**: medium
- **Code ref**: [`airace/train.py`]

## H03: Gate recall additions by two-model agreement
- **Rationale**: Raw learned union added more than 600 spans; requiring teacher confidence, student overlap, and no V6 overlap reduces this to 169.
- **Provenance**: ai-suggested
- **Sensitivity**: high
- **Code ref**: [`airace/ensemble.py`]

## H04: Make ZIP metadata deterministic
- **Rationale**: Fixed timestamps and permissions produce byte-identical archives from identical JSON files.
- **Provenance**: ai-suggested
- **Sensitivity**: low
- **Code ref**: [`airace/package_output.py`]

## H05: Promote numeric lab pairs only through existing compound results
- **Rationale**: Numeric adjacency alone produced treatment/vital-sign hazards.
  Requiring an existing result span to cover both a supported name and value
  bounds the rewrite to the previously audited 23 compound rows.
- **Provenance**: ai-suggested
- **Sensitivity**: medium
- **Code ref**: [`airace/evidence_rebuild.py`, `airace/lab_splitter.py`]

## H06: Make ontology review authoritative and family-consistent
- **Rationale**: Preserving old candidates after rejection defeats semantic
  review, while alphabetical selection can join unrelated ICD families. Select
  only reviewed/curated WHO codes and allow parent+child only within one family.
- **Provenance**: ai-suggested
- **Sensitivity**: high
- **Code ref**: [`airace/who_icd_rebuild.py`]

## H07: Separate categorical adjudication from copied confidence
- **Rationale**: H20's Qwen response copied proposal confidence. Use categorical
  KEEP/DROP only where its behavior is coherent, and route medication spans to
  exact supervised-model agreement plus deterministic boundary filters.
- **Provenance**: ai-suggested
- **Sensitivity**: high
- **Code ref**: [`airace/turn2_expanded_pair.py`]

## H08: Select calibration records without prediction access
- **Rationale**: Stratifying raw records by length and ranking them with a
  seeded hash prevents model errors or H20 coverage from influencing queue
  membership. Corpus and record fingerprints make later input drift visible.
- **Provenance**: ai-suggested
- **Sensitivity**: medium
- **Code ref**: [`airace/blind_eval.py`,
  `experiments/H21_blind_promotion_gate/calibration_manifest.json`]

## H09: Fail closed when stripping calibration sentinels
- **Rationale**: Synthetic unmatched rows are identifiable by impossible
  offsets and literal sentinel text, but a malformed real annotation must not
  be silently discarded by the same filter. Drop only explicit sentinels and
  abort on every other invalid row.
- **Provenance**: ai-suggested
- **Sensitivity**: low
- **Code ref**: [`airace/pseudo_reconstruct.py`,
  `tests/test_pseudo_reconstruct.py`]
