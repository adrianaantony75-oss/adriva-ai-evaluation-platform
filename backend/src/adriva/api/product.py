"""Project-scoped product read models; calculations stay on the backend."""

from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Query

from adriva.config import Settings
from adriva.db.connection import connect
from adriva.errors import DomainError
from adriva.evaluation.regression import case_transitions
from adriva.evaluation.statistics import AnalysisPlan, Pair, compare


def product_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects/{project_id}")

    @router.get("/workspace")
    def workspace(project_id: UUID, include_fixtures: bool = False) -> dict:
        with connect(settings) as db:
            if not db.execute("SELECT 1 FROM project WHERE id=%s", (project_id,)).fetchone():
                raise DomainError("NOT_FOUND", "Project not found", 404)
            releases = db.execute(
                "SELECT r.id,b.name,r.version,r.state,r.manifest_digest,count(rc.case_revision_id) AS cases FROM benchmark_release r JOIN benchmark b ON b.id=r.benchmark_id LEFT JOIN release_case rc ON rc.release_id=r.id WHERE r.project_id=%s GROUP BY r.id,b.name ORDER BY b.name,r.version LIMIT 100",
                (project_id,),
            ).fetchall()
            models = db.execute(
                "SELECT id,provider,requested_model,model_version,usage_class,parameters,endpoint_ref FROM model_configuration WHERE project_id=%s ORDER BY requested_model,model_version LIMIT 100",
                (project_id,),
            ).fetchall()
            runs = db.execute(
                "SELECT r.*,m.requested_model,m.model_version,b.version AS benchmark_version,(SELECT count(*) FROM run_item i WHERE i.run_id=r.id) AS planned,(SELECT count(*) FROM run_item i WHERE i.run_id=r.id AND i.state='SUCCEEDED') AS succeeded FROM run r JOIN model_configuration m ON m.id=r.model_config_id JOIN benchmark_release b ON b.id=r.release_id WHERE r.project_id=%s AND (%s OR r.usage_class<>'FIXTURE') ORDER BY r.created_at DESC,r.id LIMIT 100",
                (project_id, include_fixtures),
            ).fetchall()
            totals = db.execute(
                "SELECT count(*) AS cases,count(DISTINCT i.family_id) AS families,count(*) FILTER(WHERE c.usage_class<>'FIXTURE' AND NOT EXISTS(SELECT 1 FROM v_case_review_readiness v WHERE v.id=c.id AND v.ready)) AS pending_review FROM case_revision c JOIN case_item i ON i.id=c.case_item_id WHERE c.project_id=%s AND (%s OR c.usage_class<>'FIXTURE')",
                (project_id, include_fixtures),
            ).fetchone()
            totals.update(
                db.execute(
                    "SELECT count(*) FILTER(WHERE a.state='ASSIGNED') AS review_queue,count(*) FILTER(WHERE a.state='SUBMITTED') AS submitted_reviews FROM assignment a WHERE a.project_id=%s",
                    (project_id,),
                ).fetchone()
            )
            totals["open_quality_issues"] = db.execute(
                "SELECT count(*) AS n FROM quality_issue WHERE project_id=%s AND state='OPEN'",
                (project_id,),
            ).fetchone()["n"]
            totals["confirmed_failures"] = db.execute(
                "SELECT count(*) AS n FROM failure_finding f JOIN response o ON o.id=f.response_id JOIN run_item i ON i.id=o.run_item_id JOIN run r ON r.id=i.run_id WHERE f.project_id=%s AND f.verification_state='CONFIRMED' AND (%s OR r.usage_class<>'FIXTURE')",
                (project_id, include_fixtures),
            ).fetchone()["n"]
            workers = db.execute(
                "SELECT owner,state,last_seen,(last_seen>now()-interval '45 seconds') AS fresh FROM worker_heartbeat ORDER BY last_seen DESC LIMIT 20"
            ).fetchall()
            jobs = db.execute(
                "SELECT state,count(*) AS count,count(*) FILTER(WHERE state='LEASED' AND lease_until<now()) AS expired_leases FROM job WHERE project_id=%s GROUP BY state",
                (project_id,),
            ).fetchall()
            activity = db.execute(
                "SELECT action,created_at,target_id FROM audit_event WHERE project_id=%s ORDER BY created_at DESC LIMIT 12",
                (project_id,),
            ).fetchall()
            return {
                "generated_at": datetime.now(UTC),
                "include_fixtures": include_fixtures,
                "totals": totals,
                "releases": releases,
                "models": models,
                "runs": runs,
                "workers": workers,
                "jobs": jobs,
                "activity": activity,
                "reliability_status": "NOT_ESTABLISHED",
                "list_limit": 100,
            }

    @router.get("/cases")
    def cases(
        project_id: UUID,
        search: str = Query(default="", max_length=200),
        language: str = "",
        task: str = "",
        release_id: UUID | None = None,
        include_fixtures: bool = False,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=40, ge=1, le=100),
    ) -> dict:
        where = (
            "c.project_id=%s AND (%s OR c.usage_class<>'FIXTURE') AND (%s='' OR i.stable_key ILIKE %s OR c.prompt ILIKE %s) AND (%s='' OR f.primary_task=%s) AND (%s='' OR "
            + LANGUAGE_SQL
            + "=%s) AND (%s::uuid IS NULL OR EXISTS(SELECT 1 FROM release_case rc WHERE rc.case_revision_id=c.id AND rc.release_id=%s))"
        )
        args = (
            project_id,
            include_fixtures,
            search,
            "%" + search + "%",
            "%" + search + "%",
            task,
            task,
            language,
            language,
            release_id,
            release_id,
        )
        joins = " FROM case_revision c JOIN case_item i ON i.id=c.case_item_id JOIN intent_family f ON f.id=i.family_id "
        with connect(settings) as db:
            total = db.execute("SELECT count(*) AS n" + joins + "WHERE " + where, args).fetchone()[
                "n"
            ]
            rows = db.execute(
                "SELECT c.id,i.stable_key,c.revision_no,c.prompt,c.usage_class,c.creation_origin,c.input_profile,f.primary_task,"
                + LANGUAGE_SQL
                + " AS language"
                + joins
                + "WHERE "
                + where
                + " ORDER BY i.stable_key,c.revision_no LIMIT %s OFFSET %s",
                (*args, limit, offset),
            ).fetchall()
            return {"items": rows, "total": total, "offset": offset, "limit": limit}

    @router.get("/cases/{case_id}")
    def case_detail(project_id: UUID, case_id: UUID) -> dict:
        with connect(settings) as db:
            case = db.execute(
                "SELECT c.*,i.stable_key,f.primary_task,f.stable_key AS family FROM case_revision c JOIN case_item i ON i.id=c.case_item_id JOIN intent_family f ON f.id=i.family_id WHERE c.project_id=%s AND c.id=%s",
                (project_id, case_id),
            ).fetchone()
            if not case:
                raise DomainError("NOT_FOUND", "Case not found", 404)
            case["responses"] = db.execute(
                "SELECT o.id,o.normalized_text,o.finish_reason,r.id AS run_id,m.requested_model,m.model_version FROM response o JOIN run_item i ON i.id=o.run_item_id JOIN run r ON r.id=i.run_id JOIN model_configuration m ON m.id=r.model_config_id WHERE i.case_revision_id=%s ORDER BY o.selected_at DESC LIMIT 30",
                (case_id,),
            ).fetchall()
            case["reviews"] = db.execute(
                "SELECT review_kind,verdict,rationale,submitted_at FROM case_review WHERE case_revision_id=%s",
                (case_id,),
            ).fetchall()
            return case

    @router.get("/language-matrix")
    def language_matrix(
        project_id: UUID, include_fixtures: bool = False, release_id: UUID | None = None
    ) -> list:
        with connect(settings) as db:
            return db.execute(
                "SELECT "
                + LANGUAGE_SQL
                + " AS language,f.primary_task,count(DISTINCT c.id) AS cases,count(DISTINCT f.id) AS families,count(DISTINCT c.id) FILTER(WHERE EXISTS(SELECT 1 FROM v_case_review_readiness v WHERE v.id=c.id AND v.ready)) AS reviewed FROM case_revision c JOIN case_item i ON i.id=c.case_item_id JOIN intent_family f ON f.id=i.family_id WHERE c.project_id=%s AND (%s OR c.usage_class<>'FIXTURE') AND (%s::uuid IS NULL OR EXISTS(SELECT 1 FROM release_case rc WHERE rc.case_revision_id=c.id AND rc.release_id=%s)) GROUP BY 1,2 ORDER BY 1,2",
                (project_id, include_fixtures, release_id, release_id),
            ).fetchall()

    @router.get("/failures")
    def failures(
        project_id: UUID,
        label: str = "",
        state: str = "",
        language: str = "",
        task: str = "",
        search: str = Query(default="", max_length=200),
        include_fixtures: bool = False,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=40, ge=1, le=100),
    ) -> dict:
        joins = " FROM failure_finding ff JOIN response o ON o.id=ff.response_id JOIN run_item ri ON ri.id=o.run_item_id JOIN run r ON r.id=ri.run_id JOIN case_revision c ON c.id=ri.case_revision_id JOIN case_item i ON i.id=c.case_item_id JOIN intent_family f ON f.id=i.family_id "
        where = (
            "ff.project_id=%s AND (%s OR r.usage_class<>'FIXTURE') AND (%s='' OR ff.verification_state=%s) AND (%s='' OR EXISTS(SELECT 1 FROM finding_label l WHERE l.finding_id=ff.id AND l.code=%s)) AND (%s='' OR "
            + LANGUAGE_SQL
            + "=%s) AND (%s='' OR f.primary_task=%s) AND (%s='' OR i.stable_key ILIKE %s OR o.normalized_text ILIKE %s)"
        )
        args = (
            project_id,
            include_fixtures,
            state,
            state,
            label,
            label,
            language,
            language,
            task,
            task,
            search,
            "%" + search + "%",
            "%" + search + "%",
        )
        with connect(settings) as db:
            total = db.execute("SELECT count(*) AS n" + joins + "WHERE " + where, args).fetchone()[
                "n"
            ]
            rows = db.execute(
                "SELECT ff.*,c.id AS case_id,i.stable_key,f.primary_task,o.normalized_text,(SELECT array_agg(l.code ORDER BY l.code) FROM finding_label l WHERE l.finding_id=ff.id) AS labels"
                + joins
                + "WHERE "
                + where
                + " ORDER BY ff.id LIMIT %s OFFSET %s",
                (*args, limit, offset),
            ).fetchall()
            return {"items": rows, "total": total}

    @router.get("/quality")
    def quality(project_id: UUID) -> dict:
        with connect(settings) as db:
            issues = db.execute(
                "SELECT q.*,r.version FROM quality_issue q JOIN benchmark_release r ON r.id=q.release_id WHERE q.project_id=%s ORDER BY q.state,q.severity LIMIT 200",
                (project_id,),
            ).fetchall()
            pending = db.execute(
                "SELECT c.id,i.stable_key,c.creation_origin FROM case_revision c JOIN case_item i ON i.id=c.case_item_id WHERE c.project_id=%s AND c.usage_class<>'FIXTURE' AND NOT EXISTS(SELECT 1 FROM v_case_review_readiness v WHERE v.id=c.id AND v.ready) ORDER BY i.stable_key LIMIT 200",
                (project_id,),
            ).fetchall()
            return {"issues": issues, "pending_content_review": pending, "limit": 200}

    @router.get("/comparison")
    def comparison(
        project_id: UUID,
        baseline: UUID,
        candidate: UUID,
        metric: str = "reference_exact_match",
        margin: float = Query(default=0.05, ge=0, lt=1),
    ) -> dict:
        if baseline == candidate:
            raise DomainError("SAME_RUN", "Choose distinct model runs", 422)
        with connect(settings) as db:
            runs = db.execute(
                "SELECT r.*,b.manifest_digest FROM run r JOIN benchmark_release b ON b.id=r.release_id WHERE r.project_id=%s AND r.id IN (%s,%s)",
                (project_id, baseline, candidate),
            ).fetchall()
            by_id = {r["id"]: r for r in runs}
            if len(by_id) != 2:
                raise DomainError("NOT_FOUND", "Both runs must belong to this project", 404)
            a, b = by_id[baseline], by_id[candidate]
            scores = {}
            for rid in (baseline, candidate):
                scores[rid] = db.execute(
                    "SELECT * FROM scoring_run WHERE run_id=%s AND state='COMPLETED' ORDER BY created_at DESC,id DESC LIMIT 1",
                    (rid,),
                ).fetchone()
            if not all(scores.values()):
                raise DomainError("UNSCORED", "Score both terminal runs first", 409)
            if (
                a["release_id"] != b["release_id"]
                or a["protocol_digest"] != b["protocol_digest"]
                or scores[baseline]["scorer_set_digest"] != scores[candidate]["scorer_set_digest"]
            ):
                raise DomainError(
                    "INCOMPARABLE",
                    "Runs require identical benchmark, generation protocol and scorer",
                    409,
                )
            rows = db.execute(
                "SELECT i.case_revision_id,i.repetition_index,c.prompt,ci.stable_key,f.id AS family,f.cluster_id,m.value AS baseline_value,n.value AS candidate_value FROM run_item i JOIN case_revision c ON c.id=i.case_revision_id JOIN case_item ci ON ci.id=c.case_item_id JOIN intent_family f ON f.id=ci.family_id LEFT JOIN response o ON o.run_item_id=i.id LEFT JOIN metric_result m ON m.response_id=o.id AND m.scoring_run_id=%s AND m.dimension=%s AND m.status='VALUE' LEFT JOIN run_item j ON j.run_id=%s AND j.case_revision_id=i.case_revision_id AND j.repetition_index=i.repetition_index LEFT JOIN response p ON p.run_item_id=j.id LEFT JOIN metric_result n ON n.response_id=p.id AND n.scoring_run_id=%s AND n.dimension=%s AND n.status='VALUE' WHERE i.run_id=%s ORDER BY ci.stable_key,i.repetition_index",
                (
                    scores[baseline]["id"],
                    metric,
                    candidate,
                    scores[candidate]["id"],
                    metric,
                    baseline,
                ),
            ).fetchall()
            pairs = [
                Pair(
                    str(r["case_revision_id"]),
                    r["repetition_index"],
                    str(r["family"]),
                    str(r["cluster_id"]),
                    float(r["baseline_value"]) if r["baseline_value"] is not None else None,
                    float(r["candidate_value"]) if r["candidate_value"] is not None else None,
                )
                for r in rows
            ]
            plan = AnalysisPlan(
                a["manifest_digest"],
                scores[baseline]["scorer_set_digest"],
                a["protocol_digest"],
                frozenset((p.case, p.repetition) for p in pairs),
                margin,
                0.2,
                evidence="FIXTURE" if a["usage_class"] == "FIXTURE" else "PILOT",
            )
            result = compare(
                pairs,
                plan,
                candidate_fingerprints=(
                    b["manifest_digest"],
                    scores[candidate]["scorer_set_digest"],
                    b["protocol_digest"],
                ),
            )
            return {
                "analysis": asdict(result),
                "metric": metric,
                "margin": margin,
                "transitions": case_transitions(pairs, pass_threshold=1),
                "cases": rows,
                "scope": "Exploratory stored-run comparison; no predeclared release approval. Exact reference match is not semantic fidelity.",
            }

    @router.get("/runs/{run_id}/evidence")
    def run_evidence(
        project_id: UUID,
        run_id: UUID,
        offset: int = Query(0, ge=0),
        limit: int = Query(40, ge=1, le=100),
    ) -> dict:
        with connect(settings) as db:
            run = db.execute(
                "SELECT r.*,m.requested_model,m.model_version FROM run r JOIN model_configuration m ON m.id=r.model_config_id WHERE r.id=%s AND r.project_id=%s",
                (run_id, project_id),
            ).fetchone()
            if not run:
                raise DomainError("NOT_FOUND", "Run not found", 404)
            scorer = db.execute(
                "SELECT id FROM scoring_run WHERE run_id=%s AND state='COMPLETED' ORDER BY created_at DESC,id DESC LIMIT 1",
                (run_id,),
            ).fetchone()
            metrics = []
            if scorer:
                metrics = db.execute(
                    "SELECT dimension,count(*) FILTER(WHERE status='VALUE') AS scored,count(*) AS stored,avg(value) FILTER(WHERE status='VALUE') AS mean FROM metric_result WHERE scoring_run_id=%s GROUP BY dimension ORDER BY dimension",
                    (scorer["id"],),
                ).fetchall()
            rows = db.execute(
                "SELECT i.id,i.case_revision_id,i.repetition_index,i.state,c.stable_key,o.normalized_text,o.finish_reason FROM run_item i JOIN case_revision cr ON cr.id=i.case_revision_id JOIN case_item c ON c.id=cr.case_item_id LEFT JOIN response o ON o.run_item_id=i.id WHERE i.run_id=%s ORDER BY c.stable_key,i.repetition_index LIMIT %s OFFSET %s",
                (run_id, limit, offset),
            ).fetchall()
            total = db.execute(
                "SELECT count(*) AS n FROM run_item WHERE run_id=%s", (run_id,)
            ).fetchone()["n"]
            return {
                "run": run,
                "metrics": metrics,
                "items": rows,
                "total": total,
                "offset": offset,
                "limit": limit,
                "scope": "Descriptive response-weighted means; not independent-sample estimates or semantic quality scores.",
            }

    return router


LANGUAGE_SQL = "CASE WHEN c.input_profile->>'mixing'<>'none' THEN 'code-switch' WHEN c.input_profile->>'romanization' IS NOT NULL THEN 'manglish' WHEN c.input_profile->'languages' ? 'ml' THEN 'ml' ELSE 'en' END"
