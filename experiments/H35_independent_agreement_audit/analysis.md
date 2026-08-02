# H35 — Independent agreement audit

Among 1,778 frozen H34 OOF predictions, 316 are absent from H23. Exact agreement
finds 45 novel spans supported by the independent VietMed model and eight
supported by H26 phrase policy on records excluded from phrase construction.
Two spans have both sources; the union contains 51 rows.

The queue is clinically promising (`khó thở`, `đái tháo đường`, `viêm xoang`,
`buồn nôn`, `nhiễm trùng máu`) but not automatically clean. It contains both
registered fused-token hazards: `doxycyclinebactrim` and
`klonopinclonidine`. Agreement therefore raises confidence but is not a complete
boundary/type decision rule.

The next experiment should freeze this queue, add deterministic H23-present
positive controls, and require two independent semantic/boundary reviews. No
merge, ZIP or submission was created.
