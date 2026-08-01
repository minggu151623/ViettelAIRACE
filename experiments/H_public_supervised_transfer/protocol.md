# H6 — licensed VietBioNER diagnostic-procedure transfer

## Status

COMPLETED AND REJECTED FOR INFERENCE; see `analysis.md`.

## Source and license

The official VietBioNER repository is pinned under `external/VietBioNER` at
commit `19ba70a5947d1be72906d407c860b1666b9337e9`. Its README grants CC BY 4.0;
local checksums are recorded in `external/VietBioNER_PROVENANCE.md`.

## Safe label mapping

Only source `DiagnosticProcedure` is mapped to BTC `TÊN_XÉT_NGHIỆM`.
`Symptom_and_Disease`, `Location`, `DateTime`, and `Organisation` are excluded.
In particular, the combined disease/symptom label must not be converted to either
BTC `CHẨN_ĐOÁN` or `TRIỆU_CHỨNG`.

## Prepared corpus

`data/vietbioner_transfer/` contains deterministic JSONL conversion:

- train: 706 sentences / 191 retained entities;
- validation: 300 / 89;
- test: 700 / 202.

## Next experiment

The source-only checkpoint reached F1 0.462745 with precision 0.355422, so it is
not promoted to a proposal source. Any future aligned model must pass source
validation and independently reviewed BTC precision checks before integration.
