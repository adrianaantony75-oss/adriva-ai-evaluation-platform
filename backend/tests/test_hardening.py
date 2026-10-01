import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from uuid import uuid4

import pytest
from adriva.api.app import create_app
from adriva.config import Settings
from adriva.db.connection import connect
from adriva.domain.contracts import BenchmarkImport
from adriva.domain.validation import validate_import
from adriva.gateway.compatible import CompatibleAdapter
from adriva.gateway.contracts import AdapterError, GenerationRequest, ModelConfig
from adriva.workers.runner import run_once
from fastapi.testclient import TestClient


def test_request_security_and_response_headers():
    with TestClient(create_app(Settings(environment="test"))) as client:
        assert (
            client.get("/api/v1/health/live", headers={"host": "attacker.example"}).status_code
            == 400
        )
        assert (
            client.post(
                "/api/v1/projects", headers={"origin": "https://attacker.example"}, json={}
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/v1/projects", headers={"sec-fetch-site": "cross-site"}, json={}
            ).status_code
            == 403
        )
        response = client.get("/")
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "script-src 'self'" in response.headers["content-security-policy"]


def test_seed_benchmark_validity():
    root = Path(__file__).resolve().parents[2]
    pilot = BenchmarkImport.model_validate_json(
        (root / "benchmarks/pilot/adriva-bench-0.1.0.json").read_text(encoding="utf-8")
    )
    assert not validate_import(pilot)
    assert len(pilot.cases) == 24
    assert len({c.family_key for c in pilot.cases}) == 6
    assert len({c.task for c in pilot.cases}) == 6
    assert all(c.usage == "PILOT" and c.origin == "SYNTHETIC" for c in pilot.cases)
    assert sum(c.derivation is not None for c in pilot.cases) == 18
    assert all(
        any("\u0d00" <= char <= "\u0d7f" for char in c.prompt)
        for c in pilot.cases
        if c.input_profile.script in ("Malayalam", "mixed")
    )


def test_two_distinct_content_reviewers_required(settings, batch):
    # All submissions here are isolated database test records, never user evidence.
    case = batch.cases[0].model_copy(deep=True)
    case.usage = "PILOT"
    case.creator_ref = "TEST-ONLY"
    case.generator_metadata = {"generator": "fixture", "version": "1", "prompt_digest": "0" * 64}
    batch.cases = [case]
    with TestClient(create_app(settings)) as client:
        project = client.post(
            "/api/v1/projects", json={"name": "Quorum test", "slug": "quorum"}
        ).json()["id"]
        base = f"/api/v1/projects/{project}"
        release = client.post(
            base + "/benchmarks/import", json=batch.model_dump(mode="json")
        ).json()["release_id"]
        case_id = client.get(base + "/cases").json()["items"][0]["id"]
        payload = {
            "reviewer_name": "TEST reviewer A",
            "review_kind": "CONTENT",
            "verdict": "VERIFIED",
            "rationale": "Isolated integration test; not a genuine human judgment.",
            "human_attestation": True,
        }
        for _ in range(2):
            assert (
                client.post(base + f"/cases/{case_id}/content-review", json=payload).status_code
                == 201
            )
        assert client.post(base + f"/releases/{release}/publish").status_code == 409
        assert len(client.get(base + "/quality").json()["pending_content_review"]) == 1
        assert (
            client.post(
                base + f"/cases/{case_id}/content-review",
                json={**payload, "reviewer_name": "TEST reviewer B"},
            ).status_code
            == 201
        )
        assert client.get(base + "/quality").json()["pending_content_review"] == []
        assert client.post(base + f"/releases/{release}/publish").status_code == 200
        assert (
            client.post(base + f"/cases/{case_id}/content-review", json=payload).status_code == 409
        )


