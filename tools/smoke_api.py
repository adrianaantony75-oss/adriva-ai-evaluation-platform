"""Explicit fixture-only end-to-end smoke against a running loopback API."""

import argparse
import json
from pathlib import Path
from uuid import uuid4

import httpx
from adriva.config import Settings
from adriva.workers.runner import run_once


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    if not args.url.startswith(("http://127.0.0.1:", "http://localhost:")):
        parser.error("Smoke script is restricted to local development")
    fixture = Path(__file__).resolve().parents[1] / "benchmarks/fixtures/engineering-v1.json"
    with httpx.Client(base_url=args.url, timeout=20) as client:

        def post(path: str, payload=None):
            result = client.post(path, json=payload)
            result.raise_for_status()
            return result.json()

        assert client.get("/api/v1/health/ready").status_code == 200
        project = post(
            "/api/v1/projects",
            {"name": "ENGINEERING SMOKE FIXTURE", "slug": "smoke-" + str(uuid4())[:8]},
        )["id"]
        prefix = f"/api/v1/projects/{project}"
        release = post(
            prefix + "/benchmarks/import",
            json.loads(fixture.read_text(encoding="utf-8")),
        )["release_id"]
        manifest = post(prefix + f"/releases/{release}/publish")["manifest_digest"]
        model = post(
            prefix + "/models",
            {
                "provider": "fixture",
                "requested_model": "offline-engineering-only",
                "model_version": "1",
                "usage_class": "FIXTURE",
                "parameters": {"fixture_text": "250"},
            },
        )["model_id"]
        run = post(prefix + "/runs", {"release_id": release, "model_id": model})["run_id"]
        while run_once(Settings(), owner="smoke-fixture-worker"):
            pass
        result = client.get(prefix + f"/runs/{run}").json()
        assert result["state"] == "COMPLETED" and result["succeeded"] == 4
        scoring = post(prefix + f"/runs/{run}/score")["scoring_run_id"]
        assert client.get(prefix + "/coverage").json() == []
        print(
            json.dumps(
                {
                    "usage_class": "FIXTURE",
                    "run_state": result["state"],
                    "items": result["succeeded"],
                    "manifest_digest": manifest,
                    "scoring_run_id": scoring,
                    "scientific_results": False,
                }
            )
        )


if __name__ == "__main__":
    main()
