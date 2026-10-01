# ADRIVA — Final delivery report

Delivered 2026-10-01. **Working, verified local edition. The full production/scientific objective is not complete.** Real model access, genuine human review and production identity/operations infrastructure remain prerequisites. No fixture is presented as scientific evidence.

## PRODUCT

Multilingual evaluation workbench for versioned benchmarks, model execution, paired comparisons, failure investigation and human review. Local URL: **http://127.0.0.1:8019**.

## IMPLEMENTED

**IMPLEMENTED + VERIFIED locally:** FastAPI; PostgreSQL and nine checksummed migrations; immutable benchmark/model registries; durable leased runner; offline/HTTP gateways; deterministic scoring; paired comparisons; failure explorer; blind human-review API; annotation agreement; content-review quorum; data-quality views; worker health; ten-module browser frontend; launcher and reproducible fixture onboarding.

**IMPLEMENTED + VERIFIED using mathematical fixtures:** statistical, agreement, semantic-evidence, role-bound entity/quantity, robustness and judge-audit kernels. These are not validated automatic language judges.

**IMPLEMENTED + UNVERIFIED in deployment:** Docker/Compose and CI scaffolding. No remote repository was published.

## VERIFIED

63 tests passed against isolated PostgreSQL with zero failures/skips. Browser checks covered all ten sections, run/case inspection, paired comparison, Malayalam filtering and mobile layout. Desktop/mobile screenshots inspected; dependency consistency, compilation and lint passed. See VERIFICATION.md.

## BENCHMARK

ADRIVA-BENCH **0.1.0**: 24 synthetic draft cases, six intent families/dependency clusters, six tasks, four language modes. Six base cases and 18 variants; development split only. No external dataset or native verification claimed. Exact generator build/transcript is unavailable; per-case fingerprints identify authored prompt text.

The separate 24-case engineering pack supplies two constant-output fixtures and 48 stored engineering responses. An inherited four-case fixture remains for tests. None is a measured AI benchmark result.

## AI/ML

Integrated/tested: fixture adapter, chat-completions-compatible HTTP transport, NFC exact match, strict JSON-schema subset, typed field accuracy, literal presence and character-limit checks. HTTP validation used a local protocol stub. **No pretrained-model inference, training, live-provider study or validated LLM judge was executed.**

## MALAYALAM

Malayalam script, English, informal Manglish and mixed-language profiles; task/language coverage; derivation lineage; Unicode normalization; Malayalam numeral handling in quantity checks; human review workflow. Native phrasing, dialect coverage, transliteration quality and semantic equivalence remain unverified. Literal metrics are diagnostic.

## STATISTICS

Hierarchical paired means; seeded cluster percentile bootstrap; practical margins; equivalence/noninferiority rules; incomplete/degenerate/small-sample HOLD; Bonferroni interval tails; Holm/BY corrections; independent-pair exact McNemar; nominal/ordinal Krippendorff alpha. Public comparisons remain exploratory and HOLD for fixture/pilot evidence. No independent certification or population validation claimed.

## HUMAN EVALUATION

Matched pairs, balanced blinded A/B assignments, eight rating dimensions, ties, cannot-judge/NA, immutable original submissions, canonical agreement and disagreement lists. Two distinct content reviewers and two transformation reviewers for derived cases are database-enforced. Identity/qualification remains locally self-attested. **Genuine labels: zero.** Test judgments exist only in the disposable test database.

## REGRESSION TESTING

Checks shared release, generation protocol and scorer identity; displays paired changes, observed/planned counts, uncertainty and case transitions. Format/length violations create deduplicated deterministic findings. Exact-match differences do not become semantic failures. Persisted preregistered release approval is not implemented.

## DATA ENGINEERING

Transactions, project-scoped foreign keys, checksummed migrations, immutable manifests/provenance, typed import/export, lineage and cluster-split validation, revision conflicts, content-addressed artifacts, durable jobs and SQL read models. Database/worker behavior tested. Production load and backup/restore drills unverified.

## APPLICATION

Overview; Model Lab; Benchmarks; Regression Testing; Language Intelligence; Failure Explorer; Human Evaluation; Annotation QA; Data Quality; System Health. Includes search, filters, responsive tables, plots, drilldowns, import/export, review forms, health/heartbeat views, empty/error/loading states, focus styling and reduced-motion support.

## TESTING

**63 passed, 0 failed, 0 skipped**; one dependency deprecation warning. Ten browser sections plus interactions passed without JavaScript page exceptions. Results in `docs/evidence/`, screenshots in `docs/screenshots/`. No test-coverage percentage or production-throughput claim.

