# Official Viettel AI Race forum evidence

Collected from the public forum API on 2026-07-27. Only comments authored by
`Admin AI RACE` or `AI Race Administrator` are treated as organizer evidence.

## Confirmed annotation policy

- A test name does not have to have a test result.
- A test result does not have to be numeric.
- The task does not require linking a test name to its result.
- Symptoms do not require subtype classification.
- Every occurrence of a repeated symptom is a separate concept.
- `assertions` is multilabel.
- Textual test values such as positive/negative are extracted; include the unit
  when the note provides it.
- A repeated concept at multiple positions must produce multiple JSON records.
- RxNorm uses a 2026 release; ICD-10 uses a Vietnamese edition.
- Public Vietnamese medical NER data may be used subject to its license and may
  have to be supplied to the organizer.

## Unspecified by design

The organizer explicitly declined to disclose exact position matching,
RxNorm fallback/TTY selection, combination-drug boundaries, and candidate
matching. The position response only says the field was designed so the
scoring formula can find a concept when it exists.

## RxNorm caveat

In the sample-data discussion, the organizer said a reported RxCUI had been
withdrawn and was no longer used, but the published examples themselves were
challenged by participants for containing retired mappings. Therefore sample
mappings are positive evidence for those exact strings, but they do not define
a reliable general fallback rule.

## API references

- `https://competition.viettel.vn/api/forum/posts/019f3337-5a5f-7435-b86c-34b3da200d11`
- `https://competition.viettel.vn/api/forum/posts/019f26d6-1cc1-745f-9d66-c5646bdbeba1`
- `https://competition.viettel.vn/api/forum/posts/019f2753-b5ba-7293-82f0-766f0d85dee9`
- `https://competition.viettel.vn/api/forum/posts/019f42d6-7bbd-7720-b585-ef341e88ddd2`
- `https://competition.viettel.vn/api/forum/posts/019f4256-a2aa-750c-8ec0-e5fd9ba80613`

## Completeness audit

On 2026-07-28, the public forum index was enumerated with `offset=0` and
`offset=100`, covering all 148 posts reported by the API at capture time.
Every commented post whose title/body mentioned Track 2, entities, assertions,
positions, tests, drugs, ICD, RxNorm, or candidates was inspected for comments
from `Admin AI RACE` or `AI Race Administrator`.

This exhaustive index pass found no newer organizer clarification beyond the
policy statements already recorded above. In particular, the organizer still
has not specified exact position matching, RxNorm TTY/fallback selection, or
candidate matching. This is absence-of-public-evidence at the capture time, not
proof that no unpublished convention exists.
