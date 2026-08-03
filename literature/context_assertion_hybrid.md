# ConText prior for H62

Primary source: Harkema et al., *ConText: An Algorithm for Determining
Negation, Experiencer, and Temporal Status from Clinical Reports*, Journal of
Biomedical Informatics 42(5), 2009.

The paper supports four design choices used in H62: assertions are properties
of already indexed clinical concepts; default assertion values change under
contextual evidence; trigger scope must stop at termination cues and account
for pseudo-triggers; portability varies by report type. It also reports that
historical status requires knowledge beyond surface clues, motivating an LLM
critic rather than another wider regular-expression window.

The paper does not validate Vietnamese prompts, the organizer ontology, Qwen,
or H62's hidden-test performance. Those remain empirical risks.
