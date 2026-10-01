"""Idempotent local onboarding. Creates no human labels or scientific model results."""

import json
from pathlib import Path

from adriva.config import Settings
from adriva.db.connection import connect
from adriva.db.migrate import migrate
from adriva.domain.benchmarks import create_project, import_benchmark, publish_release
from adriva.domain.contracts import BenchmarkImport
from adriva.domain.runs import create_run, register_model
from adriva.evaluation.service import score_run
from adriva.gateway.contracts import ModelConfig
from adriva.workers.runner import run_once

ROOT = Path(__file__).resolve().parents[1]


def main():
    settings = Settings()
    migrate(settings)
    created = []
    for slug, title, file, fixture in [
        (
            "engineering",
            "Engineering verification",
            "fixtures/product-0.1.0.json",
            True,
        ),
        (
            "research",
            "ADRIVA research workspace",
            "pilot/adriva-bench-0.1.0.json",
            False,
        ),
    ]:
        with connect(settings) as db:
            if db.execute("SELECT id FROM project WHERE slug=%s", (slug,)).fetchone():
                continue
            project = create_project(db, title, slug)
            batch = BenchmarkImport.model_validate_json(
                (ROOT / "benchmarks" / file).read_text(encoding="utf-8")
            )
            release = import_benchmark(db, project, batch)
            if fixture:
                publish_release(db, project, release)
                for version, response in [
                    ("constant-250", "250"),
                    (
                        "constraint-violation",
                        "Engineering test response intentionally longer than the instruction limit.",
                    ),
                ]:
                    model = register_model(
                        db,
                        project,
                        ModelConfig(
                            provider="fixture",
                            requested_model="Deterministic fixture",
                            model_version=version,
                            usage_class="FIXTURE",
                            parameters={"fixture_text": response},
                        ),
                    )
                    created.append((project, create_run(db, project, release, model)))
    while run_once(settings):
        pass
    for project, run in created:
        with connect(settings) as db:
            score_run(db, project, run)
    print(
        json.dumps(
            {
                "created_fixture_runs": len(created),
                "human_labels_created": 0,
                "scientific_runs_created": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
