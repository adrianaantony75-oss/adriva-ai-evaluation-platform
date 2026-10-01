> Current implementation note (2026-10-01): ADRIVA-BENCH 0.1.0 is a 24-case synthetic draft spanning all six tasks. Deterministic checks do not validate free-text semantics. The SQL release gate now requires two distinct reviewer records; qualifications remain self-attested locally. See BENCHMARK-CARD.md and FINAL-DELIVERY.md. The v1 title below describes the inherited protocol, not a released benchmark.

# ADRIVA-BENCH v1 scientific protocol

Status: implementation protocol 1.0; candidate benchmark, NOT a validated population benchmark. No real model study or human response ratings have occurred. The accompanying synthetic cases are review-pending development material. This document extends the approved architecture; it does not replace it.

## Scientific audit before implementation

| Threat | Decision and implemented safeguard | Remaining limitation |
|---|---|---|
| Pseudoreplication | Pair identical case/repetition IDs; average repetitions, then cases within family, then families within source cluster; bootstrap clusters | Cluster membership must be reviewed; hidden common sources can still invalidate independence |
| Literal matching mistaken for meaning | Keep exact-match/literal checks diagnostic; require attributed proposition/claim judgments for semantic scores | No automatic free-text semantic oracle; native human review remains necessary |
| Malayalam reduced to translated English | Separate script, register, romanization and switching; review meaning and native phrasing separately | Synthetic authoring cannot certify native quality or dialect coverage |
| Unfair comparison | Require equal frozen benchmark, scoring protocol, generation protocol and planned grid | Equal token budgets can constrain languages differently; disclose tokenization/truncation and cost separately |
| Missing failures silently excluded | Incomplete planned pairs force HOLD; report observed and missing counts | Complete-case estimates remain descriptive and may be biased |
| Small/degenerate sample | Minimum independent clusters, nondegenerate interval and predeclared precision gate | Minimum count is an operational guard, not a power proof |
| Multiple testing | Bonferroni simultaneous primary intervals; Holm adjusted p-values; BY exploratory FDR under arbitrary dependence | Corrections cannot rescue biased sampling or invalid p-values |
| Nonsignificance called equality | Equivalence requires entire interval inside predeclared practical margin | Margins require domain justification before seeing results |
| Judge validity assumed | Blinded swap/repeat audits, canonical identity mapping, held-out human comparison | Consistency does not establish correctness; style can reveal model identity |
| Annotation subjectivity | Anchored dimensions, abstention, original independent ratings, disagreement review | Reviewer population and language competence limit generalization |
| Contamination/leakage | Cluster-level splits; reviewed duplicates; versioned sources; public candidates only in development | No claim that model training excluded public data |
| Correlation called causation | Observational evaluator agreement is descriptive; controlled transformations require verified invariants | Bundled language rewrites do not identify a causal language effect |

## Scope and release rules

The initial executable track covers grounded QA, typed extraction and translation. Summarization, instruction following and bounded reasoning have methodology and rubric coverage, but need separately reviewed cases before being advertised as benchmark coverage. Open-world factuality is not inferred from a fictional grounding passage.

Candidate generation is SYNTHETIC; derivation is a separate lineage event; HUMAN_VERIFIED may only be recorded after an actual qualified review. Candidate files use PILOT/development so they cannot masquerade as held-out evaluation. The v1 candidate number is not a frozen benchmark release. Publish only after two independent language-capable reviewers inspect source meaning, answerability, references, entity/quantity bindings, target register and every transformation; disagreement requires documented adjudication or quarantine. Reviews of benchmark cases are distinct from ratings of model responses.

Before a real study, expand independent families across task, domain and difficulty. Estimate variance and annotation cost on development/calibration; plan sample size from the desired confidence-interval width and decision margin using cluster-level simulation. Freeze the sampling frame, primary gates, exclusions, missingness policy, scorer versions, model configurations and analysis plan before collecting held-out results. Do not promote these public development cases to a secret test set by renaming them.

## Estimand and statistical decision

