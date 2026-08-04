# H72 result: technical pass, semantic type-coverage reject

H72 produced the registered large intervention: 542 span/type symmetric
differences across 75 records, with all 48 H69 brand rows preserved, 100/100
schema validation and deterministic packaging.

The mandatory post-build semantic audit rejects the artifact before user
submission. The canonical views removed 57 `KẾT_QUẢ_XÉT_NGHIỆM` entities and
added none, including long, clinically meaningful imaging and pathology
findings. This is not evidence that those findings are false positives; it
shows that the five proposal views have asymmetric type coverage. Applying a
missing-vote rule to unsupported types would mistake model incapability for
negative annotation evidence.

The H72 ZIP is quarantined and must not be submitted. H73 will preregister a
new type-routed hypothesis: use the repeated-passage canonical only for
`CHẨN_ĐOÁN` and `TRIỆU_CHỨNG`, the two types with genuine multi-view support,
and keep tests, results, drugs and every candidate exactly equal to H69.
