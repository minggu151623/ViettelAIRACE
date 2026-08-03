# H60 result: technical pass, semantic audit reject

H60 deterministically resegmented 162 existing H38 rows across 61 records,
split evenly between diagnosis and symptom. All structural gates passed and the
repeat ZIP hash is
`a7f6fbe3d464ca61037d0b1f20f6ceb10a054693ac1e951ec490a2cc53fa0cf6`.

The preregistered protocol deliberately delayed text review until after the
aggregate selection rule was frozen. That review exposed severe cross-domain
fragmentation: 45 new spans contain one whitespace token, 85 are shorter than
half the old span, 33 contain at most three characters, and the median
new/old character ratio is 0.4667. Examples include complete clinical phrases
being reduced to `Đái`, `Lú`, `Tê`, `buồn`, or `đau`.

These are direct semantic defects, not uncertainty about hidden ground truth.
H60 is therefore quarantined and must not consume a submission slot. Its ZIP
is retained locally only for reproducibility and is ignored by Git.

The failure identifies a concrete domain-shift target: source supervision is
strong, but the source-trained BIO decoder does not preserve multiword clinical
heads in Turn2. H61 will test task-adaptive masked-language pretraining on the
unlabelled Turn2 input before the same source fine-tuning. H61 is a new model
training intervention, not a post-hoc filter over H60 rows.
