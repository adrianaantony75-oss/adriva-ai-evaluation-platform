# ADRIVA: engineering design

Implementation specification, not installed software or a running application.

## 20. Model gateway design

The gateway is an interface inside the backend, not a separate service initially. Model selection is configuration data, not conditional logic spread throughout scorers.

| Contract | Required fields/behavior |
|---|---|
| ModelConfig | provider, endpoint reference, requested model/version, supported capability snapshot, generation parameters, credential reference, digest |
| GenerationRequest | logical request ID, role-based messages, optional output schema, output-token limit, temperature/top-p/seed only if supported, timeout, metadata |
| GenerationResult | raw artifact reference, normalized content, finish reason, requested/returned model IDs, provider request ID, usage with known/unknown flags, timing, error state |
| Capabilities | structured output, seed, token-limit semantics, system messages, parameter restrictions; explicit SUPPORTED/UNSUPPORTED/UNKNOWN |
| Adapter operations | validate configuration, build provider request, execute, normalize result, classify error |

Initial adapters: `FixtureAdapter` for deterministic offline engineering tests and one real provider chosen when credentials and budget are available. The fixture must never appear as a real model in scientific reports. Optional later adapters: second provider and an approved local HTTP endpoint. Unsupported parameters produce validation errors; do not silently discard them. Do not silently fall back from a failed model to a different model.

Pin immutable provider snapshots when offered; otherwise record alias, timestamp and returned metadata and warn that provider-side reproducibility is limited. The same seed does not promise identical outputs across providers. Adapter integration tests use recorded sanitized fixtures; small paid smoke tests are opt-in and budgeted.

Errors: AUTHENTICATION, INVALID_REQUEST, RATE_LIMIT, TIMEOUT, CONNECTION, PROVIDER_ERROR, CANCELLED, MALFORMED_RESPONSE. Distinguish refusal and truncation finish states from transport errors. Retry transient failures with bounded exponential backoff and jitter, respecting Retry-After; never retry invalid credentials indefinitely. Default proposed maximum: three transport attempts, configurable per provider. Timeout may mean the provider completed/billed the request; mark uncertainty rather than assuming it did not happen.

Cache keys cover full normalized request, model configuration and adapter revision; caches are disabled for fresh stochastic repetitions. Reused responses carry explicit cache origin and are never counted as independent generations. Idempotency keys avoid duplicate scheduling; external exactly-once execution is not guaranteed.

### Durable job lifecycle

PENDING → LEASED → RUNNING → SUCCEEDED, with RETRY_WAIT, FAILED or CANCELLED branches. Claim and lease renewal use short DB transactions. A worker checks a monotonically changing lease token before committing selected output; a late stale worker may record an attempt but cannot replace accepted results. Start with one worker and bounded provider concurrency. Introduce additional workers only after crash/retry tests pass.

Cost controls: preflight estimate based on selected cases, repeat count, expected token bounds, judge orders/repeats and a dated price configuration. Estimates are not bills. Track reserved budgets for in-flight calls, actual reported usage and unknown charges. A cap cannot undo already dispatched costs; keep concurrency low enough to bound overshoot and show the bound.

## API contracts and execution states

Proposed REST resources, versioned under `/api/v1`:

| Resource | Operations |
|---|---|
| `/health/live`, `/health/ready` | Process liveness; database/migration readiness without secret disclosure |
| `/benchmarks`, `/benchmark-releases` | Draft/import, validate, review, publish immutable release |
| `/model-configurations`, `/runs` | Capability validation, freeze, enqueue, status, cancel |
| `/responses/{id}`, `/scoring-runs` | Inspect authorized evidence; start versioned scoring |
| `/comparison-protocols`, `/comparisons` | Lock protocol, validate compatibility, compute/report |
| `/studies`, `/assignments`, `/judgments` | Manage review, fetch blind assignment, submit immutable judgment |
| `/failures`, `/quality-issues` | Filter findings, confirm/dispute, quarantine source defects |
| `/artifacts`, `/audit-events` | Authorized expiring downloads; restricted audit access |

