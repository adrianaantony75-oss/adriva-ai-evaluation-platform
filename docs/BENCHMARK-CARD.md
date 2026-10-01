# ADRIVA-BENCH 0.1.0 — draft seed pack

Status: **PROTOTYPE / UNREVIEWED PILOT**. This is a small behavior-oriented seed pack, not a statistically representative benchmark.

| Property | Value |
|---|---|
| Cases | 24 |
| Intent families / dependency clusters | 6 / 6 |
| Language modes | English, Malayalam script, informal Manglish, Malayalam–English code-switch |
| Cases per mode | 6 |
| Tasks | Grounded QA, extraction, translation, summarization, instruction following, bounded reasoning |
| Cases per task | 4 |
| Base cases / derived variants | 6 / 18 |
| Split | Development only |
| Origin | AI-assisted synthetic authoring in this session |
| Native review | None |
| Genuine human response labels | None |
| External datasets | None copied or claimed |
| Version | 0.1.0; database scientific release remains DRAFT |

`tools/build_benchmark.py` is the reproducible source. Synthetic contexts are fictional; no private customer data was used. The generator build is explicitly unavailable. The per-case digest identifies the authored prompt text, not a recoverable upstream model-generation transcript. Generation metadata does not establish reproducible neural generation.

The four variants in a family share a source/task and cannot be treated as independent samples. Six clusters are below the implemented default minimum of 30; even 30 would not establish representativeness or adequate power. No deployment decision can be based on this pack.

Malayalam prompts and Manglish spellings need independent language-capable review for meaning, naturalness, register, reference adequacy and code-switch plausibility. The English-grounded contexts and parallel variants are a limitation: this is not a native Malayalam cultural or domain benchmark. There are no dialect coverage or linguistic quality claims.

Automatic coverage differs by task. Translation exact match is a narrow diagnostic; acceptable paraphrases may fail. Summary checks cover length and required literals only; preserving both day names does not prove the right temporal relationship. Structured field accuracy and schema validity are separate dimensions. Character limits count Unicode code points, not grapheme clusters or tokens.

The database requires two distinct reviewer records for content and for every derived transformation. Any REJECTED/REVIEW_REQUIRED record blocks release; fix by creating a new case revision. Local identities and qualifications are self-attested, so this is an engineering guard rather than proof of independent expert certification.

`benchmarks/fixtures/product-0.1.0.json` mirrors the pack as **ADRIVA-ENGINEERING 0.1.0**, explicitly FIXTURE. It supports full offline workflow tests. Its two constant-output configurations generate 48 engineering responses and deterministic constraint findings, never AI quality measurements. The inherited four-case `engineering-v1.json` remains a separate integration-test fixture.
