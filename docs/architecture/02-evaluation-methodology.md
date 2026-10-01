# ADRIVA: evaluation methodology

Protocol design 1.0 • No evaluation results exist yet. Source IDs resolve in 06-sources-and-verification.md.

## 9. ADRIVA-BENCH methodology

### Measurement contract

Every case defines task, input, relevant context, required output behavior, allowed alternatives, applicable metrics, reference/evidence, language requirements and severity policy. Benchmark items are measurements with limitations, not merely prompts. Do not score a property unless the case provides enough evidence to assess it.

Two tracks remain separate:

- **Controlled track:** curated behavior tests and related language variants. Supports diagnosis and comparisons on that suite; not population prevalence claims.
- **Naturalistic track:** rights-cleared prompts sampled from a declared source population, if later available. Publish sampling frame, dates and selection/exclusion process. Do not call synthetic prompts real user traffic.

Start with a proposed pilot of 60 independent intent families, 20 in each initial primary task. Aim for four core input modes per family, plus one reviewed single-factor perturbation: approximately 300 cases if all variants prove valid. This count is a workflow budget, not a power calculation or sufficient sample claim. Invalid variants reduce counts; do not fill quotas with unverified rewrites. Translation tracks must record direction and expected output mode; some comparisons require separate strata.

For the pilot, assign approximately 30 families to development, 15 to scorer/judge calibration and 15 to a locked smoke-evaluation split. The last split is far too small to promise precise release inference across all slices. Expand the independent evaluation families after variance and annotation-time estimates exist. A frozen pilot can demonstrate a rigorous workflow while returning INCONCLUSIVE.

### Case record and publication checks

Required: stable case ID, revision, family ID, dependency cluster ID, primary task, secondary capabilities, input/output language profiles, original prompt and context, source IDs, expected constraints, reference answers or explicit no-reference status, provenance lineage, author, license/permission, sensitivity, split, transformation record, review record and content hash.

Publish only after schema, required fields, UTF-8 integrity, duplicate and split-leakage checks pass. Human review must check the answer contract as well as the wording. Source-grounded tasks retain evidence snapshots and citations, including retrieval date where relevant. Use stable fictional scenarios for initial grounding; exclude current-world knowledge claims without dated evidence.

Review statuses: DRAFT → VALIDATED → REVIEW_REQUIRED → VERIFIED → FROZEN. REJECTED/QUARANTINED is an explicit branch, not a silently removed row. A valid mechanical transformation may be reviewed in a batch, but semantic intent must still be verified before it enters the trusted robustness track.

### Provenance is multidimensional

| Requested label | Representation | Meaning |
|---|---|---|
| HUMAN_CREATED | creation_origin | A person authored the case; assisted edits are disclosed |
| SYNTHETIC | creation_origin | A generator authored content; retain generator and prompt version |
| PUBLIC_DATASET | creation_origin | Imported dataset revision, item ID, source and license retained |
| TRANSFORMED | derivation event | Parent case, operator/version, parameters and creator retained |
| HUMAN_VERIFIED | review event/status | Named/pseudonymous real reviewer, rubric, time and outcome retained |

These are not five mutually exclusive origins. A SYNTHETIC case may be TRANSFORMED and then HUMAN_VERIFIED. It never becomes HUMAN_CREATED retrospectively. Human verification of a prompt is also different from human evaluation of a model response. FIXTURE is a separate usage class for engineering tests, excluded by default from all scientific aggregates.

### Leakage controls

Split by dependency cluster, not case row. Shared source passages, translations, close paraphrases and generated variants stay together. Establish clusters before splitting; perform exact hashes, normalized hashes and reviewed near-duplicate search across splits. If a source links multiple families, all share one cluster. Prompt tuning uses development only; thresholds and judge calibration use calibration only. Locked evaluation is not used to repair prompts repeatedly. New failure-derived cases enter a disclosed challenge release; they do not retroactively prove generalization.

Benchmark authors may know the public suite; that cannot be undone. A private split helps process discipline but does not prove provider training-data non-contamination. Record possible exposure and avoid claims of contamination-free evaluation.

## 10. Task taxonomy

One primary task per case avoids double counting; capability tags may overlap.