## SECURITY

Tested Host/origin rejection, safe errors, strict contracts, project-scoped access, artifact safety, immutable evidence, provider redirect rejection and fixture boundaries. Security headers/page CSP added. Credentials are environment references. Source package excludes runtime data/environments/logs/secrets. Local PostgreSQL uses loopback trust. **Public production use is not safe without further identity/operational controls; production startup is blocked.** Dependency CVE auditing was not completed.

## DOCUMENTATION

README/run guide; this report; benchmark card; technical/recruiter audit; verification record; scientific protocol; inherited architecture documents; screenshots and test evidence. Historical architecture is design material, not completion evidence.

## HOW TO RUN ADRIVA

```powershell
cd C:\Users\adria\Documents\Codex\2026-10-01\new-chat-9\ADRIVA
.\Start-ADRIVA.ps1
```

Open **http://127.0.0.1:8019**. Select **Engineering verification**, then include engineering fixtures. Select **ADRIVA research workspace** for the unreviewed pilot. README contains setup, testing and endpoint instructions. Second-computer installation and Docker are documented but unverified.

## REPOSITORY STRUCTURE

`backend/src/adriva/{api,db,domain,evaluation,gateway,workers,storage,web}`; `backend/tests`; `benchmarks/{fixtures,pilot}`; `tools`; `docs`; `infra`; `.github/workflows`; `Start-ADRIVA.ps1`. Source project/package delivered; no GitHub publication.

## LIMITATIONS

No real-model study or genuine human dataset; no validated Malayalam benchmark; only six pilot clusters; no production SSO/RBAC, qualification enforcement, public hosting, CVE clearance, load measurement or backup drill. Semantic/judge/robustness kernels are Python modules rather than integrated automatic judging services. Adjudication/qualification have schema foundations but no completed product workflow. Lists have disclosed caps. Local names cannot prove independent humans. These prevent full enterprise/scientific completion claims.

### USER ACTION REQUIRED — real scientific evaluation

**WHAT:** Configure a permitted model endpoint and arrange actual language-capable reviewers.

**WHY:** Software cannot invent real predictions without a model, independent human judgments or reviewer qualifications.

**STEPS:**
1. Select/start the model service you intend to use. Decide the budget before any paid calls.
2. Set `ADRIVA_ENDPOINT_LOCAL` locally to its full compatible chat-completions URL; set `ADRIVA_PROVIDER_KEY_LOCAL` locally if required. In Model Lab enter only the variable names, actual model ID and version.
3. Restart the worker with those variables. Have two reviewers inspect cases under Benchmarks → Inspect → Record human content review, including transformation reviews. Revise rejected cases rather than overriding them.
4. Freeze genuinely reviewed releases. Plan a larger independent sample before scientific deployment claims.

**WHAT I SHOULD NOT SHARE:** Keys, passwords, tokens or private customer data. Keep secrets in your local environment.

**AFTER COMPLETION:** Send: “ADRIVA endpoint is configured locally; model ID/version is [non-secret ID/version]. Resume real-model verification.” State human-review progress separately and truthfully.

## PORTFOLIO

**ADRIVA — Multilingual AI Evaluation Workbench.** FastAPI/PostgreSQL software for versioned benchmarks, durable evaluation, dependency-aware comparisons, blind review and failure investigation across English, Malayalam, Manglish and code-switching. Locally verified with 63 automated tests and browser checks; scientific collection pending.

## CV

- Developed an AI-assisted FastAPI/PostgreSQL evaluation workbench with nine transactional migrations, immutable benchmark releases and a durable worker.
- Implemented paired cluster-bootstrap comparisons, uncertainty gates and blind human-review workflows; verified the local system with 63 automated tests and browser checks.
- Created a provenance-tracked 24-case multilingual pilot covering six tasks and four language modes, separating synthetic fixtures from scientific evidence.

Use these after you can explain/demonstrate the code. Do not claim independent authorship, native validation or production deployment.

## INTERVIEW

“ADRIVA helps inspect whether a model change is reliable. It versions test cases, stores outputs, compares matched runs and supports blind review. Related language variants share a statistical cluster, and exact match is not semantic understanding. The local system is tested; real-model and native-review results are pending. I used AI assistance and can explain the engineering choices.”

## NEXT STEPS

Optional scope extensions: independently licensed domain datasets, richer adjudication tools, validated judge studies, report exports or a hosted team edition. Actual model access and genuine review are prerequisites for scientific claims, not cosmetic improvements. Production security is required if moving beyond the trusted-local edition.