Long jobs return 202 plus job ID; frontend polls bounded status endpoints initially. Cursor pagination, maximum payload sizes, typed error codes and correlation IDs are required. Use idempotency keys for creation/enqueue, and expected revision/ETag on draft edits to detect concurrent changes. Server-generated OpenAPI types drive the frontend. Never expose raw ORM objects as annotation response DTOs.

Run states: DRAFT, QUEUED, RUNNING, COMPLETED, PARTIAL, FAILED, CANCELLED. Completed generation does not mean completed scoring, qualified human evidence or release approval. Track these separately. Reports read frozen evidence snapshots, not changing live dashboard aggregates.

## 21. Security and privacy design

### Scope and threat model

Protect provider keys, private benchmark inputs, held-out references, reviewer identities, A/B mappings and release evidence. Threats include unauthorized object access, accidental prompt leakage, malicious response markup, judge prompt injection, provider endpoint abuse, oversized uploads, leaked exports and destructive administrative mistakes.

| Boundary | Required control |
|---|---|
| Browser/API | Server-side project authorization on every object lookup; explicit roles; bounded requests |
| Reviewer endpoint | Assignment-scoped DTO; no model mapping, other ratings or automatic scores before submission |
| Authentication | Loopback-only development identity initially; deployed multi-user mode must use maintained OIDC integration before exposure |
| Session | HttpOnly/Secure cookies for deployed sessions, CSRF protection where applicable, explicit allowed origins |
| Provider access | Server-only credentials, endpoint allowlist, TLS for remote endpoints, outbound restriction; no arbitrary URL fetch |
| Local adapters | Explicit development allowlist for approved localhost service only; not user-supplied arbitrary network destinations |
| Untrusted text | Render as escaped text; restricted Markdown if needed; no executable HTML or scripts |
| Judge | Untrusted candidate delimiter, no tools, schema validation, injection tests; prompt instructions alone are not a security boundary |
| Upload/import | JSONL and constrained CSV only initially; file size/row/text limits; schema validation; no pickle, executable templates or arbitrary archives |
| Export | Sanitize spreadsheet-formula prefixes, redact restricted payloads, exclude secrets and reviewer identifiers |
| Operations | Separate migration/runtime DB roles, least privilege, non-root containers, secret/dependency scanning |

OIDC is deferred to the deployment phase, not omitted. Before then bind to loopback and label the demo single-user; the dev identity mode must refuse production startup. Evaluate a maintained OIDC library/provider at that phase rather than implement password recovery and authentication protocols from scratch.

PostgreSQL row-level security is optional defense in depth for later project isolation, not a substitute for authorization; owners and privileged roles require special care [S11]. Do not claim tenant isolation without dedicated tests and threat review.

### Privacy practices

Use invented non-personal contexts first. Public availability does not establish reuse rights. Store dataset licenses, consent/permission and provider-data handling policy before transmission. Sensitive cases are blocked from remote execution unless explicitly approved for that provider; local-only policy is enforceable per source/project. Secret/PII detection is a review aid, not a guarantee of anonymization.

Store reviewer accounts separately from exports; pseudonyms may still be personal data. Keep original sensitive prompts out of normal logs and traces. Record limited access audits. Deletion must cover original artifacts, derived exports, caches and backup-expiry policy; cryptographic hashes can still require sensitivity assessment. No GDPR, Indian-law, ISO or SOC compliance claim is made by this design. Real organizational deployment needs an applicable policy review.

## 22. Enterprise UI information architecture

An application for making and auditing decisions: restrained navigation, dense readable tables, useful filters, status explanations, evidence drawers and saved comparisons. Avoid decorative “AI score” hero cards, fabricated live activity and empty charts presented as results.