| Primary task | Required gold/evidence | Main outcomes | Limits |
|---|---|---|---|
| Grounded QA | Source passage, answerability, accepted answers, supporting spans | Answer correctness, abstention correctness, support, completeness | Groundedness does not guarantee real-world truth of the passage |
| Information extraction | Field schema, typed gold values, alias/normalization policy | Field exactness, precision/recall/F1, required-field and schema pass | Macro and micro summaries both needed; formatting and content separate |
| Translation | Source, target language/register, reviewed references and semantic units | Fidelity, omissions/additions, entities/numbers, naturalness | Reference overlap is not sufficient evidence of meaning preservation |
| Summarization | Source, key content units, length/task constraints | Supported claims, content coverage, constraints, human coherence | A short empty summary can avoid false claims while failing completeness |
| Instruction following | Explicit objectively checkable constraints plus rubric | Per-constraint pass and all-required pass | “Good answer” is not an executable constraint |
| Bounded reasoning | Solvable synthetic or reviewed problem, final answer, accepted verification | Answer/checker correctness; short verifiable rationale if requested | Do not infer internal reasoning from fluent explanation; no hidden chain-of-thought required |

Open-domain factual QA is deferred until source collection and evidence aging exist. Tools/code execution by evaluated models are out of scope for the initial release. Translation and summarization are evaluation tracks, not end-user translator products.

## 11. Language taxonomy and controlled robustness

Language, script, register, mixing and noise are separate axes. Store input profile and requested output profile independently.

| Axis | Initial values |
|---|---|
| Language composition | English; Malayalam; Malayalam+English; unknown |
| Script | Latin; Malayalam; mixed; other |
| Register | Formal; conversational; colloquial; unspecified |
| Mixing | None; lexical borrowing; within-sentence; between-sentence; ambiguous |
| Romanization | Not applicable; conventional scheme if specified; informal Manglish |
| Transformation | Translation; register shift; paraphrase; spelling noise; typing error; punctuation; code-switch; transliteration |
| Locale metadata | Kerala context when supplied; dialect/community only when known and consented, never inferred from identity |

Use `en`, `ml`, `ml-Latn` as applicable language/script tags. Represent code-switching as a composition of languages with optional spans; do not invent an ISO language code for “Manglish.” Romanized Malayalam and English mixed with Malayalam are not the same condition. Automatic language identification is an auxiliary flag, not ground truth for short or mixed text.

### Transformation contract

Each operator stores parent revision, seed/configuration, exact changed span, intended invariant, expected direction if any, severity and a verification result. Preserve task facts, negation, entities, units, quantities and constraints unless the experiment intentionally changes one. Single-factor tests precede combined stress tests. A punctuation deletion that changes sentence meaning is not an invariance test. An ambiguous typo must be quarantined or assigned a different answer contract.

Three test relationships, inspired by behavioral testing [S01]: minimum-capability tests, invariance tests and directional tests. Formal/conversational language may preserve factual intent while legitimately changing tone; score factual invariants and register expectations separately. English-to-Malayalam rewriting is not automatically semantically equivalent just because a model translated it.

For family f, baseline behavior score b_f and applicable variant scores v_fk, define D_f = mean_k(v_fk − b_f), using a frozen operator weighting scheme. Report mean D_f across families, with cluster-aware intervals. Also report:

- Variant pass rate among all eligible variants, macro-averaged by family.
- Baseline-pass → variant-fail transition rate, with its restricted denominator.
- Baseline-fail → variant-pass rate and unchanged fail rate.
- Fraction of families passing every required variant, only when required variant sets match.
- Worst-language or worst-operator slice with counts and uncertainty, not just the overall mean.

Conditioning on baseline passes answers a narrow question and can hide weak baseline performance; show the unconditional result beside it. For V2-versus-V1 robustness, compare family penalties: (variant−baseline)_V2 − (variant−baseline)_V1. Do not count each reused baseline as another independent observation. If variant sets differ, analyze a preregistered common subset and disclose exclusions.

## 12. Failure taxonomy

Multi-label findings; one outcome can have several supported labels. Severity is independent: MINOR (small usability impact), MAJOR (material task failure), CRITICAL (predeclared serious consequence). Criticality follows the scenario, not an automatic scary-word heuristic. Counts of labels must never be summed and presented as unique failed cases.

