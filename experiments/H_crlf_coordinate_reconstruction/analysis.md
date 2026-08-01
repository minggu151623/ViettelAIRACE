# H7 analysis

## Local result

The exact V6 artifact was projected from LF coordinates to CRLF coordinates.
The transformation changed only `position`; a field-by-field comparison over
2,254 entities found zero changes to `text`, `type`, `assertions`, or
`candidates`. 2,246 entities moved, with endpoint shifts from 0 to 139
characters and median shift 17.

All 100 files pass the explicit CRLF validator. Two independent packaging runs
produce SHA-256
`88282fa37b3afb04320da1123995a505a44f6e120eb1c8c28733b262d271a04e`.

## Interpretation

This is a valid causal test of coordinate provenance. It is not evidence that
the semantic policy is correct, and it must not be combined with model or
candidate changes. The external leaderboard result is intentionally pending;
the user must decide whether to submit it.

## Additional quantitative consistency check

V6 contains 2,254 entities whose spans are valid substrings of the distributed
input, yet its official text score is only `100 - 99.9602 = 0.0398%`. A
text-first matcher would necessarily give substantial credit to obvious exact
drug and symptom mentions, so this near-zero value is evidence that matching
depends strongly on position.

The CRLF projection moves 2,246 of the 2,254 entities. The only eight unchanged
entities occur before the first LF in their records. This aligns the scope of
the suspected coordinate defect with the scope of the observed matching
failure. It strengthens H7 internally, while the leaderboard remains the
required causal measurement.

## Archive provenance

`zipinfo -v input.zip` reports `MS-DOS, OS/2 or NT FAT` as the source file
system for all 101 archive entries. Nevertheless, the 100 text members contain
2,889 LF bytes and zero CR bytes. Windows archive provenance alone does not
prove newline conversion, but together with the official example's exact CRLF
offset reconstruction it provides independent evidence that text may have been
normalized after annotation coordinates were created.

## Competing coordinate conventions eliminated

The Vietnamese prefix before the first official drug span makes the sample a
direct encoding test. Published `amlodipine` start is 58. The flattened text
gives Unicode/code-point 56; adding the first CRLF gives exactly 58. UTF-8 byte
coordinates would give 75 flattened or 77 with CRLF, so byte offsets are
decisively excluded. The official final end is likewise 554, exactly
`532 + 11*2`; UTF-8+CRLF would be 624.

All 100 distributed files are NFC, contain no astral Unicode characters, and
therefore have identical Python code-point and JavaScript UTF-16 coordinates.
They contain 2,889 LF bytes and zero CR bytes. This eliminates UTF-8 byte,
UTF-16-surrogate, and Unicode-normalization hypotheses: newline normalization
is the only evidence-supported coordinate discrepancy. Raw measurements are in
`coordinate_alternatives.json`.