| Area | Primary screen and action | Phase |
|---|---|---|
| Overview | Current project/release, evidence readiness, unresolved gates, recent real runs | P3–P7 |
| Model Lab | Immutable configurations, capabilities, run manifest, spend estimate, execution status | P3 |
| Benchmarks | Release browser, provenance, split coverage, case/variant lineage, publish review | P2 |
| Regression Testing | V1/V2 compatibility, effects/intervals, pass-to-fail cases, review decision | P4/P7 |
| Language Intelligence | Matched family views, input/output profiles, robustness penalties and limitations | P4/P7 |
| Failure Explorer | Taxonomy/severity slices, evidence spans, proposed/confirmed findings | P4/P7 |
| Human Evaluation | Assigned blind A/B queue, anchored rubric, autosaved draft, final submit | P5 |
| Annotation QA | Overlap, agreement, disagreement/adjudication, reviewer workload | P5 |
| Data Quality | Import reports, duplicates, license/provenance gaps, quarantine and leakage | P2 |
| System Health | Queue age, errors, provider status, costs, versions and backup state | P3/P8 |

Keep future areas out of navigation until implemented or clearly label them “Not implemented”; no dead links implying completeness. Top-level context includes project, benchmark release and evaluation provenance (FIXTURE/PILOT/REAL RUN). Metric tiles always show applicable n, coverage, definition and uncertainty where available. Empty state says “No evaluations yet.” “Human reviewed” requires an actual review record.

Comparison screen: protocol and compatibility at top, then estimates/gates and counts, followed by filtered failures and detailed paired evidence. Annotation screen: original task/context above two equally sized panes; no response-length truncation that favors one model. Keyboard shortcuts must not accidentally submit. Malayalam wrapping and text-selection behavior need visual verification. Preserve full source text behind a clear expansion control.

## 23. Repository architecture

One Git repository; ordinary monorepo directories, no monorepo orchestration framework initially.

| Path | Responsibility |
|---|---|
| `README.md`, `docs/` | Setup, architecture, methods, ADRs, data/model cards, runbooks and limitations |
| `backend/pyproject.toml`, `backend/uv.lock` | Python dependency groups and exact resolved versions |
| `backend/src/adriva/api/` | Routes, authentication dependencies, public DTOs |
| `backend/src/adriva/domain/` | Benchmark, execution, annotation, scoring and comparison rules |
| `backend/src/adriva/db/`, `backend/migrations/` | ORM, repositories, migrations and SQL views |
| `backend/src/adriva/gateway/` | Provider adapters and normalized contracts |
| `backend/src/adriva/evaluation/` | Metrics, statistics, rubrics and judge integration |
| `backend/src/adriva/workers/` | Job claims, retries, cancellation and execution |
| `backend/src/adriva/storage/` | Artifact interface and local adapter |
| `backend/tests/` | Unit, integration, scientific reference fixtures and contract tests |
| `frontend/src/` | App shell, feature modules, shared controls and generated API types |
| `frontend/tests/` | UI behavior and end-to-end tests |
| `benchmarks/schemas/`, `benchmarks/manifests/` | Versioned contracts and public release manifests |
| `benchmarks/fixtures/` | Clearly marked non-scientific test data |
| `infra/` | Compose and container definitions; deployment configuration later |
| `scripts/` | Small import/export/verification commands; no hidden business logic |
| `.github/workflows/` | Offline quality gates and later gated deployment |

Ignore local secrets, database volumes, raw private benchmarks, generated responses, model weights and caches. Publish safe configuration examples only. Public benchmark data needs explicit rights review; use a manifest without private payloads where appropriate. Notebooks are optional exploratory analysis, not production scoring pipelines. A packaged CLI invokes the same domain services as the API.

## 29. Required software and dependencies

Proposed baseline: Python 3.12 with uv; Node.js 24 LTS with npm lockfile; PostgreSQL 18; Docker Compose for Linux containers. These are selected compatibility targets, not claims that each is the latest available release. Lock exact compatible patch/package versions in P1 after install/build checks; never use floating `latest` container tags in a released environment. Node's official release table lists 24 as LTS [S12]; Python downloads and Vite/uv docs are the installation references [S13–S15].