| Label | Operational definition and evidence |
|---|---|
| Meaning Drift | Response alters a required proposition, relation or intent; identify source and changed claim |
| Instruction Drift | Ignores or changes an explicit task constraint; link the constraint ID |
| Hallucination | Fabricated/unsupported asserted content under the task's evidence contract; link claim and unsupported/contradicted status |
| Factual Error | Claim contradicted by trusted reference evidence; absence of support alone is insufficient |
| Entity Preservation Failure | Required identity is lost, substituted or mislinked after allowed aliases/transliteration |
| Number Preservation Failure | Required quantity, date, unit or numeric relation changes outside allowed conversion/tolerance |
| Over-Literal Translation | Surface rendering distorts intended idiom or function; bilingual evidence required |
| Unnatural Language | Awkward usage for requested register despite understandable meaning; qualified language review |
| Grammar Error | Syntax/morphology violates target-language expectations; do not penalize permitted code-switch conventions |
| Code-Switch Failure | Mixing violates requested mode or loses meaning/coherence at switch boundaries |
| Transliteration Failure | Romanization changes identity/meaning or violates a required scheme; allow legitimate informal variants |
| Cultural Misinterpretation | Misreads a context-dependent convention or reference; record context and reviewer rationale |
| Omission | Missing required semantic unit or answer field |
| Unsupported Addition | Adds material absent from source/task permission; may be true yet inappropriate |
| Format Failure | Violates output schema or explicit structural requirement |
| Contradiction | Incompatible statements within response or with authoritative task context |
| Inappropriate Refusal | Declines an answerable allowed task without task-supported reason |

Hallucination is an umbrella finding, not a separate count to add to unsupported additions. Preserve subtype `unsupported`, `contradicted`, or `fabricated_evidence`; only evidence-backed claims receive confirmation. Store detector proposal separately from human confirmation. Execution timeout, truncation and provider refusal codes are operational events; a successful model refusal may additionally be a task failure if the rubric warrants it.

## 13. Automatic evaluation methodology

### Layers and applicability

1. Validate execution and payload status. A missing response has no language-quality score.
2. Deterministic constraints: parse schema, required fields, counts, exact accepted answers, numeric values/units and permitted entity aliases.
3. Reference-based diagnostics: chrF for translation when a reviewed target reference exists [S02]; optional lexical summaries for debugging, never universal quality gates.
4. Optional learned signals: multilingual embeddings for duplicate discovery/failure grouping; translation quality models only after checkpoint-specific language validation. COMET is an MT evaluation framework, not proof of validity for ADRIVA's Manglish slices [S03].
5. Validated judge or human assessment for semantics and naturalness. Until validated, automatic semantic findings remain provisional.

Metric result types: VALUE, NOT_APPLICABLE, INSUFFICIENT_EVIDENCE, SCORER_ERROR. Keep numeric nulls distinct from zero. Store metric revision, input hashes, normalizer version, direction, units, range, decision threshold if any and evidence. A metric returning an error is never silently omitted from its coverage denominator.

Unicode policy: preserve original text and derive a versioned normalized copy; start with NFC, but test Malayalam combining forms and chillu variants explicitly. Do not strip joiners, punctuation or case blindly. Numeric matching uses Decimal and explicit locale/unit rules; comparison of unordered digit bags is invalid. Entity matching uses reviewed aliases and relations, not only string presence. No universal edit-distance threshold for informal Manglish.

Extraction reports exact field accuracy and typed value correctness, with micro and per-case macro F1 where appropriate. QA separates answerable and unanswerable cases. Empty/no-answer outputs cannot pass all tasks by avoiding claims. Summarization reports claim support and required-content coverage together. Factuality requires a trusted evidence source; groundedness asks whether provided evidence supports the response. Neither an embedding cosine nor a fluent judge explanation establishes truth.

For claim-based diagnostics report unsupported evaluated claims / evaluated claims, plus claim-extraction coverage and unsupported-response incidence. A response with no extractable claims is N/A for claim precision and still assessed for answer completeness. Do not describe this as the true hallucination rate if claim extraction/judgment is incomplete or unvalidated.

