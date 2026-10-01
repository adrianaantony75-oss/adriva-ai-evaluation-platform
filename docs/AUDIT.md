# Final technical and recruiter audit

Scope: internally audited local implementation on 2026-10-01. This is not independent security certification or scientific peer review.

| Severity | Finding | Resolution / remaining limit |
|---|---|---|
| HIGH | Local API could accept hostile Host/origin requests | Fixed: loopback Host allowlist, cross-origin/cross-site mutation rejection; tested |
| HIGH | Protocol required two reviewers while database required one | Fixed: migration 009 enforces distinct reviewer quorum; repeated same-reviewer submissions cannot satisfy it; negative verdict veto retained |
| HIGH | UI review readiness could count transformation-only approval as content readiness | Fixed: common SQL readiness view checks content/transform quorum and negative verdicts |
| HIGH for public deployment | No authenticated multiuser identity or authorization enforcement | Unresolved production prerequisite. Local-only deployment, trusted OS user, production startup refused. Do not publish this as enterprise SaaS |
| HIGH for scientific claims | No genuine human review, representative sample or real-model experiment | No scientific claims released. Pilot remains DRAFT; fixture/pilot comparisons HOLD. Requires real reviewers and model access |
| MEDIUM | Completed runs lacked a consolidated evidence inspection screen | Fixed: project-scoped run evidence endpoint and UI, tested |
| MEDIUM | Deterministic violations were scored but not discoverable as failure findings | Fixed: only schema/length violations become confirmed automatic findings; exact-match differences do not become semantic failures; rescore deduplication tested |
| MEDIUM | Reproducible launch and current documentation missing | Fixed: local launcher, seed builder, bootstrap, run guide, source package and verification evidence |
| MEDIUM | Production quality/methodology modules exceeded UI integration | Disclosed: semantic evidence, role-bound entity/quantity checks, robustness and judge-audit kernels are unit-tested Python components; not a validated automatic judge service |
| MEDIUM | Rare events, domain shifts and cluster misspecification invalidate broad inference | Preserved caveats. Bootstrap gates are safeguards, not guarantees. No benchmark generalization claimed |
| LOW | Starlette TestClient warns about future HTTPX transition | One deprecation warning; tests pass. Dependency migration is optional maintenance |

## Security checks

Checked strict request contracts, safe error messages, request-size limits, cross-project lookups, immutable releases/reviews, transactional imports, migration checksums, lease behavior, artifact traversal/integrity, SQL parameter binding, frontend text escaping and fixture contamination boundaries. Tested HTTP redirects, malformed responses and rate-limit classification with an in-process protocol stub. Provider secrets are environment references, not stored values. Logs omit provider response bodies and credentials; API access paths are local operational metadata.

Additional response headers: no-store, nosniff, DENY framing, no-referrer and restrictive page CSP. Inline styling remains allowed; inline scripts do not. API docs use their normal external assets and are excluded from page CSP. No network exposure, provider credentials, paid calls or messages to others were used.

The local PostgreSQL cluster uses trust authentication over loopback. Any trusted local OS process can connect; this is inappropriate for sensitive/shared production machines. A runtime role with deployment-grade least privilege, SSO/RBAC, TLS, rate limiting, retention policy, backup/restore drills and load testing remain necessary before public deployment. Container files were inspected and corrected, not executed. No vulnerability-database audit could be completed with the restricted package/network environment; do not interpret a source secret scan as a dependency CVE clearance.

## Scientific checks

Checked finite score validation, exact case/repetition pairing, family-to-cluster consistency, equal hierarchical weighting, seeded paired resampling, missing-data HOLD, degenerate interval HOLD, practical margins, exact independent-pair McNemar calculations, Holm/BY reference examples, nominal/ordinal alpha behavior, blinded mapping and fixture-origin guards. Tests are mathematical and engineering fixtures. They do not measure natural-language accuracy or validate a judge against humans.

The public comparison endpoint is exploratory and intentionally never upgrades a pilot to predeclared scientific evidence. The Python inference kernel supports reviewed-evaluation plans, but the application does not offer a fully persisted preregistered release-approval workflow. A clinician, regulator or production release owner must not treat the demo as certified decision support.

Primary implementation references consulted: FastAPI middleware documentation, SciPy bootstrap documentation; the inherited scientific protocol links original methodology literature. These references motivate checks, but do not independently validate ADRIVA's code.

## Recruiter audit

Strong evidence: relational modeling, PostgreSQL constraints and migrations, durable worker design, tested APIs, multilingual data provenance, uncertainty-aware inference, independent-review workflows, frontend/backend integration, and honest separation of fixtures from findings.

Not demonstrated: training an ML model, improving real model performance, serving enterprise customers, production scaling, independently certified Malayalam evaluation, or running a real annotator study. Do not add claims such as “improved accuracy by 30%,” “evaluated thousands of models,” “production enterprise SaaS,” or “human-validated benchmark.”

For interview ownership, be able to explain: why related language variants share a cluster, why exact match is not semantics, why missing pairs force HOLD, what a worker lease prevents, how freeze checks are enforced in SQL, and how the fixture boundary is tested. This code was developed with AI assistance; do not misrepresent independent authorship or understanding.
