from importlib.resources import files
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb

from adriva.domain.contracts import ExpectedContract
from adriva.domain.hashing import digest
from adriva.errors import DomainError
from adriva.evaluation.deterministic import evaluate


def score_run(db: psycopg.Connection, project_id: UUID, run_id: UUID) -> UUID:
    run = db.execute(
        "SELECT * FROM run WHERE id=%s AND project_id=%s FOR UPDATE", (run_id, project_id)
    ).fetchone()
    if not run:
        raise DomainError("NOT_FOUND", "Run not found", 404)
    if run["state"] not in {"COMPLETED", "PARTIAL", "FAILED", "CANCELLED"}:
        raise DomainError("RUN_ACTIVE", "Score a terminal run snapshot", 409)
    root = files("adriva.evaluation")
    source_digest = digest(
        {
            name: root.joinpath(name).read_text(encoding="utf-8")
            for name in ("deterministic.py", "schema.py")
        }
    )
    version = "1-" + source_digest[:12]
    scorer = db.execute(
        "SELECT id FROM scorer_revision WHERE project_id=%s AND name='deterministic' AND version=%s",
        (project_id, version),
    ).fetchone()
    scorer_id = scorer["id"] if scorer else uuid4()
    if not scorer:
        db.execute(
            "INSERT INTO scorer_revision(id,project_id,name,version,code_digest,config,direction) VALUES (%s,%s,'deterministic',%s,%s,%s,'HIGHER')",
            (
                scorer_id,
                project_id,
                version,
                source_digest,
                Jsonb({"normalizer": "NFC-strip-v1", "semantic_claim": False}),
            ),
        )
    scoring_id = uuid4()
    protocol = digest({"version": "deterministic-v1", "scorer": source_digest})
    db.execute(
        "INSERT INTO scoring_run(id,project_id,run_id,scorer_set_digest,protocol_digest,state) VALUES (%s,%s,%s,%s,%s,'RUNNING')",
        (scoring_id, project_id, run_id, source_digest, protocol),
    )
    outputs = db.execute(
        "SELECT o.id,c.expected_contract FROM response o JOIN run_item i ON i.id=o.run_item_id JOIN case_revision c ON c.id=i.case_revision_id WHERE i.run_id=%s",
        (run_id,),
    ).fetchall()
    for output in outputs:
        text = db.execute(
            "SELECT normalized_text FROM response WHERE id=%s", (output["id"],)
        ).fetchone()["normalized_text"]
        contract = ExpectedContract.model_validate(output["expected_contract"])
        for metric in evaluate(text, contract):
            db.execute(
                "INSERT INTO metric_result(id,project_id,scoring_run_id,response_id,scorer_revision_id,dimension,status,value,unit,evidence) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'proportion',%s)",
                (
                    uuid4(),
                    project_id,
                    scoring_id,
                    output["id"],
                    scorer_id,
                    metric.dimension,
                    metric.status,
                    metric.value,
                    Jsonb(metric.evidence),
                ),
            )
            # Only executable constraints produce confirmed automatic findings.
            # Exact-match differences must never become semantic failure claims.
            labels = {"schema_valid": "FORMAT_FAILURE", "character_limit": "INSTRUCTION_DRIFT"}
            if metric.status == "VALUE" and metric.value == 0 and metric.dimension in labels:
                prior = db.execute(
                    "SELECT id FROM failure_finding WHERE response_id=%s AND origin_kind='DETERMINISTIC' AND evidence->>'dimension'=%s AND evidence->>'scorer_digest'=%s",
                    (output["id"], metric.dimension, source_digest),
                ).fetchone()
                if not prior:
                    finding_id = uuid4()
                    db.execute(
                        "INSERT INTO failure_finding(id,project_id,response_id,severity,origin_kind,verification_state,evidence) VALUES(%s,%s,%s,'MAJOR','DETERMINISTIC','CONFIRMED',%s)",
                        (
                            finding_id,
                            project_id,
                            output["id"],
                            Jsonb(
                                {
                                    "dimension": metric.dimension,
                                    "scorer_digest": source_digest,
                                    "rationale": "Executable output constraint failed",
                                    "metric_evidence": metric.evidence,
                                }
                            ),
                        ),
                    )
                    db.execute(
                        "INSERT INTO finding_label(finding_id,code,taxonomy_version) VALUES(%s,%s,'1')",
                        (finding_id, labels[metric.dimension]),
                    )
    db.execute("UPDATE scoring_run SET state='COMPLETED' WHERE id=%s", (scoring_id,))
    return scoring_id
