# H21 operating guide

H21 is isolated from the frozen 29.8409 artifact. The calibration manifest was
selected from raw Turn 2 structure only and must not be regenerated after
annotation begins.

## 1. Annotate development from raw text

```bash
python -m airace annotate \
  --input turn2/input \
  --pred experiments/H21_blind_promotion_gate/no_predictions \
  --out experiments/H21_blind_promotion_gate/annotations/development.jsonl \
  --manifest experiments/H21_blind_promotion_gate/calibration_manifest.json \
  --split development
```

Development record IDs:

```text
13, 14, 21, 27, 40, 49, 53, 59, 76, 79, 88, 100
```

Annotate every occurrence. First fix exact text, type and `[start,end)`; then
assertions; finally independently defensible candidates. Do not open H20 or
proposal-bank JSON while performing the first pass.

If two reviewers are available, save independent files such as
`development_reviewer_a.jsonl` and `development_reviewer_b.jsonl`, then
adjudicate disagreements before producing `development.jsonl`.

## 2. Develop challengers without holdout

```bash
python -m airace blind-evaluate \
  --input turn2/input \
  --manifest experiments/H21_blind_promotion_gate/calibration_manifest.json \
  --labels experiments/H21_blind_promotion_gate/annotations/development.jsonl \
  --baseline turn2/output_v6_expanded_pair \
  --challenger PATH_TO_CHALLENGER \
  --split development \
  --report experiments/H21_blind_promotion_gate/reports/CHALLENGER-development.json
```

Development reports always return `DEVELOPMENT_ONLY`; they cannot promote a
submission. Freeze the challenger source, configuration and thresholds before
opening the holdout.

## 3. Annotate and evaluate holdout once

```bash
python -m airace annotate \
  --input turn2/input \
  --pred experiments/H21_blind_promotion_gate/no_predictions \
  --out experiments/H21_blind_promotion_gate/annotations/holdout.jsonl \
  --manifest experiments/H21_blind_promotion_gate/calibration_manifest.json \
  --split holdout

python -m airace blind-evaluate \
  --input turn2/input \
  --manifest experiments/H21_blind_promotion_gate/calibration_manifest.json \
  --labels experiments/H21_blind_promotion_gate/annotations/holdout.jsonl \
  --baseline turn2/output_v6_expanded_pair \
  --challenger PATH_TO_FROZEN_CHALLENGER \
  --split holdout \
  --report experiments/H21_blind_promotion_gate/reports/CHALLENGER-holdout.json
```

Holdout record IDs:

```text
7, 25, 47, 61, 71, 96
```

Only `PROMOTE` clears the local gate. `REJECT`, `INSUFFICIENT_EVIDENCE` and
`INCOMPLETE_ANNOTATIONS` all preserve H20 as the submission candidate.

## Integrity checks

- Corpus SHA-256: `c1eeb7a7fd8dbfb90ce820075ef9e78b08e1e7f774adba91b6a037b1742035fb`
- Manifest SHA-256: `37b0cb4beb5b1fd22e5539c364e7f84ac288cb4e4ee6c655919c0c5bb0908bc0`
- Seed: `298409`
- Queue: 18 records across six length strata
- H20 output directory: 100/100 valid

Never edit record IDs or split membership after reviewing predictions.

