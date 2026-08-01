# H8 — Audit RxNorm semantic consistency before changing candidates

## Hypothesis

The low candidate score is partly caused by the resolver selecting the
numerically first RxCUI for an ingredient/strength key, even when that concept
adds ingredients, changes route, or changes strength.

## Locked audit

1. Check every unique V6 RxCUI against NLM `historystatus`.
2. Compare mention evidence (ingredient, strength, route) against the official
   RxNorm concept name.
3. Preserve all exact mappings demonstrated in the organizer PDF.
4. Do not generate a submission until the CRLF position experiment is measured.

## Prediction

All-or-most codes may be active, but a non-trivial subset will be semantically
over-specific or contradictory. If confirmed, ranking must prefer concepts
with no unsupported ingredient and matching strength/route over numeric ID
order.