Golden scorer tests must include semantically correct alternative wording, wrong negation with high lexical overlap, changed numbers, transliterated entity aliases, empty answers, malformed JSON, Unicode variants and unsupported statements. Label these engineering fixtures explicitly.

## 14. Human evaluation methodology

### Blind study design

Freeze study protocol, response set, rubric, eligibility and sampling before assignment. Use at least two independent qualified reviewers for the primary overlap set; prefer three on the calibration/disagreement subset when available. Human agreement is NOT ESTIMABLE with one reviewer, however often that person repeats a rating.

Reviewers qualify separately for Malayalam, English and mixed-script work using reviewed practice items and rubric discussion. Self-reported language fluency alone is not sufficient evidence of rating consistency. Avoid having case authors be the only reviewers of their own examples. Record conflicts, training and proficiency; do not collect irrelevant identity attributes.

Each unit shows task/context, permitted references, Response A and Response B. Hidden model IDs, provider names in metadata, generation time, costs, automatic scores and other ratings are unavailable to the annotator API. Randomize A/B order per unit and reviewer, balance across a study, and store the mapping server-side. Model-written self-identification can compromise blinding; record suspected unblinding. Never rewrite substantive answers silently to hide identity.

Rate dimensions for each response, then overall preference: A, B, TIE, or CANNOT_JUDGE. A tie means comparable quality; cannot-judge means insufficient evidence/expertise. N/A means the dimension is inapplicable. These states are not interchangeable.

| Dimension | 1: unacceptable | 3: mixed/adequate with material issue | 5: fully meets requirement |
|---|---|---|---|
| Meaning preservation | Core intent changed | Main meaning retained with an important loss | Required meaning and relations retained |
| Naturalness | Very difficult/unnatural | Understandable but awkward | Natural for requested register |
| Grammar | Errors impede comprehension | Some consequential errors | No material grammatical issue |
| Factuality | Major contradicted claims | Mix of correct and problematic claims | All assessable claims supported by truth evidence |
| Instruction following | Core instruction ignored | Some constraints missed | All applicable instructions met |
| Cultural fit | Material contextual misinterpretation | Context fit uneven | Fits explicit context without stereotyping |
| Completeness | Required content largely absent | Some required units absent | All required units covered |

Scores 2 and 4 represent intermediate severity between adjacent anchors; task-specific examples are mandatory before a study. Factuality is N/A or cannot-judge where evidence does not allow assessment. Cultural fit is N/A for tasks with no cultural requirement. Use a separate groundedness judgment for source entailment when needed. No single mandatory average across these ordinal dimensions.

Require a short rationale and evidence span for major/critical findings and pairwise preferences where feasible. Submission locks the original record; later changes create amendments. Adjudicators see disagreement only after independent submissions. Adjudication creates a separate resolution, including “rubric ambiguous” or “benchmark defective”; it never overwrites original ratings used for agreement.

### Sampling and annotation QA

Maintain a random stratified sample by task and language for overall judge validation and quality estimation. Store sampling probabilities. Keep a separate purposive sample enriched for disagreements/failures; report it as diagnostic, never as population prevalence. If estimates combine unequal-probability sampling, apply declared weights and a compatible uncertainty method.

Use small blinded repeat and reviewed attention-check subsets to inspect within-reviewer consistency, not to inflate the independent sample. Review unusually short completion times as a signal, not automatic fraud proof. Track skip rates and workload. Exclusion rules must be set before outcomes; publish the effect of exclusions and retain audit history. Estimate annotation cost from timed practice sessions, not guessed ratings-per-hour.

## 15. Statistical methodology

### Define what is being estimated

Primary comparison: difference in a specified task success rate between V2 and V1 on matched cases, aggregated with frozen family/slice weights. Report operational completion separately. The default statistical unit is the highest known dependency cluster (source cluster containing one or more intent families); variants and repeated generations stay inside it.

Report case count, family count, cluster count, repetitions, score coverage, slice counts, weights and exclusions. An empirical score on a fixed curated suite is descriptive. Cluster intervals describe a stated generalization model over comparable clusters; they do not convert a convenience benchmark into a representative survey of Malayalam users.

