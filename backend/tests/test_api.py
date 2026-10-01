from uuid import uuid4

from adriva.api.app import create_app
from adriva.config import Settings
from adriva.db.connection import connect
from fastapi.testclient import TestClient


def test_live_survives_database_outage() -> None:
    config = Settings(database_url="postgresql://unavailable@127.0.0.1:1/not_present")
    with TestClient(create_app(config), base_url="http://127.0.0.1") as client:
        assert client.get("/api/v1/health/live").status_code == 200
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 503 and "unavailable@" not in response.text


def test_safe_validation_errors() -> None:
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        response = client.post(
            "/api/v1/projects",
            json={"name": "fixture", "slug": "invalid!", "password": "PRIVATE-TEST-VALUE"},
        )
        assert response.status_code == 422 and "PRIVATE-TEST-VALUE" not in response.text
        assert response.headers["x-request-id"]


def test_registry_api_scope_and_fixture_filter(settings, batch) -> None:
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/health/ready").status_code == 200
        project = client.post(
            "/api/v1/projects", json={"name": "Fixture project", "slug": "fixture-api"}
        ).json()["id"]
        result = client.post(
            f"/api/v1/projects/{project}/benchmarks/import", json=batch.model_dump(mode="json")
        )
        assert result.status_code == 201, result.text
        release = result.json()["release_id"]
        assert (
            client.post(f"/api/v1/projects/{uuid4()}/releases/{release}/publish").status_code == 404
        )
        assert (
            client.post(f"/api/v1/projects/{project}/releases/{release}/publish").status_code == 200
        )
        exported = client.get(f"/api/v1/projects/{project}/releases/{release}/export")
        assert exported.status_code == 200 and exported.json()["cases"][0]["usage"] == "FIXTURE"
        assert client.get(f"/api/v1/projects/{project}/coverage").json() == []
        assert (
            len(client.get(f"/api/v1/projects/{project}/coverage?include_fixtures=true").json()) > 0
        )
        assert client.get(f"/api/v1/projects/{project}/releases?limit=999").status_code == 422
        with connect(settings) as db:
            assert db.execute("SELECT count(*) AS n FROM case_review").fetchone()["n"] == 0
