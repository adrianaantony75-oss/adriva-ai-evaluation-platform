from uuid import uuid4

import psycopg
import pytest
from adriva.db.connection import connect
from adriva.db.migrate import migrate, ready
from adriva.domain.benchmarks import (
    create_project,
    export_benchmark,
    import_benchmark,
    publish_release,
)
from adriva.errors import DomainError
from psycopg.types.json import Jsonb

pytestmark = pytest.mark.integration


def test_migration_idempotence_and_checksum(settings) -> None:
    assert migrate(settings) == []
    assert ready(settings)
    with connect(settings) as db:
        db.execute(
            "UPDATE schema_migration SET checksum='invalid' WHERE version='001_benchmarks.sql'"
        )
    try:
        assert not ready(settings)
        with pytest.raises(RuntimeError):
            migrate(settings)
    finally:
        from adriva.db.migrate import migrations

        with connect(settings) as db:
            db.execute(
                "UPDATE schema_migration SET checksum=%s WHERE version='001_benchmarks.sql'",
                (migrations()[0][2],),
            )


def test_registry_publish_and_versions(settings, project_id, batch) -> None:
    with connect(settings) as db:
        release_id = import_benchmark(db, project_id, batch)
        frozen_hash = publish_release(db, project_id, release_id)
        assert frozen_hash == publish_release(db, project_id, release_id)
        assert len(frozen_hash) == 64
        assert db.execute("SELECT count(*) AS n FROM v_provenance_lineage").fetchone()["n"] == 5
        rows = db.execute(
            "SELECT sum(n_cases) AS n FROM v_benchmark_coverage WHERE release_id=%s", (release_id,)
        ).fetchone()
        assert rows["n"] == 4
        with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
            db.execute("UPDATE benchmark_release SET version='2.0.0' WHERE id=%s", (release_id,))
        with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
            db.execute("DELETE FROM release_case WHERE release_id=%s", (release_id,))
        with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
            db.execute("UPDATE case_revision SET prompt='changed'")
        with pytest.raises(DomainError), db.transaction():
            import_benchmark(db, project_id, batch)
        changed = batch.model_copy(deep=True)
        changed.version = "1.1.0"
        second = import_benchmark(db, project_id, changed)
        assert publish_release(db, project_id, second) != frozen_hash
        assert db.execute("SELECT count(*) AS n FROM case_revision").fetchone()["n"] == 4


def test_invalid_import_is_atomic(settings, project_id, batch) -> None:
    batch.cases[1].split = "evaluation"
    with pytest.raises(DomainError), connect(settings) as db:
        import_benchmark(db, project_id, batch)
    with connect(settings) as db:
        assert db.execute("SELECT count(*) AS n FROM benchmark").fetchone()["n"] == 0


def test_cross_project_foreign_key(settings, project_id, batch) -> None:
    with connect(settings) as db:
        release = import_benchmark(db, project_id, batch)
        other = create_project(db, "Other fixture", "other")
        case = db.execute("SELECT id FROM case_revision LIMIT 1").fetchone()["id"]
        with pytest.raises(psycopg.errors.ForeignKeyViolation), db.transaction():
            db.execute(
                "UPDATE release_case SET project_id=%s WHERE release_id=%s AND case_revision_id=%s",
                (other, release, case),
            )


def test_real_content_requires_real_review(settings, project_id, batch) -> None:
    for case in batch.cases:
        case.usage = "PILOT"
        case.creator_ref = "NEGATIVE-TEST-FIXTURE-AUTHOR"
        case.generator_metadata = {
            "generator": "engineering-only",
            "version": "1",
            "prompt_digest": "0" * 64,
        }
    with connect(settings) as db:
        release = import_benchmark(db, project_id, batch)
        with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
            publish_release(db, project_id, release)
        assert db.execute("SELECT count(*) AS n FROM case_review").fetchone()["n"] == 0
        assert (
            db.execute("SELECT DISTINCT creation_origin FROM case_revision").fetchone()[
                "creation_origin"
            ]
            == "SYNTHETIC"
        )


def test_db_split_leakage_and_frozen_sources(settings, project_id, batch) -> None:
    with connect(settings) as db:
        release = import_benchmark(db, project_id, batch)
        db.execute(
            "UPDATE release_case SET split='evaluation' WHERE release_id=%s AND ordinal=1",
            (release,),
        )
        with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
            publish_release(db, project_id, release)
        db.execute("UPDATE release_case SET split='development' WHERE release_id=%s", (release,))
        publish_release(db, project_id, release)
        source = db.execute("SELECT * FROM case_source LIMIT 1").fetchone()
        with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
            db.execute(
                "DELETE FROM case_source WHERE case_revision_id=%s", (source["case_revision_id"],)
            )


def test_case_revision_conflict(settings, project_id, batch) -> None:
    with connect(settings) as db:
        import_benchmark(db, project_id, batch)
        batch.version = "1.1.0"
        batch.cases[0].prompt = "New intent needs a new revision"
        with pytest.raises(DomainError), db.transaction():
            import_benchmark(db, project_id, batch)
        assert db.execute("SELECT count(*) AS n FROM benchmark_release").fetchone()["n"] == 1


def test_export_round_trip_and_parent_revision_guard(settings, project_id, batch) -> None:
    with connect(settings) as db:
        release = import_benchmark(db, project_id, batch)
        first_hash = publish_release(db, project_id, release)
        exported = export_benchmark(db, project_id, release)
        other = create_project(db, "Round-trip fixture", "round-trip")
        second = import_benchmark(db, other, exported)
        assert publish_release(db, other, second) == first_hash
        changed = batch.model_copy(deep=True)
        changed.version = "1.1.0"
        changed.cases[0].revision = 2
        changed.cases[0].prompt += " (new revision)"
        with pytest.raises(DomainError, match="Changed parent"), db.transaction():
            import_benchmark(db, project_id, changed)


def test_negative_review_veto_preserves_synthetic_origin(settings, project_id, batch) -> None:
    batch.cases = batch.cases[:1]
    case = batch.cases[0]
    case.usage = "PILOT"
    case.creator_ref = "NEGATIVE-TEST-FIXTURE"
    case.generator_metadata = {
        "generator": "fixture-only",
        "version": "1",
        "prompt_digest": "0" * 64,
    }
    with connect(settings) as db:
        release = import_benchmark(db, project_id, batch)
        reviewer, rubric = uuid4(), uuid4()
        db.execute(
            "INSERT INTO user_account(id,external_subject,display_name) VALUES (%s,%s,'FIXTURE REVIEWER')",
            (reviewer, str(reviewer)),
        )
        db.execute(
            "INSERT INTO rubric_revision(id,project_id,name,version,dimensions,digest) VALUES (%s,%s,'FIXTURE','1',%s,%s)",
            (rubric, project_id, Jsonb({"fixture_only": True}), "0" * 64),
        )
        revision = db.execute("SELECT id FROM case_revision LIMIT 1").fetchone()["id"]
        for verdict in ("VERIFIED", "REJECTED"):
            db.execute(
                "INSERT INTO case_review(id,project_id,case_revision_id,reviewer_id,rubric_revision_id,review_kind,verdict,rationale) VALUES (%s,%s,%s,%s,%s,'CONTENT',%s,'NEGATIVE TEST FIXTURE')",
                (uuid4(), project_id, revision, reviewer, rubric, verdict),
            )
        with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
            publish_release(db, project_id, release)
        assert (
            db.execute(
                "SELECT creation_origin FROM case_revision WHERE id=%s", (revision,)
            ).fetchone()["creation_origin"]
            == "SYNTHETIC"
        )