| Stage | Dependencies/tools | Purpose |
|---|---|---|
| P1 | Git, Python/uv, Node/npm, Docker Desktop or Docker Engine + Compose, editor | Reproducible foundation |
| P1 backend | FastAPI, Uvicorn, Pydantic, pydantic-settings, SQLAlchemy, psycopg, Alembic | Typed service and PostgreSQL migrations |
| P1 frontend | React, TypeScript, Vite, router; selected accessible component primitives and CSS approach | Enterprise shell without SSR |
| P1 quality | pytest, Ruff, type checker; TypeScript/ESLint and Vitest | Targeted correctness and static checks |
| P2/P3 | HTTPX, JSON Schema validation; provider SDK only if adapter needs it | Imports and provider execution |
| P4 | NumPy, SciPy, pandas, statsmodels, sacrebleu as applicable | Statistics and reference diagnostics |
| P5 | Validated Krippendorff alpha implementation; Playwright | Agreement and blind-workflow testing |
| P7 | TanStack Query/Table and a modest chart library if needed | Caching, dense tables, inspectable charts |
| P8 | Maintained OIDC library, metrics exporter; optional OpenTelemetry | Authentication and operational observability |
| Optional later | sentence-transformers; compatible COMET checkpoint runtime | Failure grouping or validated MT diagnostics only |

Dependency minimization: install groups when their phase starts. Validate licenses and maintenance before adopting optional metric models. An optional metric must not make the core application require heavyweight tensor libraries. No paid plugin is necessary. GitHub integration is convenient after a repository exists; provider accounts/API keys are needed only for real remote calls. ChatGPT subscription access must not be assumed to include external API credits.

No installations, account creation, paid requests or deployments are performed in this architecture phase.

## 30. Local environment and hardware

Machine specifications have not been inspected in this phase. Prior conversation mentioned an 8 GB laptop; treat that as unverified. The platform should run without a dedicated GPU when using remote model APIs.

| Environment | Planning recommendation | Limitation |
|---|---|---|
| Comfortable local build | 4+ CPU cores, 16 GB RAM, SSD with roughly 25–40 GB free | Estimated headroom, not a measured minimum |
| Constrained 8 GB machine | API models, one worker, small batches; frontend/backend native plus one database, or carefully limited containers | Browser/IDE/Docker may exhaust memory; postpone embeddings and local inference |
| Optional local-model evaluation | Select hardware only after model size, precision and context are chosen | No promise that an existing laptop can run a suitable Malayalam model |
| Hosted demo | Start with a small single-host private environment, benchmark before sizing | No uptime/capacity guarantee from this document |

Windows setup: confirm supported Windows build, virtualization and WSL2 requirements against Docker's official instructions [S16]. Keep Linux dependencies inside WSL/container and Windows dependencies in Windows; do not mix virtual environments or node_modules across OS boundaries. Docker Desktop licensing must be checked for the eventual organization. If virtualization/admin access is unavailable, use a supported native PostgreSQL development installation and document the alternative; CI still exercises Linux containers.

The first implementation should inspect actual RAM, free disk, existing tools and virtualization status read-only, then use what is available. Do not ask the user to buy hardware or download local models before the actual workload requires it.

## Testing, CI/CD and observability

CI uses deterministic fixtures and PostgreSQL integration tests, not paid live model calls. Check migrations from an empty database and upgrade from the preceding release, scorer edge cases, independent-pair accounting, cluster resampling, blind API payloads, authorization, stale-lease recovery and export redaction at the phases that introduce them. Avoid meaningless test-count or coverage-percentage claims.

Build immutable container images after tests; scan dependencies/secrets; retain build revision. Later deployment migrates via a controlled job, backs up first and verifies health. Application rollback must be compatible with the schema; do not assume destructive migration rollback is safe. CD is a later private deployment workflow, not auto-publishing every commit.

Logs: correlation/run/job/attempt IDs, safe error classification, duration and state transitions; no full prompts or tokens. Metrics: queue age, attempts, completion and scoring failures, latency, coverage, estimated/known spend and worker heartbeat. Distinguish provider latency from API response latency. Do not put prompts or unbounded case IDs in metric labels. Health endpoints expose only what is needed; detailed health is administrator-only.
