from uuid import uuid4

import psycopg
import pytest
from adriva.db.connection import connect
from adriva.domain.benchmarks import import_benchmark, publish_release
from adriva.domain.runs import cancel_run, create_run, register_model
from adriva.errors import DomainError
from adriva.evaluation.service import score_run
from adriva.gateway.contracts import GenerationRequest, ModelConfig
from adriva.gateway.fixture import FixtureAdapter
from adriva.storage.local import LocalArtifactStore
from adriva.workers.runner import claim, complete, run_once

pytestmark = pytest.mark.integration


@pytest.fixture
def registered(settings, project_id, batch):
    with connect(settings) as db:
        release = import_benchmark(db, project_id, batch)
        publish_release(db, project_id, release)
        config = ModelConfig(
            provider="fixture",
            requested_model="offline-fixture",
            model_version="1",
            usage_class="FIXTURE",
            parameters={"fixture_text": "250"},
        )
        model = register_model(db, project_id, config)
        assert model == register_model(db, project_id, config)
        run = create_run(db, project_id, release, model)
    return release, model, run


def test_full_fixture_run_and_scoring(settings, project_id, registered) -> None:
    run = registered[2]
    assert sum(run_once(settings) for _ in range(5)) == 4
    with connect(settings) as db:
        state = db.execute("SELECT * FROM v_run_completion WHERE run_id=%s", (run,)).fetchone()
        assert (
            state["state"] == "COMPLETED"
            and state["succeeded"] == 4
            and state["usage_class"] == "FIXTURE"
        )
        scoring = score_run(db, project_id, run)
        metrics = db.execute(
            "SELECT * FROM metric_result WHERE scoring_run_id=%s", (scoring,)
        ).fetchall()
        assert len(metrics) == 4 and all(m["value"] == 1 for m in metrics)
        assert db.execute("SELECT count(*) AS n FROM execution_attempt").fetchone()["n"] == 4
        row = db.execute("SELECT * FROM response LIMIT 1").fetchone()
        with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
            db.execute("UPDATE response SET normalized_text='rewritten' WHERE id=%s", (row["id"],))
        a = db.execute("SELECT * FROM artifact LIMIT 1").fetchone()
        raw = LocalArtifactStore(settings.artifact_root).read(a["storage_key"], a["content_hash"])
        assert b'"request"' in raw and b'"FIXTURE"' in raw


def test_two_claims_skip_locked(settings, registered) -> None:
    with connect(settings) as first, connect(settings) as second:
        a = claim(first, "worker-A")
        b = claim(second, "worker-B")
        assert a and b and a["id"] != b["id"]


def test_expired_lease_fences_old_worker(settings, registered) -> None:
    with connect(settings) as db:
        stale = claim(db, "old")
        db.execute(
            "UPDATE job SET lease_until=now()-interval '1 second',available_at=now()-interval '1 hour' WHERE id=%s",
            (stale["id"],),
        )
    with connect(settings) as db:
        current = claim(db, "new")
        assert current["id"] == stale["id"] and current["lease_token"] != stale["lease_token"]
        request = GenerationRequest(
            logical_request_id=stale["run_item_id"],
            prompt="fixture",
            context="fixture",
            parameters={"fixture_text": "250"},
        )
        result = FixtureAdapter().generate(request)
        assert not complete(db, stale, result, LocalArtifactStore(settings.artifact_root), request)
        assert complete(db, current, result, LocalArtifactStore(settings.artifact_root), request)
        assert (
            db.execute(
                "SELECT count(*) AS n FROM response WHERE run_item_id=%s", (stale["run_item_id"],)
            ).fetchone()["n"]
            == 1
        )


def test_cancel_fences_active_work(settings, project_id, registered) -> None:
    with connect(settings) as db:
        pending = claim(db, "cancelled-worker")
    with connect(settings) as db:
        cancel_run(db, project_id, registered[2])
    request = GenerationRequest(
        logical_request_id=pending["run_item_id"],
        prompt="fixture",
        context="",
        parameters={"fixture_text": "250"},
    )
    with connect(settings) as db:
        assert not complete(
            db,
            pending,
            FixtureAdapter().generate(request),
            LocalArtifactStore(settings.artifact_root),
            request,
        )
        assert claim(db, "new") is None
        assert db.execute("SELECT count(*) AS n FROM response").fetchone()["n"] == 0


def test_model_secret_fields_rejected(settings, project_id) -> None:
    config = ModelConfig(
        provider="future-provider",
        requested_model="model",
        model_version="v1",
        usage_class="REAL",
        parameters={"nested": {"api_key": "not-a-real-key"}},
    )
    with connect(settings) as db, pytest.raises(DomainError):
        register_model(db, project_id, config)


def test_run_manifest_constraint(settings, project_id, registered, batch) -> None:
    with connect(settings) as db:
        case = db.execute("SELECT id FROM case_revision LIMIT 1").fetchone()["id"]
        with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
            db.execute(
                "INSERT INTO run_item(id,project_id,run_id,case_revision_id,repetition_index,request_digest,state) VALUES (%s,%s,%s,%s,99,'fixture','PENDING')",
                (uuid4(), project_id, registered[2], case),
            )


def test_pair_view_matches_cases_and_versions(settings, project_id, registered) -> None:
    with connect(settings) as db:
        candidate = create_run(db, project_id, registered[0], registered[1])
    while run_once(settings):
        pass
    with connect(settings) as db:
        score_run(db, project_id, registered[2])
        score_run(db, project_id, candidate)
        rows = db.execute(
            "SELECT * FROM v_paired_metric WHERE baseline_run_id=%s AND candidate_run_id=%s",
            (registered[2], candidate),
        ).fetchall()
        assert len(rows) == 4 and all(r["baseline_value"] == r["candidate_value"] for r in rows)


def test_retryable_timeout_retains_attempt_without_response(settings, registered) -> None:
    from adriva.gateway.contracts import AdapterError

    with connect(settings) as db:
        pending = claim(db, "retry-worker")
        request = GenerationRequest(
            logical_request_id=pending["run_item_id"],
            prompt="fixture",
            context="",
            parameters={"fixture_text": "250"},
        )
        assert not complete(
            db,
            pending,
            None,
            LocalArtifactStore(settings.artifact_root),
            request,
            AdapterError("TIMEOUT", True),
        )
        job = db.execute(
            "SELECT state,attempt_count FROM job WHERE id=%s", (pending["id"],)
        ).fetchone()
        assert job["state"] == "PENDING" and job["attempt_count"] == 1
        attempt = db.execute(
            "SELECT outcome,error_class FROM execution_attempt WHERE id=%s",
            (pending["attempt_id"],),
        ).fetchone()
        assert attempt == {"outcome": "FAILED", "error_class": "TIMEOUT"}
        assert db.execute("SELECT count(*) AS n FROM response").fetchone()["n"] == 0


def test_expired_exhausted_job_becomes_failed(settings, registered) -> None:
    with connect(settings) as db:
        pending = claim(db, "lost-worker")
        db.execute(
            "UPDATE job SET lease_until=now()-interval '1 second',attempt_count=max_attempts WHERE id=%s",
            (pending["id"],),
        )
    with connect(settings) as db:
        claim(db, "recovery-worker")
        assert (
            db.execute("SELECT state FROM job WHERE id=%s", (pending["id"],)).fetchone()["state"]
            == "FAILED"
        )
        assert (
            db.execute(
                "SELECT state FROM run_item WHERE id=%s", (pending["run_item_id"],)
            ).fetchone()["state"]
            == "FAILED"
        )
