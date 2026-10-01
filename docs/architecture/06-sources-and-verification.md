# ADRIVA: sources and verification record

Prepared 1 October 2026. Sources support method/technology choices, not ADRIVA results. The architecture and proposed thresholds are project decisions. No live evaluation, hardware benchmark, dependency install or independent human study was performed.

## Primary-source register

| ID | Source | How used and limitation |
|---|---|---|
| S01 | Ribeiro et al., [Beyond Accuracy: Behavioral Testing of NLP Models with CheckList](https://aclanthology.org/2020.acl-main.442/), ACL 2020 | Behavioral testing foundation; ADRIVA's multilingual contracts still require validation |
| S02 | Popović, [chrF: character n-gram F-score for automatic MT evaluation](https://aclanthology.org/W15-3049/), WMT 2015 | Reference overlap diagnostic; not proof of semantic fidelity |
| S03 | Rei et al., [COMET: A Neural Framework for MT Evaluation](https://aclanthology.org/2020.emnlp-main.213/), EMNLP 2020 | Learned translation metric foundation; no inferred Manglish validity |
| S04 | Koehn, [Statistical Significance Tests for Machine Translation Evaluation](https://aclanthology.org/W04-3250/), EMNLP 2004 | Paired resampling foundation; ADRIVA's source/family clustering is an explicit design adaptation |
| S05 | statsmodels, [paired TOST documentation](https://www.statsmodels.org/stable/generated/statsmodels.stats.weightstats.ttost_paired.html) | Equivalence has bounds and assumptions; not a drop-in test for nested variants |
| S06 | statsmodels, [McNemar documentation](https://www.statsmodels.org/stable/generated/statsmodels.stats.contingency_tables.mcnemar.html) | Paired binary test availability; independent-unit applicability must be checked |
| S07 | PostgreSQL, [SELECT / locking clauses](https://www.postgresql.org/docs/current/sql-select.html) | SKIP LOCKED for queue-style claims; does not supply full job reliability |
| S08 | Krippendorff, [Computing Krippendorff's Alpha-Reliability](https://www.asc.upenn.edu/sites/default/files/2021-03/Computing%20Krippendorff%27s%20Alpha-Reliability.pdf) | Agreement with appropriate measurement distance; not evidence that agreement implies correctness |
| S09 | Zheng et al., [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://arxiv.org/abs/2306.05685), 2023 | Position, verbosity and self-enhancement concerns; its empirical findings are not transferred to ADRIVA |
| S10 | FastAPI, [deployment concepts](https://fastapi.tiangolo.com/deployment/concepts/) | Process/deployment responsibilities; does not establish performance of this planned app |
| S11 | PostgreSQL, [row security policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html) | Optional defense-in-depth behavior and privilege caveats |
| S12 | Node.js, [release schedule/status](https://nodejs.org/en/about/previous-releases) | Node 24 LTS selected; pin actual patch at implementation |
| S13 | Astral, [uv documentation](https://docs.astral.sh/uv/) | Python project/dependency management |
| S14 | Vite, [getting started](https://vite.dev/guide/) | Frontend tooling and environment constraints; resolve actual compatibility in P1 |
| S15 | Python, [downloads and release information](https://www.python.org/downloads/) | Python baseline planning; 3.12 chosen for compatibility, not claimed newest |
| S16 | Docker, [Windows installation requirements](https://docs.docker.com/desktop/setup/install/windows-install/) | Environment preflight; current machine has not been validated |

Methodological cross-checks: behavioral testing versus exact-output matching; paired inference versus independent-row inference; equivalence bounds versus nonsignificance; chance-corrected agreement versus raw percent agreement; judge bias versus automatic truth. Multiple sources cover complementary methods; no claim is made that every ADRIVA-specific policy has external empirical validation.

## Coverage of requested deliverables

| Requested item | Location |
|---|---|
| 1. Final product definition | 01, section 1 |
| 2. Personas | 01, section 2 |
| 3. Workflows | 01, section 3 |
| 4. Requirements | 01, section 4 |
| 5. System architecture | 01, section 5 |
| 6. Technology architecture | 01, section 6; 04 dependencies |
| 7. PostgreSQL/data architecture | 03, section 7 and integrity/storage |
| 8. ER/data model | 03, section 8 |
| 9. Benchmark methodology | 02, section 9 |
| 10. Task taxonomy | 02, section 10 |
| 11. Language taxonomy | 02, section 11 |
| 12. Failure taxonomy | 02, section 12 |
| 13. Automatic evaluation | 02, section 13 |
| 14. Human evaluation | 02, section 14 |
| 15. Statistics | 02, section 15 |
| 16. Inter-annotator agreement | 02, section 16 |
| 17. Judge methodology/bias | 02, section 17 |
| 18. Regression testing | 02, section 18 |
| 19. Benchmark versioning | 02, section 19 |
| 20. Model gateway | 04, section 20 |
| 21. Security/privacy | 04, section 21 |
| 22. UI information architecture | 04, section 22 |
| 23. Repository | 04, section 23 |
| 24. Roadmap | 05, sections 24–26 |
| 25. Phase dependencies | 05, phase table and diagram |
| 26. Acceptance criteria | 05, phase table and evidence bundles |
| 27. Risks/weaknesses | 05, section 27 |
| 28. What not to build | 05, section 28 |
| 29. Software/dependencies | 04, section 29 |
| 30. Local hardware/environment | 04, section 30 |

## Architecture audit and unresolved matters

- Human verification and synthetic origin coexist without conflation.
- Fixture/demo values cannot be reported as observed model or human performance.
- Repeated generations, related variants and shared sources remain clustered.
- Missingness, execution errors and scorer errors have separate result states.
- Equivalence/non-inferiority require predefined margins and sufficient evidence.
- Human A/B identities are withheld server-side; canonical identities are used for agreement analysis.
- Frozen release corrections require new versions; comparison compatibility is explicit.
- Model outputs are persisted separately from scorer revisions; both sides can be rescored fairly.
- API credentials, model provider, actual run budget, reviewer availability and practical margins are intentionally unresolved until their relevant phase.
- These documents are implementation-ready specifications, not production certification or experimentally validated evaluation instruments.
