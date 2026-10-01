from uuid import uuid4

import psycopg
import pytest
from adriva.db.connection import connect
from adriva.domain.benchmarks import import_benchmark, publish_release
from adriva.domain.runs import create_run, register_model
from adriva.gateway.contracts import ModelConfig
from adriva.workers.runner import run_once
from psycopg.types.json import Jsonb

pytestmark = pytest.mark.integration


def test_blind_view_rating_constraints_and_originals(settings, project_id, batch) -> None:
    with connect(settings) as db:
        release = import_benchmark(db, project_id, batch)
        publish_release(db, project_id, release)
        model = register_model(
            db,
            project_id,
            ModelConfig(
                provider="fixture",
                requested_model="fixture",
                model_version="1",
                usage_class="FIXTURE",
                parameters={"fixture_text": "250"},
            ),
        )
        first = create_run(db, project_id, release, model)
        second = create_run(db, project_id, release, model)
    while run_once(settings):
        pass
    with connect(settings) as db:
        pair = db.execute(
            "SELECT a.id AS a,b.id AS b,i.family_id FROM response a JOIN run_item ia ON ia.id=a.run_item_id JOIN case_revision c ON c.id=ia.case_revision_id JOIN case_item i ON i.id=c.case_item_id JOIN run_item ib ON ib.case_revision_id=ia.case_revision_id JOIN response b ON b.run_item_id=ib.id WHERE ia.run_id=%s AND ib.run_id=%s LIMIT 1",
            (first, second),
        ).fetchone()
        reviewer, rubric, study, unit, assignment, judgment = (uuid4() for _ in range(6))
        db.execute(
            "INSERT INTO user_account(id,external_subject,display_name) VALUES (%s,%s,'FIXTURE REVIEWER')",
            (reviewer, "fixture-" + str(reviewer)),
        )
        db.execute(
            "INSERT INTO rubric_revision(id,project_id,name,version,dimensions,digest) VALUES (%s,%s,'FIXTURE RUBRIC','1',%s,%s)",
            (rubric, project_id, Jsonb({"fixture_only": True}), "0" * 64),
        )
        db.execute(
            "INSERT INTO human_study(id,project_id,rubric_revision_id,protocol_digest,sampling_plan,state) VALUES (%s,%s,%s,%s,%s,'FROZEN')",
            (study, project_id, rubric, "0" * 64, Jsonb({"usage": "FIXTURE"})),
        )
        db.execute(
            "INSERT INTO comparison_unit(id,project_id,study_id,baseline_response_id,candidate_response_id,family_id,sample_kind) VALUES (%s,%s,%s,%s,%s,%s,'FIXTURE')",
            (unit, project_id, study, pair["a"], pair["b"], pair["family_id"]),
        )
        db.execute(
            "INSERT INTO assignment(id,project_id,comparison_unit_id,reviewer_id,state) VALUES (%s,%s,%s,%s,'ASSIGNED')",
            (assignment, project_id, unit, reviewer),
        )
        db.execute(
            "INSERT INTO assignment_mapping(assignment_id,project_id,a_response_id,b_response_id) VALUES (%s,%s,%s,%s)",
            (assignment, project_id, pair["b"], pair["a"]),
        )
        blind = db.execute(
            "SELECT * FROM v_blind_assignment WHERE assignment_id=%s", (assignment,)
        ).fetchone()
        assert not (
            {"a_response_id", "b_response_id", "model_config_id", "baseline_response_id"}
            & blind.keys()
        )
        db.execute(
            "INSERT INTO judgment(id,project_id,assignment_id,preference,rationale) VALUES (%s,%s,%s,'TIE','FIXTURE ONLY')",
            (judgment, project_id, assignment),
        )
        assert (
            db.execute(
                "SELECT n_reviewers FROM v_annotation_overlap WHERE comparison_unit_id=%s", (unit,)
            ).fetchone()["n_reviewers"]
            == 1
        )
        with pytest.raises(psycopg.errors.UniqueViolation), db.transaction():
            db.execute(
                "INSERT INTO judgment(id,project_id,assignment_id,preference,rationale) VALUES (%s,%s,%s,'A','FIXTURE ONLY')",
                (uuid4(), project_id, assignment),
            )
        with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
            db.execute("UPDATE judgment SET preference='A' WHERE id=%s", (judgment,))
        for value in (None, 0, 6):
            with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
                db.execute(
                    "INSERT INTO dimension_rating(id,project_id,judgment_id,response_slot,dimension,status,ordinal_value,evidence,rationale) VALUES (%s,%s,%s,'A','MEANING','RATED',%s,'{}','FIXTURE ONLY')",
                    (uuid4(), project_id, judgment, value),
                )
        with pytest.raises(psycopg.errors.ForeignKeyViolation), db.transaction():
            db.execute(
                "INSERT INTO finding_label(finding_id,code,taxonomy_version) VALUES (%s,'INVENTED_LABEL','1')",
                (uuid4(),),
            )
