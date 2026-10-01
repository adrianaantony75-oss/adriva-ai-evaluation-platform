"""Local study administration and blind review; production identity is intentionally gated."""

from dataclasses import asdict
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter
from psycopg.types.json import Jsonb
from pydantic import Field

from adriva.config import Settings
from adriva.db.connection import connect
from adriva.domain.contracts import StrictModel
from adriva.domain.hashing import digest
from adriva.errors import DomainError
from adriva.evaluation.agreement import krippendorff_alpha
from adriva.evaluation.human import (
    DIMENSIONS,
    BlindPair,
    HumanSubmission,
    blind_assignments,
    canonical_choice,
)


class StudyInput(StrictModel):
    baseline: UUID
    candidate: UUID
    reviewers: list[str] = Field(min_length=1, max_length=5)
    seed: int = 1729


class FindingInput(StrictModel):
    response_id: UUID
    label: str
    rationale: str = Field(min_length=5, max_length=4000)


class ContentReviewInput(StrictModel):
    reviewer_name: str = Field(min_length=2, max_length=120)
    review_kind: Literal["CONTENT", "TRANSFORMATION"]
    verdict: Literal["VERIFIED", "REJECTED", "REVIEW_REQUIRED"]
    rationale: str = Field(min_length=20, max_length=4000)
    human_attestation: Literal[True]