### Paired uncertainty and effect sizes

- For each model, aggregate repetitions within case and variants within family according to the protocol. Retain pairing between configurations.
- Use paired stratified cluster bootstrap for mean-score and pass-rate differences: resample dependency clusters with replacement, retain all paired observations, recompute the declared estimator. Start with 5,000 seeded draws; record method/draws and validate Monte Carlo stability near gates. This is ADRIVA's clustered extension of paired resampling practice [S04].
- Strata used for resampling must be nonoverlapping at the cluster level. If a cluster spans language slices, resample the cluster once and derive all language estimates together; never sample its languages independently.
- Primary effect sizes: absolute percentage-point difference for rates, raw score difference for continuous measures, preference advantage over 0.5 for pairwise judgments. Avoid standardized effects that obscure the original meaning.
- Exact McNemar is optional only for independent paired binary units with one valid outcome per unit; applying it to every dependent variant is invalid [S06]. For family-aggregated nonbinary scores, use cluster resampling instead.
- Treat ordinal ratings with distributions, ordinal agreement and paired preference as primary. Any mean-rating summary explicitly assumes approximate equal spacing and is secondary.

For human preference, map A/B to canonical model identity before analysis. Report V2 wins, V1 wins, ties and cannot-judge separately. A tie-adjusted descriptive rate is (wins + 0.5 × ties)/(wins + losses + ties); cluster over families, not individual ratings. It is not a calibrated probability that V2 is objectively correct.

Default intervals: 95% descriptive confidence intervals. For multiple release gates, use a preregistered multiplicity strategy, initially Bonferroni simultaneous intervals over the finite primary gate set; conservative but straightforward. Exploratory slice tests may use Benjamini–Hochberg adjusted p-values with an explicit dependence caveat and remain exploratory. Never choose the best-looking slice post hoc and relabel it primary.

### Equivalence and release inference

Normalize orientation so positive Δ always means V2 is better. Declare a smallest practically meaningful change δ before looking at evaluation outputs. There is no universal justified δ for all tasks; a release owner must set it from use-case harm and tolerance. Until set, show estimates and INCONCLUSIVE, not a release recommendation.

For a chosen appropriate confidence interval [L,U]:

- Meaningful improvement if L > δ.
- Meaningful regression if U < −δ.
- Practical equivalence if the entire interval is strictly inside [−δ,+δ].
- Otherwise inconclusive about meaningful change. A statistically detectable but smaller effect can coexist with practical equivalence.

Formal equivalence tests require explicit margins and compatible assumptions; paired TOST documentation [S05] is a reference, not permission to feed dependent variants into a t-test. ADRIVA initially uses the conservative interval containment policy above. A non-inferiority release gate requires L > −δ and is labeled “non-inferior within margin,” not “equivalent.”

### Sample size and stochastic outputs

Use pilot cluster differences to simulate power/precision for planned margins, imbalance and within-family dependence; expand independent families, not just paraphrases. No universal minimum n or guaranteed power is asserted. Very small/degenerate cluster samples get descriptive results and an insufficient-evidence flag; a constant observed outcome does not establish zero risk. For truly independent zero-event units, an exact binomial bound can be supplemental; do not use naive binomial bounds on dependent variants.

Initial generation repeat count is one per model/case for cost control; this characterizes observed responses, not stochastic reliability. For a preregistered stochastic subset, use at least three proposed repeats and assess whether more are needed; model seeds may not be supported or deterministic. Repeated outputs remain nested in cases. Interleave/randomize model execution to reduce time/provider drift confounding; retain timestamps and returned version metadata.

Timeouts and rate-limit failures are not hallucinations. Report completion rates, paired semantic results, missingness by slice and worst/best-case sensitivity bounds where useful. A successful-call-only result cannot pass release gates if required completion coverage fails. Do not impute missing semantic ratings as measured zero; a separately labeled end-to-end task-success gate may count noncompletion as failure.

## 16. Inter-annotator agreement

Default: Krippendorff's alpha, nominal for canonical pairwise preference labels and ordinal for anchored dimension ratings. It accommodates multiple raters and missing ratings with an appropriate distance function [S08]. Do not encode A/B/TIE as ordered quality levels. For exactly two fixed reviewers, Cohen's kappa (nominal) or explicitly weighted kappa (ordinal ratings) may be secondary diagnostics.

