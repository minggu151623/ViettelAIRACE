# H27 — Dual-prompt phrase context verifier

## Outcome

H27 failed its preregistered development gate, so test review was canceled and
no submission artifact was created.

The unanimous semantic/boundary verifier retained 35 of 43 H23-present phrase
additions (81.40%) and raised the simulated strict span/type F1 from 52.14% to
56.19% (+4.06 points). It also removed the registered fused-token hazard
`klonopinclonidine`. However, pseudo precision increased only from 50.59% to
61.40%, a gain of 10.82 points rather than the required 15 points.

## Interpretation

H23 absence is not a clean negative label. Several accepted H23-absent rows are
plausible clinical mentions, including explicit falls, seizures, pneumonia,
CT imaging, hypoxia and bleeding. The observed 61.40% is therefore a lower-bound
diagnostic rather than organizer precision.

The remaining errors expose a structural limitation in KEEP/DROP verification:
the verifier cannot repair an incomplete candidate. Examples include `Phù` in
`Phù gai thị`, generic `Đau` adjacent to a modifier, and the heading `Dị ứng`
without its specific object. Conversely, it rejected some H23-present generic
mentions such as `Mạch`, `ngã`, `đau`, `sốt` and `ý định tự tử`.

## Decision

- Reject H27 under its frozen gates.
- Do not inspect the H27 test split and do not create a ZIP.
- Retain the dual-prompt decisions as error-analysis evidence only.
- The next experiment must evaluate constrained boundary completion on
  synthetic corruptions and unchanged controls before applying it to unseen
  phrase proposals.