def test_content_review_gate_and_deterministic_findings(settings):
    root = Path(__file__).resolve().parents[2]
    with TestClient(create_app(settings)) as client:
        project = client.post(
            "/api/v1/projects", json={"name": "Hardening", "slug": "hardening"}
        ).json()["id"]
        base = f"/api/v1/projects/{project}"
        batch = json.loads(
            (root / "benchmarks/pilot/adriva-bench-0.1.0.json").read_text(encoding="utf-8")
        )
        release = client.post(base + "/benchmarks/import", json=batch).json()["release_id"]
        assert client.post(base + f"/releases/{release}/publish").status_code == 409
        case = client.get(base + "/cases").json()["items"][0]["id"]
        payload = {
            "reviewer_name": "TEST FIXTURE reviewer",
            "review_kind": "CONTENT",
            "verdict": "REVIEW_REQUIRED",
            "rationale": "TEST ONLY: request a qualified native-speaker review.",
            "human_attestation": True,
        }
        assert (
            client.post(
                base + f"/cases/{case}/content-review", json={**payload, "human_attestation": False}
            ).status_code
            == 422
        )
        assert client.post(base + f"/cases/{case}/content-review", json=payload).status_code == 201
        assert client.post(base + f"/releases/{release}/publish").status_code == 409
        batch = json.loads(
            (root / "benchmarks/fixtures/product-0.1.0.json").read_text(encoding="utf-8")
        )
        project2 = client.post(
            "/api/v1/projects", json={"name": "Fixtures", "slug": "fixtures"}
        ).json()["id"]
        base2 = f"/api/v1/projects/{project2}"
        release = client.post(base2 + "/benchmarks/import", json=batch).json()["release_id"]
        assert client.post(base2 + f"/releases/{release}/publish").status_code == 200
        model = client.post(
            base2 + "/models",
            json={
                "provider": "fixture",
                "requested_model": "fixture",
                "model_version": "1",
                "usage_class": "FIXTURE",
                "parameters": {"fixture_text": "invalid long fixture output"},
            },
        ).json()["model_id"]
        run = client.post(base2 + "/runs", json={"release_id": release, "model_id": model}).json()[
            "run_id"
        ]
        while run_once(settings):
            pass
        for _ in range(2):
            assert client.post(base2 + f"/runs/{run}/score").status_code == 201
        evidence = client.get(base2 + f"/runs/{run}/evidence").json()
        assert evidence["total"] == 24 and len(evidence["items"]) == 24
        assert evidence["metrics"]
        assert client.get(base + f"/runs/{run}/evidence").status_code == 404
        findings = client.get(base2 + "/failures?include_fixtures=true").json()
        assert (
            findings["total"] == 8
        )  # Four schema violations, four length violations; rescore deduplicates.
        assert all(
            f["origin_kind"] == "DETERMINISTIC" and f["verification_state"] == "CONFIRMED"
            for f in findings["items"]
        )
        assert client.get(base2 + "/failures").json()["total"] == 0
        with connect(settings) as db:
            assert db.execute("SELECT count(*) AS n FROM judgment").fetchone()["n"] == 0


@pytest.mark.parametrize("kind", ["success", "redirect", "malformed", "rate_limit"])
def test_gateway_real_http_transport(monkeypatch, kind):
    """Local HTTP protocol stub, NOT an AI model or real provider result."""
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            seen.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            if kind == "redirect":
                self.send_response(302)
                self.send_header("Location", "https://example.invalid/credential-leak")
                self.end_headers()
                return
            if kind == "rate_limit":
                self.send_response(429)
                self.end_headers()
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {
                        "model": "http-test-stub",
                        "choices": [
                            {
                                "message": {"content": "fixture transport response"},
                                "finish_reason": "stop",
                            }
                        ],
                    }
                    if kind == "success"
                    else {"bad": "schema"}
                ).encode()
            )

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv(
        "ADRIVA_ENDPOINT_TEST", f"http://127.0.0.1:{server.server_port}/chat/completions"
    )
    adapter = CompatibleAdapter()
    adapter.validate(
        ModelConfig(
            provider="openai_compatible",
            requested_model="test-stub",
            model_version="1",
            usage_class="REAL",
            endpoint_ref="ADRIVA_ENDPOINT_TEST",
            parameters={"temperature": 0},
        )
    )
    try:
        request = GenerationRequest(
            logical_request_id=uuid4(),
            prompt="transport fixture",
            context="source fixture",
            parameters={},
        )
        if kind == "success":
            assert adapter.generate(request).text == "fixture transport response"
            assert (
                seen[0]["messages"][0]["content"] == "Context:\nsource fixture\n\ntransport fixture"
            )
        else:
            with pytest.raises(AdapterError) as error:
                adapter.generate(request)
            assert (
                error.value.code
                == {
                    "redirect": "PROVIDER_REDIRECT_REJECTED",
                    "malformed": "PROVIDER_SCHEMA_ERROR",
                    "rate_limit": "PROVIDER_HTTP_429",
                }[kind]
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
