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

## External result

The user submitted the exact artifact and reported 38.9720 versus H23's
38.9352. WER improved from 57.2161 to 56.9633, assertion Jaccard declined from
47.5455 to 47.4154, and candidate Jaccard remained 29.5910. The net gain is
only 0.0368. H37 supports shorter symptom cores weakly, but closes micro-queue
integration as a path to a leaderboard-scale improvement.