Compute agreement on original overlapping judgments before adjudication. Report number of reviewers, rated units, overlapping units, language/task distribution, missing/cannot-judge frequency, category prevalence and raw agreement alongside alpha. Exclude N/A from applicable dimensions, and publish its rate. A study with all one category can make chance-corrected coefficients undefined; report UNDEFINED, not 1.0. Negative agreement is allowed and must not be clipped.

Resample dependent families/clusters with all their ratings for an approximate interval; disclose instability for small sets. Such intervals generalize over items conditional on the observed reviewers, not a broad reviewer population. Reviewer-population inference would require a larger crossed design and additional modeling. No universal alpha threshold certifies validity. Low agreement triggers rubric/language/evidence review, not automatic removal of dissenting raters. High agreement can still mean shared error.

Investigate disagreements by dimension, language, task, reviewer pair, ambiguity and factual evidence. Separate rubric ambiguity, reviewer expertise gaps, multiple valid answers, source defects and model ambiguity. Fixing a rubric creates a new rubric revision and possibly a new study; retain the original coefficient.

## 17. LLM-as-Judge methodology and bias controls

Judge output is a fallible measurement. Position, verbosity and self-preference biases are documented concerns [S09]. ADRIVA does not inherit a paper's agreement rate or assume it transfers to Malayalam.

Use an immutable judge configuration: model identifier, returned provider metadata, prompt hash, rubric revision, schema, generation parameters and evidence permissions. Ask for dimension verdicts, short evidence-based rationale and cannot-judge; no hidden reasoning trace is needed. Validate JSON and evidence spans. Parse failure or missing evidence is an error, not a pass. Candidate text is delimited untrusted data; judge has no tools or network access for the initial design.

Calibrate on independently rated calibration families, then evaluate on a separate locked human-reviewed sample. For each applicable language/task slice report confusion matrices, false-positive/negative behavior for critical labels, agreement, score/rank associations where appropriate, abstention and coverage, with uncertainty. Calibration thresholds are selected on calibration only. A judge with unestablished validity in Manglish cannot be a release gate for Manglish.

| Bias or failure | Planned control and evidence |
|---|---|
| Position | Judge both A/B orders on the audit subset; map identities before comparing; report reversal rate |
| Verbosity/style | Human-verified equal-quality content with controlled length/style changes; investigate preference shifts |
| Self/family preference | Record judge/candidate families; cross-family judge where feasible; disclose unavoidable overlap |
| Language preference | Matched human-verified multilingual cases; slice errors rather than assume English calibration transfers |
| Reference anchoring | Include valid alternative answers and intentionally flawed references in clearly separated diagnostic fixtures |
| Prompt injection | Adversarial quoted instructions in candidate text; no execution privileges; check judge task compliance |
| Instability | Repeated audit judgments with stored parameters; variability remains visible |
| Severity blindness | Curated number, negation, omission and fabricated-citation errors with expert labels |

Order disagreement results in UNSTABLE/REVIEW_REQUIRED for a pair, not selecting the convenient order. Multiple judges from similar model families can share bias; a panel is not automatically independent validation. Human reference judgments also have uncertainty and require QA. Optional judge self-confidence is not a calibrated probability.

Architectural choice: one judge integration plus swap/repeat audit first. Alternatives: large judge ensemble or a learned reward model. Selected for inspectability and budget. Trade-off: limited coverage and throughput until human validation expands.

## 18. AI regression-testing methodology

Before execution, freeze a comparison protocol containing baseline/candidate configuration hashes, release manifest, case set, scorers, rubrics, generation repetitions, weights, primary slices, margins, completion requirements, critical failure policy and exclusion rules. Compare like-for-like scoring revisions; if scorers change, rescore both stored response sets and create a new analysis revision. Never compare V1 old scorer scores with V2 new scorer scores without labeling the confound.

The report contains:

