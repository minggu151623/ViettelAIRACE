# Source-corpus provenance assessment

## Evidence supporting an i2b2-family hypothesis

The official 2010 i2b2/VA challenge describes exactly three concept families:
medical problems, tests, and treatments, with assertions on problems. Its records are
semi-structured discharge summaries/progress notes from Partners HealthCare, Beth Israel
Deaconess/MIMIC II, and UPMC. The challenge data were manually annotated for concepts,
assertions, and relations.

The BTC schema resembles a narrower adaptation:

- problem -> `CHẨN_ĐOÁN` / `TRIỆU_CHỨNG`;
- test -> `TÊN_XÉT_NGHIỆM` / `KẾT_QUẢ_XÉT_NGHIỆM`;
- treatment -> mostly `THUỐC`;
- absent / other experiencer -> `isNegated` / `isFamily`;
- BTC adds a separate historical dimension and multilabel assertions.

The public BTC inputs also share a generated three-section template and retain English
clinical fragments, which is compatible with translation/restructuring of an English
clinical corpus.

## Evidence that is still missing

No exact BTC record has been aligned to an i2b2 source record. Searches using distinctive
back-translated phrases did not recover an indexed source. The original i2b2 corpus is
access-controlled through the n2c2/DBMI Data Portal under a Data Use Agreement; it is not
appropriate to treat unofficial mirrors as an auditable competition resource.

Therefore:

- **supported:** shared task-family and annotation-policy resemblance;
- **plausible:** translated/restructured English source records;
- **unproven:** the named source is i2b2 2010, MIMIC II, or UPMC;
- **not authorized:** mechanical source-label transfer without exact licensed alignment.

## Sources

- [2010 i2b2/VA challenge page](https://www.i2b2.org/NLP/Relations/)
- [i2b2/n2c2 dataset access page](https://www.i2b2.org/NLP/DataSets/Download.php)
- [2010 i2b2/VA challenge paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC3168320/)
