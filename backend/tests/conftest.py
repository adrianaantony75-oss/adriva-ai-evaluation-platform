import os
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from adriva.config import Settings
from adriva.db.connection import connect
from adriva.db.migrate import migrate
from adriva.domain.benchmarks import create_project
from adriva.domain.contracts import BenchmarkImport
from psycopg import sql
from pydantic import SecretStr


@pytest.fixture
def batch() -> BenchmarkImport:
    path = Path(__file__).resolve().parents[2] / "benchmarks/fixtures/engineering-v1.json"
    return BenchmarkImport.model_validate_json(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def database_settings(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    url = os.environ.get("ADRIVA_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set ADRIVA_TEST_DATABASE_URL for PostgreSQL integration tests")
    if not urlparse(url).path.endswith("_test"):
        pytest.fail("Destructive tests require an explicitly named *_test database")
    settings = Settings(
        database_url=SecretStr(url),
        environment="test",
        artifact_root=tmp_path_factory.mktemp("artifacts"),
    )
    migrate(settings)
    return settings


@pytest.fixture
def settings(database_settings: Settings) -> Settings:
    # Reset only the explicitly isolated test DB, keeping migration history.
    with connect(database_settings) as db:
        names = [
            r["tablename"]
            for r in db.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'schema_migration'"
            )
        ]
        db.execute(
            sql.SQL("TRUNCATE {} CASCADE").format(
                sql.SQL(",").join(sql.Identifier(n) for n in names)
            )
        )
        # Taxonomy is definition data; reseed after test reset without rerunning migration history.
        from adriva.db.migrate import migrations

        seed = (
            migrations()[2][1]
            .split("INSERT INTO failure_label")[1]
            .split("CREATE TABLE failure_finding")[0]
        )
        db.execute("INSERT INTO failure_label" + seed)
    return database_settings


@pytest.fixture
def project_id(settings: Settings):
    with connect(settings) as db:
        return create_project(db, "Fixture project", "fixture-" + str(uuid4())[:8])