def reviews_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects/{project_id}")

    @router.post("/cases/{case_id}/content-review", status_code=201)
    def content_review(project_id: UUID, case_id: UUID, payload: ContentReviewInput) -> dict:
        with connect(settings) as db:
            db.execute("SELECT id FROM project WHERE id=%s FOR UPDATE", (project_id,))
            case = db.execute(
                "SELECT usage_class FROM case_revision WHERE id=%s AND project_id=%s",
                (case_id, project_id),
            ).fetchone()
            if not case:
                raise DomainError("NOT_FOUND", "Case not found", 404)
            if case["usage_class"] == "FIXTURE":
                raise DomainError(
                    "FIXTURE_BOUNDARY",
                    "Engineering fixtures do not collect human content certification",
                    409,
                )
            if db.execute(
                "SELECT 1 FROM release_case rc JOIN benchmark_release r ON r.id=rc.release_id WHERE rc.case_revision_id=%s AND r.state='FROZEN'",
                (case_id,),
            ).fetchone():
                raise DomainError(
                    "FROZEN", "Create a new case revision to change frozen review evidence", 409
                )
            if (
                payload.review_kind == "TRANSFORMATION"
                and not db.execute(
                    "SELECT 1 FROM derivation_event WHERE child_revision_id=%s", (case_id,)
                ).fetchone()
            ):
                raise DomainError("NOT_DERIVED", "This case has no transformation to review", 422)
            name = payload.reviewer_name.strip()
            if len(name) < 2:
                raise DomainError("INVALID_REVIEWER", "A reviewer name is required", 422)
            subject = "local-content:" + str(project_id) + ":" + name.casefold()
            reviewer = db.execute(
                "SELECT id FROM user_account WHERE external_subject=%s", (subject,)
            ).fetchone()
            reviewer_id = reviewer["id"] if reviewer else uuid4()
            if not reviewer:
                db.execute(
                    "INSERT INTO user_account(id,external_subject,display_name) VALUES(%s,%s,%s)",
                    (reviewer_id, subject, name),
                )
                db.execute(
                    "INSERT INTO membership(project_id,user_id,role) VALUES(%s,%s,'REVIEWER')",
                    (project_id, reviewer_id),
                )
            rubric = db.execute(
                "SELECT id FROM rubric_revision WHERE project_id=%s AND name='content-review' AND version='1'",
                (project_id,),
            ).fetchone()
            rubric_id = rubric["id"] if rubric else uuid4()
            if not rubric:
                definition = [
                    "task validity",
                    "reference validity",
                    "natural language",
                    "transformation equivalence",
                ]
                db.execute(
                    "INSERT INTO rubric_revision(id,project_id,name,version,dimensions,digest) VALUES(%s,%s,'content-review','1',%s,%s)",
                    (rubric_id, project_id, Jsonb(definition), digest(definition)),
                )
            review_id = uuid4()
            db.execute(
                "INSERT INTO case_review(id,project_id,case_revision_id,reviewer_id,rubric_revision_id,review_kind,verdict,rationale) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    review_id,
                    project_id,
                    case_id,
                    reviewer_id,
                    rubric_id,
                    payload.review_kind,
                    payload.verdict,
                    payload.rationale,
                ),
            )
            db.execute(
                "INSERT INTO audit_event(id,project_id,action,target_id) VALUES(%s,%s,'CONTENT_REVIEW_SUBMITTED',%s)",
                (uuid4(), project_id, review_id),
            )
            return {"review_id": review_id, "identity_status": "LOCAL_SELF_ATTESTED"}

    @router.post("/review-studies", status_code=201)
    def create_study(project_id: UUID, payload: StudyInput) -> dict:
        names = [name.strip() for name in payload.reviewers]
        if (
            any(not n or len(n) > 120 for n in names)
            or len(set(names)) != len(names)
            or payload.baseline == payload.candidate
        ):
            raise DomainError("INVALID_STUDY", "Distinct reviewers and runs are required", 422)
        with connect(settings) as db:
            runs = db.execute(
                "SELECT * FROM run WHERE project_id=%s AND id IN (%s,%s)",
                (project_id, payload.baseline, payload.candidate),
            ).fetchall()
            if (
                len(runs) != 2
                or len({r["release_id"] for r in runs}) != 1
                or len({r["protocol_digest"] for r in runs}) != 1
            ):
                raise DomainError(
                    "INCOMPARABLE",
                    "Study requires matched project runs and generation protocol",
                    409,
                )
            rows = db.execute(
                "SELECT a.id AS a_id,b.id AS b_id,a.normalized_text AS a_text,b.normalized_text AS b_text,c.prompt,c.context,f.id AS family,c.input_profile FROM response a JOIN run_item i ON i.id=a.run_item_id JOIN run_item j ON j.case_revision_id=i.case_revision_id AND j.repetition_index=i.repetition_index AND j.run_id=%s JOIN response b ON b.run_item_id=j.id JOIN case_revision c ON c.id=i.case_revision_id JOIN case_item ci ON ci.id=c.case_item_id JOIN intent_family f ON f.id=ci.family_id WHERE i.run_id=%s ORDER BY i.case_revision_id,i.repetition_index LIMIT 201",
                (payload.candidate, payload.baseline),
            ).fetchall()
            if not rows or len(rows) > 200:
                raise DomainError(
                    "STUDY_SIZE", "Study needs 1–200 completed matched response pairs", 409
                )
            fixture = any(r["usage_class"] == "FIXTURE" for r in runs)
            rubric = db.execute(
                "SELECT id,digest FROM rubric_revision WHERE project_id=%s AND name='ADRIVA-human' AND version='1'",
                (project_id,),
            ).fetchone()
            if not rubric:
                rubric = {
                    "id": uuid4(),
                    "digest": digest({"version": "human-1", "dimensions": DIMENSIONS}),
                }
                db.execute(
                    "INSERT INTO rubric_revision(id,project_id,name,version,dimensions,digest) VALUES(%s,%s,'ADRIVA-human','1',%s,%s)",
                    (rubric["id"], project_id, Jsonb(list(DIMENSIONS)), rubric["digest"]),
                )
            study = uuid4()
            db.execute(
                "INSERT INTO human_study(id,project_id,rubric_revision_id,protocol_digest,sampling_plan,state) VALUES(%s,%s,%s,%s,%s,'FROZEN')",
                (
                    study,
                    project_id,
                    rubric["id"],
                    digest(
                        {
                            "seed": payload.seed,
                            "baseline": str(payload.baseline),
                            "candidate": str(payload.candidate),
                        }
                    ),
                    Jsonb(
                        {
                            "kind": "FIXTURE" if fixture else "DIAGNOSTIC",
                            "seed": payload.seed,
                            "population_claim": False,
                            "qualification": "not certified by local enrollment",
                        }
                    ),
                ),
            )
            pairs = []
            for row in rows:
                pair_id = uuid4()
                db.execute(
                    "INSERT INTO comparison_unit(id,project_id,study_id,baseline_response_id,candidate_response_id,family_id,sample_kind) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                    (
                        pair_id,
                        project_id,
                        study,
                        row["a_id"],
                        row["b_id"],
                        row["family"],
                        "FIXTURE" if fixture else "DIAGNOSTIC",
                    ),
                )
                pairs.append(
                    BlindPair(
                        str(pair_id),
                        str(row["input_profile"]),
                        row["prompt"],
                        row["context"],
                        str(row["a_id"]),
                        row["a_text"],
                        str(row["b_id"]),
                        row["b_text"],
                    )
                )
            for index, name in enumerate(names):
                reviewer = uuid4()
                # Explicit local identity; no claim of authentication or language qualification.
                db.execute(
                    "INSERT INTO user_account(id,external_subject,display_name) VALUES(%s,%s,%s)",
                    (reviewer, "local-study:" + str(study) + ":" + str(index), name),
                )
                db.execute(
                    "INSERT INTO membership(project_id,user_id,role) VALUES(%s,%s,'REVIEWER')",
                    (project_id, reviewer),
                )
                _, mappings = blind_assignments(pairs, seed=payload.seed + index)
                for assignment, mapping in mappings.items():
                    db.execute(
                        "INSERT INTO assignment(id,project_id,comparison_unit_id,reviewer_id,state) VALUES(%s,%s,%s,%s,'ASSIGNED')",
                        (assignment, project_id, mapping["pair_id"], reviewer),
                    )
                    db.execute(
                        "INSERT INTO assignment_mapping(assignment_id,project_id,a_response_id,b_response_id) VALUES(%s,%s,%s,%s)",
                        (assignment, project_id, mapping["A"], mapping["B"]),
                    )
            return {
                "study_id": study,
                "pairs": len(rows),
                "assignments": len(rows) * len(names),
                "sample_kind": "FIXTURE" if fixture else "DIAGNOSTIC",
            }

    @router.get("/review-queue")
    def queue(project_id: UUID) -> list:
        with connect(settings) as db:
            return db.execute(
                "SELECT a.id,a.state,a.reviewer_id,u.display_name,c.sample_kind,c.study_id FROM assignment a JOIN user_account u ON u.id=a.reviewer_id JOIN comparison_unit c ON c.id=a.comparison_unit_id WHERE a.project_id=%s ORDER BY a.state,a.id LIMIT 500",
                (project_id,),
            ).fetchall()

    @router.get("/review-queue/{assignment_id}")
    def detail(project_id: UUID, assignment_id: UUID) -> dict:
        with connect(settings) as db:
            row = db.execute(
                "SELECT a.id,a.state,a.reviewer_id,u.display_name,ra.normalized_text AS response_a,rb.normalized_text AS response_b,c.prompt,c.context,c.expected_contract,rr.digest AS rubric_digest,cu.sample_kind FROM assignment a JOIN user_account u ON u.id=a.reviewer_id JOIN assignment_mapping m ON m.assignment_id=a.id JOIN response ra ON ra.id=m.a_response_id JOIN response rb ON rb.id=m.b_response_id JOIN run_item i ON i.id=ra.run_item_id JOIN case_revision c ON c.id=i.case_revision_id JOIN comparison_unit cu ON cu.id=a.comparison_unit_id JOIN human_study hs ON hs.id=cu.study_id JOIN rubric_revision rr ON rr.id=hs.rubric_revision_id WHERE a.project_id=%s AND a.id=%s",
                (project_id, assignment_id),
            ).fetchone()
            if not row:
                raise DomainError("NOT_FOUND", "Assignment not found", 404)
            return row

    @router.post("/review-queue/{assignment_id}", status_code=201)
    def submit(project_id: UUID, assignment_id: UUID, payload: HumanSubmission) -> dict:
        with connect(settings) as db:
            row = db.execute(
                "SELECT a.*,cu.sample_kind,rr.digest FROM assignment a JOIN comparison_unit cu ON cu.id=a.comparison_unit_id JOIN human_study hs ON hs.id=cu.study_id JOIN rubric_revision rr ON rr.id=hs.rubric_revision_id WHERE a.project_id=%s AND a.id=%s FOR UPDATE OF a",
                (project_id, assignment_id),
            ).fetchone()
            if not row:
                raise DomainError("NOT_FOUND", "Assignment not found", 404)
            if row["state"] != "ASSIGNED":
                raise DomainError(
                    "ALREADY_SUBMITTED", "Original judgments cannot be overwritten", 409
                )
            if (
                payload.assignment_id != str(assignment_id)
                or payload.reviewer_ref != str(row["reviewer_id"])
                or payload.rubric_digest != row["digest"]
            ):
                raise DomainError(
                    "ASSIGNMENT_MISMATCH", "Reviewer, assignment or rubric mismatch", 409
                )
            expected_origin = "TEST_FIXTURE" if row["sample_kind"] == "FIXTURE" else "ACTUAL_HUMAN"
            if payload.data_origin != expected_origin:
                raise DomainError(
                    "ORIGIN_MISMATCH", "Fixture judgments cannot become actual-human evidence", 409
                )
            judgment = uuid4()
            db.execute(
                "INSERT INTO judgment(id,project_id,assignment_id,preference,rationale,data_origin) VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    judgment,
                    project_id,
                    assignment_id,
                    payload.preference,
                    payload.rationale,
                    payload.data_origin,
                ),
            )
            for rating in payload.ratings:
                db.execute(
                    "INSERT INTO dimension_rating(id,project_id,judgment_id,response_slot,dimension,status,ordinal_value,evidence,rationale) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        uuid4(),
                        project_id,
                        judgment,
                        rating.slot,
                        rating.dimension,
                        rating.status,
                        rating.value,
                        Jsonb({"rubric_digest": payload.rubric_digest}),
                        rating.rationale,
                    ),
                )
            db.execute("UPDATE assignment SET state='SUBMITTED' WHERE id=%s", (assignment_id,))
            return {"judgment_id": judgment, "state": "SUBMITTED"}

    @router.get("/annotation-qa")
    def annotation_qa(project_id: UUID, include_fixtures: bool = False) -> dict:
        with connect(settings) as db:
            rows = db.execute(
                "SELECT j.preference,j.data_origin,a.comparison_unit_id,a.reviewer_id,m.a_response_id,cu.baseline_response_id,cu.study_id FROM judgment j JOIN assignment a ON a.id=j.assignment_id JOIN assignment_mapping m ON m.assignment_id=a.id JOIN comparison_unit cu ON cu.id=a.comparison_unit_id WHERE j.project_id=%s AND j.amendment_of_id IS NULL AND (%s OR j.data_origin='ACTUAL_HUMAN')",
                (project_id, include_fixtures),
            ).fetchall()
            studies = {}
            for row in rows:
                study = studies.setdefault(str(row["study_id"]), {})
                preference = canonical_choice(
                    row["preference"],
                    "A" if row["a_response_id"] == row["baseline_response_id"] else "B",
                )
                study.setdefault(str(row["comparison_unit_id"]), {})[str(row["reviewer_id"])] = (
                    None if preference == "CANNOT_JUDGE" else preference
                )
            reports = []
            for study, units in studies.items():
                reports.append(
                    {
                        "study_id": study,
                        "agreement": asdict(
                            krippendorff_alpha(
                                units, level="nominal", categories=("BASELINE", "CANDIDATE", "TIE")
                            )
                        ),
                        "disagreements": [
                            key
                            for key, ratings in units.items()
                            if len({v for v in ratings.values() if v is not None}) > 1
                        ],
                    }
                )
            return {
                "ratings": len(rows),
                "studies": reports,
                "include_fixtures": include_fixtures,
                "status": "PENDING" if not rows else "DESCRIPTIVE",
                "scope": "Original independent preferences, canonical identity; local enrollment does not certify language expertise.",
            }

    @router.get("/failure-labels")
    def labels(project_id: UUID) -> list:
        with connect(settings) as db:
            return db.execute(
                "SELECT code,definition FROM failure_label WHERE taxonomy_version='1' ORDER BY code"
            ).fetchall()

    @router.post("/findings", status_code=201)
    def finding(project_id: UUID, payload: FindingInput) -> dict:
        with connect(settings) as db:
            if not db.execute(
                "SELECT 1 FROM response WHERE id=%s AND project_id=%s",
                (payload.response_id, project_id),
            ).fetchone():
                raise DomainError("NOT_FOUND", "Response not found", 404)
            if not db.execute(
                "SELECT 1 FROM failure_label WHERE code=%s AND taxonomy_version='1'",
                (payload.label,),
            ).fetchone():
                raise DomainError("INVALID_LABEL", "Choose a versioned failure label", 422)
            finding_id = uuid4()
            db.execute(
                "INSERT INTO failure_finding(id,project_id,response_id,severity,origin_kind,verification_state,evidence) VALUES(%s,%s,%s,'MAJOR','HUMAN','PROPOSED',%s)",
                (
                    finding_id,
                    project_id,
                    payload.response_id,
                    Jsonb(
                        {"rationale": payload.rationale, "identity": "local operator; unverified"}
                    ),
                ),
            )
            db.execute(
                "INSERT INTO finding_label(finding_id,code,taxonomy_version) VALUES(%s,%s,'1')",
                (finding_id, payload.label),
            )
            return {"finding_id": finding_id, "verification_state": "PROPOSED"}

    return router
