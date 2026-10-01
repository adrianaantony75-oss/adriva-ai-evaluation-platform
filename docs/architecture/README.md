# ADRIVA — architecture and methodology checkpoint

Version: 1.0 • Prepared: 1 October 2026 • Status: design complete; implementation not started.

ADRIVA is a multilingual AI evaluation and release-decision workbench. It produces traceable evidence about changes between model configurations, with controlled English/Malayalam robustness tests and independent human review. It does not certify universal model reliability.

## Reading order

1. [Product and system architecture](01-product-and-system.md): definition, people, workflows, requirements, topology and architectural decisions.
2. [Scientific methodology](02-evaluation-methodology.md): benchmark, taxonomies, scoring, human review, statistics, judge validation and regression gates.
3. [Data architecture](03-data-architecture.md): PostgreSQL entities, relationships, constraints, lineage and analytical SQL contracts.
4. [Engineering design](04-engineering-design.md): gateway, APIs, security, UI, repository and local environment.
5. [Delivery plan and handoff](05-delivery-plan.md): dependencies, phase acceptance criteria, risks, exclusions and next implementation prompt.
6. [Sources and verification](06-sources-and-verification.md): primary sources, limitations and coverage of all 30 requested deliverables.

## Non-negotiable interpretation rules

- No benchmark scores, human ratings, agreement coefficients, release outcomes or performance measurements have been produced in this phase.
- All counts, performance budgets and proposed thresholds in these documents are planning choices, not empirical results.
- Engineering fixtures are always marked FIXTURE and excluded from scientific reports. Synthetic benchmark content retains its origin even after human review.
- Related variants, repeated generations and questions sharing a source are not independent observations.
- A nonsignificant difference is not evidence of equivalence. An unsupported claim is not automatically a proven falsehood.
- Independent human evaluation requires other people. One author's repeated ratings cannot establish inter-annotator agreement.
- The first build targets a local, single-organization application. Production readiness requires completing the later security and operational gates.

## Scope sequence

Build one trustworthy vertical slice: benchmark import → immutable release → two model configurations → deterministic evaluation → paired comparison → inspectable evidence. Add controlled variants, independent human evaluation and judge calibration in subsequent phases. Do not scaffold every eventual feature in the first implementation.

ASTRA MEDIUM PHASE COMPLETE

NEXT RECOMMENDED MODEL: GPT-5.6 SOL  
EFFORT: MEDIUM

NEXT TASK: Implement Phase P1 only: repository foundation, PostgreSQL migration infrastructure, FastAPI health/readiness endpoints, a React application shell, Docker Compose development setup and offline CI. Use the exact handoff and acceptance criteria in 05-delivery-plan.md. Stop before benchmark ingestion, model calls or scoring.
