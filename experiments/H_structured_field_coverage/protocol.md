# H9 — Structured-field coverage audit

## Question

Is V6's near-zero official text score plausibly explained by globally poor
entity recall, or does it already cover the high-confidence semantic fields in
the organizer input?

## Method

For every non-empty colon-delimited field whose heading strongly implies a
target entity type, measure whether at least one V6 entity overlaps the field
value. Keep procedure-only and temporal descriptor fields out because they are
not competition entity types.

This is a coverage diagnostic, not gold evaluation: it cannot determine exact
boundaries, type correctness, or missing entities within a covered field.