1. Compatibility and data-quality checks, with explicit pass/block reason.
2. Matched sample accounting, operational failure rates and costs.
3. Per-task/language effects, intervals, gate classifications and multiplicity policy.
4. Paired transition table: pass→pass, pass→fail, fail→pass, fail→fail, plus missing/unscorable.
5. Hallucination/unsupported-content diagnostics and their validation status.
6. Robustness penalty change, applicable variant sets and language-specific failures.
7. Human preference and agreement evidence, or NOT AVAILABLE.
8. Critical case list, dispositions and unresolved evidence gaps.

Statistical similarity is reported only as practical equivalence within declared margins. A previously passing case now failing is a **case regression** even if aggregate evidence is inconclusive; repeated execution may establish whether it is persistent or stochastic. Do not conflate a single sampled transition with a deterministic model property.

Release state: BLOCK for incompatible evidence, violated hard rules or confirmed disallowed critical regressions; HOLD for insufficient coverage, missing human evidence or inconclusive mandatory gates; ELIGIBLE_FOR_REVIEW when all specified gates meet criteria. Final RELEASE is a signed human decision, not automatic deployment. Exceptions remain explicit overrides; the failed underlying gate remains visible.

## 19. Benchmark versioning strategy

Store immutable item revisions and immutable ordered release manifests with SHA-256 hashes over a specified canonical serialization. Each release pins schema, taxonomy, transform, split and rubric versions; metric and generation configurations are separately frozen in run/analysis protocols.

Proposed semantic labels: MAJOR changes task interpretation, sampling or gold policy enough to break direct comparison; MINOR adds/removes/corrects score-affecting cases within the same broad protocol; PATCH changes only non-scoring documentation/metadata. Any input, reference, split, weighting or constraint change produces a new score-affecting release, never a silent patch. Labels communicate intent; hashes establish actual identity.

Cross-release scores are not directly comparable by default. Permit a clearly labeled intersection analysis only when case revisions and all scoring contracts match, showing excluded coverage; the intersection may not represent either full release. Retire leaked or defective releases without deleting history. Deletion for privacy can tombstone sensitive payloads and mark affected runs non-reproducible; privacy deletion takes precedence over perfect archival reproducibility.

Further methodological decisions: curated families over scraped volume (cost: limited coverage); dimension rubrics over a universal score (cost: more interpretation); independent reviews over synthetic reviewer agents (cost: recruitment); validated proxies over automatic truth claims (cost: unscored cases). These constraints are deliberate quality controls.

### Additional scientific decision record

| DECISION | ALTERNATIVES | WHY SELECTED | TRADE-OFFS |
|---|---|---|---|
| Factorized language/script/register labels | One flat language enum | Separates Romanization from code-switching and noise | More metadata and reviewer work |
| Origin plus derivation plus review events | One provenance category | Preserves synthetic origin after real verification | More relations and validation rules |
| Ordinal alpha for dimension ratings | Pearson correlation; unqualified percent agreement | Models disagreement with the specified measurement level; handles incomplete overlap | Sensitive to category prevalence and distance definition; undefined cases possible |
| Independent blind ratings before adjudication | Consensus discussion first | Measures actual disagreement and reduces anchoring | Slower and requires multiple qualified people |
| Cluster-aware paired intervals | Independent-row t-tests; bootstrap all rows | Preserves shared-intent/source dependence and model pairing | Fewer effective observations and wider intervals |
| Margin-based classifications with conservative primary gate intervals | Nonsignificant means same; unadjusted many-slice tests | Separates practical equivalence, non-inferiority and lack of evidence | Requires justified margins and larger samples |
| Frozen held-out evaluation after calibration | Tune scorer on every observed failure | Limits optimistic evaluation and post hoc threshold selection | Needs new held-out families as iteration continues |
| Embeddings only for retrieval/grouping initially | Cosine similarity as factuality/fidelity gate | Similarity can overlook negation and quantities | Less automated semantic coverage |
| Task-specific evidence for factuality and support | Judge world knowledge as truth | Makes evidence inspectable and unknowns explicit | Evidence authoring and aging cost |
| Separate representative and failure-enriched samples | Merge all annotated items into one accuracy estimate | Avoids biased prevalence estimates | Two sampling/reporting paths |

Any change to these choices requires an architecture decision update and, if score meaning changes, a new evaluation protocol revision.
