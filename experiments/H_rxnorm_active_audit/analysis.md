# H8 audit result

The V6 artifact uses 79 unique RxCUIs across 162 drug entities. NLM's current
RxNorm history API reports all 79 as Active, so code retirement does not explain
the low external candidate score.

However, inspection found systematic semantic contradictions caused by the
resolver's arbitrary first-ID fallback:

| Mention evidence | Current RxCUI concept | Uses | Issue |
|---|---|---:|---|
| acetaminophen | acetaminophen/doxylamine/phenylephrine | 3 | unsupported extra ingredients |
| aspirin | acetaminophen/aspirin/caffeine product | 1 | unsupported extra ingredients |
| aspirin 325 mg | aspirin/citric acid/sodium bicarbonate product | 3 | unsupported extra ingredients |
| metoprolol | hydrochlorothiazide/metoprolol product | 2 | unsupported extra ingredient |
| metoprolol 25 mg | metoprolol succinate 50 mg ER tablet | 2 | strength/form conflict |
| IV Lasix 40 mg | furosemide 40 mg oral tablet | 2 | route conflict |
| bumetanide 2 mg IV | bumetanide 2 mg oral tablet | 1 | route conflict |
| levofloxacin 750 mg IV | levofloxacin 750 mg oral tablet | 1 | route conflict |

This accounts for at least 15 candidate-bearing entity uses with strong
contradictory evidence. NLM approximate matching independently returns active
ingredient/strength concepts such as acetaminophen `161`, aspirin `1191`,
metoprolol `6918`, furosemide `315971`, bumetanide `315502`, and levofloxacin
`330371`. The latter three are not themselves injection products; that
correction is detailed below.

## Bare-ingredient resolver repair (2026-07-28)

The failure was reproduced directly: the pre-repair resolver returned the
lexicographically first broad-product-index identifier for a bare generic
mention: `acetaminophen -> 1006887`, `aspirin -> 1052415`, and
`metoprolol -> 1162132`.  These are product/combination concepts rather than
the exact RxNorm ingredient concepts.

`CandidateResolver` now prefers the exact bundled CPC alias when the mention
has no supplied strength: an `IN`, `PIN`, `MIN`, or `BN` identifier is chosen
before the broad product index.  A focused regression locks the NLM-audited
ingredient cases to `161`, `1191`, and `6918`; all 40 project tests pass.
This changes only resolver behavior. It does **not** generate a JSON/ZIP,
does not claim organizer policy, and does not address the separately pending
route-aware brand cases (for example IV Lasix).

### Read-only V6 impact audit

The initial bare-alias audit changed 8/165 entities. After adding the
route-aware, relationship-backed resolver, the final read-only audit changes
12/165 entities across ten files: seven bare generic corrections, four explicit
IV corrections/abstentions, and one bare-brand `prograf` choice. The brand-level
choice is semantically defensible but not organizer-verified, so any future
candidate-only ablation must report it separately rather than bundling it with
the eleven non-brand rows. The audit is reproducible with
`code/audit_candidate_reresolution.py`; its report is stored in
`results/bare_alias_audit.json`. No submission JSON or ZIP was written.

### Route policy correction and deferral

The earlier audit used approximate-match results too loosely: `315971`
(furosemide 40 mg), `315502` (bumetanide 2 mg), and `330371` (levofloxacin
750 mg) are **SCDC** concepts—ingredient plus strength—not complete injection
products. RxNav's relationship endpoint does verify that the V6 codes for the
three IV mentions are oral tablets and exposes route-consistent alternatives:
furosemide injection `1719291`, bumetanide injection form `1727568`, and
levofloxacin injection `1665515`.

The official round-1 fixture gives a bounded policy signal: 10 of its 11 drug
candidates are **SCD** products, while the sole no-strength nystatin example
uses an IN. This does not make TTY universal, but it supports a conservative
rule: choose an SCD only when ingredient, total strength, and explicit route
all match; otherwise abstain rather than emit an oral product. The local CPC
catalog now retains RxNorm's direct brand-to-generic relationship, enabling
this general rule without per-record hard-coding. Regression cases select
furosemide 40 mg injection `1719291` and levofloxacin 750 mg injection
`1665515`, while bumetanide 2 mg IV abstains because no exact SCD package
matches. All 41 project tests pass. The official TTY audit and route evidence
are stored under `results/`.

Decision: H8 is now partially repaired and unit-tested.  No submission
artifact is generated before H7 is externally measured and a candidate-only
ablation is preregistered.