The implemented estimand is the equally weighted mean of dependency-cluster means, with equal family weights within cluster, case weights within family and repetition weights within case. It measures performance on this controlled suite; it is not traffic-weighted population performance. Report unaggregated task/language/operator slices too. Unequal naturalistic sampling requires a future weighted estimator.

Scores used in comparisons must lie in [0,1]. Direction is explicit: higher-is-better for correctness, lower-is-better for failure prevalence. The effect is candidate minus baseline, oriented so positive means improvement. Report raw scale and percentage points; no universal small/medium/large effect labels. Repeated generations are nested measurements, not independent cases.

Use paired cluster percentile bootstrap, seeded and versioned, normally 5,000 or more draws. Bonferroni tails use alpha/(2m) for m predeclared primary gates. The engine requires sufficient tail draws, >=30 clusters by default, complete planned pairs, reviewed evaluation evidence and a predeclared maximum interval width. These checks are deliberately conservative but do not guarantee nominal coverage. Constant observed differences return HOLD rather than a zero-width confidence claim. There is no invented bootstrap p-value.

Improved: lower interval bound exceeds +margin. Regressed: upper bound below -margin. Practically equivalent: entire interval strictly inside [-margin,+margin]. Otherwise inconclusive. Noninferiority is reported separately if lower bound exceeds -margin. All classifications are disabled on HOLD. A zero margin cannot establish practical equivalence. One-sided safety gates, heterogeneous cluster sizes and rare failures may need a separately reviewed analysis plan.

Exact McNemar/binomial inference is available ONLY for genuinely independent paired binary units, not rows of correlated variants. Holm handles a finite family of valid p-values; BY provides conservative exploratory FDR control. Never choose correction or scope after inspecting significance. Failure labels overlap; compare each label's paired response-level incidence, never a multinomial chi-square on overlapping counts. Robustness uses paired baseline/variant task-valid outcomes and conditional pass-to-fail transitions; identical wording is irrelevant.

## Alternatives and trade-offs

| Decision | Alternatives | Why selected | Trade-off |
|---|---|---|---|
| Evidence aggregation plus narrow deterministic checks | Embedding threshold, uncalibrated LLM verdict | Supports auditable uncertainty and Malayalam limitations | Many semantic outcomes remain review-pending |
| Dependency-cluster bootstrap | Row bootstrap, unpaired t-test, hierarchical model | Preserves pairing/dependency with interpretable suite-level effect | Few clusters and rare events limit inference; hierarchical model deferred |
| Anchored ordinal alpha | Pearson correlation, raw agreement alone | Supports multiple reviewers and missing ratings without assuming equal scale spacing | Alpha sensitive to prevalence and sparse overlap; report counts and raw agreement |
| Balanced blinded assignment | Fixed V1=A, arbitrary per-request shuffle | Auditable allocation, local balance, protected canonical mapping | Cannot fully hide model-specific style |
| Core standard-library math | New statistics/embedding services | Small auditable kernel, offline reproducibility, no new model dependency | Formula/reference tests needed; no claim of external statistical certification |

## Sources checked for method selection

- Ribeiro et al., CheckList: https://aclanthology.org/2020.acl-main.442/ — behavioral tests and transformation intent.
- Koehn, statistical significance for MT: https://aclanthology.org/W04-3250/ — paired resampling; ADRIVA adds source-cluster resampling for its dependency structure.
- Krippendorff, Computing Alpha Reliability: https://www.asc.upenn.edu/sites/default/files/2021-03/Computing%20Krippendorff%27s%20Alpha-Reliability.pdf — pairable coincidences, missingness, ordinal distances.
- Zheng et al., LLM-as-Judge: https://arxiv.org/abs/2306.05685 — bias motivates order, verbosity and self-preference audits; findings do not validate ADRIVA's judges.
- statsmodels multiple-testing API: https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html — correction families. ADRIVA implements Holm/BY directly and tests reference examples.

The protocol has received an internal methodological review in this implementation session, not independent peer review or native-speaker validation.
