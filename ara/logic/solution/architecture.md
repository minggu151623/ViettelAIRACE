# Architecture

V16 retains V6 as the precision anchor for existing entities, assertions, and
RxNorm. A class-balanced BamiBERT student proposes spans. The original medical
NER checkpoint acts as an independent label-space teacher. Only high-confidence
same-type overlaps are added, and additions may not overlap V6. Diagnosis ICD
candidates remain empty because prior external evidence showed candidate
stripping improved the score.
