# H7 — Reconstruct organizer CRLF position coordinates

## Status

Protocol locked before implementation.

## Observation

The organizer example is a flattened numbered list. Its published offsets do
not match the flattened text, but every offset is reproduced exactly by keeping
the visible space before each numbered item and inserting `\r\n` before that
item:

- flattened `amlodipine` start: 56; published start: 58;
- the discrepancy increases by exactly 2 for every numbered item;
- flattened final end: 532; published final end: 554;
- eleven inserted CRLF pairs add exactly 22 characters.

The 100 distributed files contain LF (`\n`) only. If gold annotations were
created on Windows-style CRLF text and the archive later normalized files to
LF, every entity after the first newline has a shifted position.

The organizer forum states that `position` was designed so the scoring formula
can find a concept if it exists, but does not disclose the matching algorithm.
The observed V6 component scores around 2–3% are consistent with systematic
entity matching failure.

## Hypothesis

Projecting every V6 `[start,end)` from LF coordinates into CRLF coordinates,

`offset_crlf = offset_lf + count("\\n" before offset_lf)`,

will materially improve entity matching if the hidden annotations retained
Windows CRLF coordinates.

## Controlled variables

- Exact V6 source entities.
- Identical file set and entity ordering.
- Identical `text`, `type`, `assertions`, and `candidates`.
- Only the two integers in `position` change.
- Deterministic BTC-style serialization and deterministic ZIP metadata.

## Decision rule

- Confirmed if the external score materially exceeds V6 `1.7280`.
- Refuted if it falls below V6.
- Position-insensitive if all component metrics remain identical within
  display precision.

No other model, span, assertion, or candidate change may enter this artifact.
