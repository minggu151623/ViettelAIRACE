# H23 candidate-only semantic ablation

## Status

Preregistered before enumerating eligible candidate changes or building an
artifact.

## Frozen baseline

`turn2/output_v7_pseudo_reconstruction.zip`, externally scored 38.7976 with
WER 57.2161, assertion Jaccard 47.5455, and candidate Jaccard 29.2469.

## Hypothesis

H22's reconstructed spans and assertions are externally productive, but its
candidate mappings remain partly unverified. A candidate-only semantic layer
can improve candidate Jaccard without risking the confirmed text or assertion
components.

## Frozen invariants

For every entity and record, H23 must preserve H22's:

- entity count and ordering;
- `text`, `type`, `position`, and `assertions` fields byte-for-byte as JSON
  values;
- candidates on types other than `CHẨN_ĐOÁN` and `THUỐC`;
- 100-record file set and raw LF coordinate mode.

## Eligible diagnosis changes

1. Keep every existing exact WHO ICD-10 2019 code.
2. An ICD-10-CM-specific code may gain its valid WHO three-character parent
   only when both share the same first three characters. Do not replace or join
   unrelated families.
3. A specific WHO code may gain its valid three-character parent, producing at
   most `[parent, specific]`, because organizer evidence permits parent plus
   specific candidates.
4. Empty diagnoses may be filled only by an exact, already-audited H19 alias.
5. Never create more than two diagnosis candidates.

The audit must report parent additions separately from replacements. Existing
specific codes are not removed merely because they are ICD-10-CM; the external
H22 result shows that blanket WHO conversion is unsafe.

## Eligible drug changes

1. Keep an existing RxCUI when it is present in the fixed CPC catalogue and its
   term supports the mention's ingredient.
2. Remove an absent or ingredient-contradictory RxCUI unless an exact local
   resolver result proves all explicitly stated ingredient, strength and route
   attributes.
3. A bare generic ingredient may map to its exact IN/PIN/MIN concept; a bare
   brand may keep its exact BN concept.
4. Strength/form/product candidates require exact expressed-attribute support.
5. Emit at most one RxCUI per drug mention.

## Evaluation and promotion gate

The H22 pseudo scorer is prohibited as an optimization objective because its
real rows contain H22's current candidates. It may be run only as a documented
anti-overfit diagnostic after the H23 selection is frozen.

H23 becomes eligible for one external submission only if:

- every non-candidate field is exactly invariant;
- 100/100 files validate and repeated ZIP hashes match;
- every new code exists in the frozen WHO/RxNorm resource;
- every changed row has a machine-readable reason and evidence tier;
- there are at least 20 independently justified changed rows, so the expected
  effect is larger than display noise;
- manual spot review finds zero ingredient/family contradictions.

Failure of any condition preserves H22 and consumes no submission slot.

## Frozen build result

- Added a same-family WHO parent to 144 singleton ICD-10-CM-specific diagnosis
  rows covering 68 unique code/parent pairs.
- Quarantined one two-family row (`F19.10`, `F11.10`) because adding both
  parents would violate the two-candidate maximum.
- Left 745 already-valid WHO-specific candidate uses, 12 codes without a valid
  same-family WHO parent, and every drug candidate unchanged.
- Preserved all 3,168 entities and every frozen field exactly.
- Passed 65 tests and raw-offset validation on 100/100 records.
- Repeated ZIP SHA-256:
  `e1fc83b8e53cd9d4ac3f5d7f072a4f34eb46ee7841243a52f690ae8645514662`.

The prohibited optimization proxy decreases from 87.0650 to 84.5409 because
its real rows define H22's original candidates as truth. This expected
in-sample penalty is recorded but was not used for selection. H23 cleared the
frozen semantic/technical gate and received one external candidate-only
measurement. The score improved from 38.7976 to 38.9352 while WER (57.2161)
and assertion Jaccard (47.5455) stayed exactly frozen; candidate Jaccard
improved from 29.2469 to 29.5910. The weighted candidate delta
`0.4 * (29.5910 - 29.2469) = 0.13764` fully explains the displayed +0.1376.
H23 is promoted, but its small effect closes the parent-expansion axis.
