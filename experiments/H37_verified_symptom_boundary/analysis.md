# H37 verified symptom boundary integration — result

Status: **passed; candidate artifact created, not submitted**.

The frozen policy applied 26 of 29 H36-accepted symptoms across 17 records. It
replaced 21 over-extended H23 symptom rows with 22 independently supported core
spans and added four disjoint symptoms. The three exact-span type conflicts
(`bại não`, `sâu răng`, `Mất ngủ`) were skipped without changing H23.

The boundary replacements remove 475 characters of old mention text and emit
161 characters of verified core mention text, a net removal of 314 modifier or
compound-boundary characters. This is not used as a score proxy; it is an audit
of the transformation's direction.

Every unaffected H23 entity remains dictionary-identical. Replacement
assertions are inherited from the corresponding H23 concept; disjoint rows use
the unchanged rule engine. Symptoms contain no candidates. All 100 records pass
schema and raw-offset validation, 108 tests pass, and two independent builds
produce the same ZIP SHA-256:

`032041a8f92bc97ca6a92d4cb4809d6aa39122471056df97bfe1fd1fe4585abc`

Artifact: `turn2/output_v9_verified_symptoms.zip`.
