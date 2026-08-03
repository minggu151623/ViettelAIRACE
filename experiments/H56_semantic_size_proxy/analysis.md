# H56 analysis — archive size is a confounded recall proxy

Across nine externally scored Turn-2 artifacts, ZIP size and score have a high
Pearson correlation (`0.9817`). That does not make ZIP bytes a valid objective:
the runs were produced sequentially, and later systems generally contain more
correct entities and assertions.

Entity count (`0.9895`) and assertion count (`0.9912`) correlate at least as
strongly with score. The causal interpretation is therefore semantic coverage,
not archive size. Two external counterexamples reject size as a selector:

- V2 is 4,827 ZIP bytes smaller than the original baseline but scores 2.4036
  points higher.
- H44 keeps the same 3,226 entities and 795 assertion labels as H38, adds 611
  candidate values, and loses 3.8174 points. Its candidate Jaccard falls by
  9.5437 while WER and assertion Jaccard remain exactly invariant.

Serialization further confounds the observation: canonical minified JSON for
H44 is larger than H38, although the packaged ZIP is smaller because formatting
and repeated parent codes compress differently.

Decision: use entity/assertion coverage only as a recall diagnostic. Never pad
JSON, change indentation, duplicate entities, or extend candidate lists to
increase bytes. The next challenger must freeze H38 candidate policy and earn
additional size through independently supported span/type/assertion rows.
