"""End-to-end product contracts against disposable PostgreSQL; all ratings are FIXTURE."""

from uuid import uuid4

from adriva.api.app import create_app
from adriva.evaluation.human import DIMENSIONS
from adriva.workers.runner import run_once
from fastapi.testclient import TestClient


def test_product_run_compare_review_and_failure_workflow(settings, batch):
    with TestClient(create_app(settings)) as client:
        assert client.get("/").status_code == 200
        assert "ADRIVA" in client.get("/").text
        project = client.post(
            "/api/v1/projects", json={"name": "Product fixture", "slug": "product-fixture"}
        ).json()["id"]
        root = f"/api/v1/projects/{project}"
        release = client.post(
            root + "/benchmarks/import", json=batch.model_dump(mode="json")
        ).json()["release_id"]
        assert client.post(root + f"/releases/{release}/publish").status_code == 200
        runs = []
        for version, text in [("A", "250"), ("B", "wrong fixture response")]:
            model = client.post(
                root + "/models",
                json={
                    "provider": "fixture",
                    "requested_model": "fixture",
                    "model_version": version,
                    "usage_class": "FIXTURE",
                    "parameters": {"fixture_text": text},
                },
            )
            assert model.status_code == 201, model.text
            run = client.post(
                root + "/runs", json={"release_id": release, "model_id": model.json()["model_id"]}
            ).json()["run_id"]
            while run_once(settings):
                pass
            assert client.post(root + f"/runs/{run}/score").status_code == 201
            runs.append(run)
        workspace = client.get(root + "/workspace?include_fixtures=true")
        assert workspace.status_code == 200, workspace.text
        assert len(workspace.json()["runs"]) == 2
        assert client.get(root + "/workspace").json()["totals"]["cases"] == 0
        cases = client.get(root + "/cases?include_fixtures=true").json()
        assert cases["total"] == 4
        assert (
            client.get(root + "/cases?include_fixtures=true&language=manglish").json()["total"] == 1
        )
        assert len(client.get(root + "/language-matrix?include_fixtures=true").json()) == 4
        comparison = client.get(root + f"/comparison?baseline={runs[0]}&candidate={runs[1]}")
        assert comparison.status_code == 200, comparison.text
        assert comparison.json()["analysis"]["decision"] == "HOLD"
        assert comparison.json()["analysis"]["observed_pairs"] == 4
        study = client.post(
            root + "/review-studies",
            json={
                "baseline": runs[0],
                "candidate": runs[1],
                "reviewers": ["Fixture reviewer one", "Fixture reviewer two"],
            },
        )
        assert study.status_code == 201, study.text
        queue = client.get(root + "/review-queue").json()
        assert len(queue) == 8
        assignment = queue[0]["id"]
        detail = client.get(root + f"/review-queue/{assignment}").json()
        assert "baseline_response_id" not in detail and "requested_model" not in detail
        payload = {
            "assignment_id": assignment,
            "reviewer_ref": detail["reviewer_id"],
            "rubric_digest": detail["rubric_digest"],
            "preference": "TIE",
            "rationale": "TEST FIXTURE ONLY",
            "data_origin": "TEST_FIXTURE",
            "ratings": [
                {
                    "slot": slot,
                    "dimension": dimension,
                    "status": "CANNOT_JUDGE",
                    "value": None,
                    "rationale": "TEST FIXTURE ONLY",
                }
                for slot in ("A", "B")
                for dimension in DIMENSIONS
            ],
        }
        assert (
            client.post(
                root + f"/review-queue/{assignment}",
                json={**payload, "data_origin": "ACTUAL_HUMAN"},
            ).status_code
            == 409
        )
        submitted = client.post(root + f"/review-queue/{assignment}", json=payload)
        assert submitted.status_code == 201, submitted.text
        assert client.post(root + f"/review-queue/{assignment}", json=payload).status_code == 409
        assert client.get(root + "/annotation-qa").json()["ratings"] == 0
        qa = client.get(root + "/annotation-qa?include_fixtures=true").json()
        assert qa["ratings"] == 1 and qa["studies"][0]["agreement"]["alpha"] is None
        case = client.get(root + f"/cases/{cases['items'][0]['id']}").json()
        finding = client.post(
            root + "/findings",
            json={
                "response_id": case["responses"][0]["id"],
                "label": "MEANING_DRIFT",
                "rationale": "TEST FIXTURE proposed finding",
            },
        )
        assert finding.status_code == 201, finding.text
        assert client.get(root + "/failures").json()["total"] == 0
        assert (
            client.get(root + "/failures?include_fixtures=true&label=MEANING_DRIFT").json()["total"]
            == 1
        )
        assert client.get(root + "/quality").status_code == 200
        assert client.get(f"/api/v1/projects/{uuid4()}/cases/{case['id']}").status_code == 404
