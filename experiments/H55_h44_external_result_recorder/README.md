# H55 — H44 external-result recorder

H55 prevents manual reinterpretation or transcription errors when H44 returns
from the leaderboard. It does not contain an external result.

After verifying that the submitted archive SHA-256 is
`5e451dd4f728ee2acecad80e364b5f750f11064941d1055031e7653aed3c83ba`, run:

```bash
python -m airace.h44_result_recorder \
  --decision-tree experiments/H44_full_who_family_hedge/external_decision_tree.yaml \
  --h44-zip turn2/output_v12_full_who_family_hedge.zip \
  --submitted-zip-sha256 5e451dd4f728ee2acecad80e364b5f750f11064941d1055031e7653aed3c83ba \
  --score SCORE --wer-percent WER --j-assertion J_ASSERTION \
  --j-candidates J_CANDIDATES \
  --output experiments/H44_full_who_family_hedge/external_result.json
```

The command writes only when identity, finiteness, candidate-only invariants,
score reconciliation and branch coverage all pass. On failure it exits without
creating the output. `result_input_template.json` lists the five values that
must be transcribed from the actual submission result.
