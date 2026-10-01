from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from adriva.domain.contracts import BenchmarkImport
from adriva.domain.hashing import digest
from adriva.domain.validation import validate_import
from adriva.errors import DomainError


def create_project(db: psycopg.Connection, name: str, slug: str) -> UUID:
    project_id = uuid4()
    db.execute("INSERT INTO project(id,name,slug) VALUES (%s,%s,%s)", (project_id, name, slug))
    return project_id


def import_benchmark(db: psycopg.Connection, project_id: UUID, batch: BenchmarkImport) -> UUID:
    """Caller owns transaction: validation failure leaves no partial imported release."""
    try:
        batch = BenchmarkImport.model_validate(batch.model_dump())
    except ValidationError as exc:
        raise DomainError("IMPORT_INVALID", "Case registry contract validation failed") from exc
    if not db.execute("SELECT id FROM project WHERE id=%s FOR UPDATE", (project_id,)).fetchone():
        raise DomainError("NOT_FOUND", "Project not found", 404)
    issues = validate_import(batch)
    if issues:
        raise DomainError("IMPORT_INVALID", "; ".join(f"{i.rule}:{i.case_key}" for i in issues))
    benchmark = db.execute(
        "SELECT id FROM benchmark WHERE project_id=%s AND name=%s", (project_id, batch.name)
    ).fetchone()
    benchmark_id = benchmark["id"] if benchmark else uuid4()
    if not benchmark:
        db.execute(
            "INSERT INTO benchmark(id,project_id,name) VALUES (%s,%s,%s)",
            (benchmark_id, project_id, batch.name),
        )
    if db.execute(
        "SELECT id FROM benchmark_release WHERE benchmark_id=%s AND version=%s",
        (benchmark_id, batch.version),
    ).fetchone():
        raise DomainError("VERSION_EXISTS", "Benchmark version already exists", 409)
    release_id = uuid4()
    db.execute(
        "INSERT INTO benchmark_release(id,project_id,benchmark_id,version) VALUES (%s,%s,%s,%s)",
        (release_id, project_id, benchmark_id, batch.version),
    )
    revision_ids: dict[str, UUID] = {}
    reused: set[str] = set()
    for ordinal, case in enumerate(batch.cases):
        cluster = db.execute(
            "SELECT id FROM dependency_cluster WHERE project_id=%s AND stable_key=%s",
            (project_id, case.cluster_key),
        ).fetchone()
        cluster_id = cluster["id"] if cluster else uuid4()
        if not cluster:
            db.execute(
                "INSERT INTO dependency_cluster(id,project_id,stable_key,reason) VALUES (%s,%s,%s,%s)",
                (cluster_id, project_id, case.cluster_key, "Declared source/intent dependency"),
            )
        family = db.execute(
            "SELECT id,cluster_id,primary_task FROM intent_family WHERE project_id=%s AND stable_key=%s",
            (project_id, case.family_key),
        ).fetchone()
        family_id = family["id"] if family else uuid4()
        if family and (family["cluster_id"] != cluster_id or family["primary_task"] != case.task):
            raise DomainError("FAMILY_CONFLICT", "Existing family contract differs", 409)
        if not family:
            db.execute(
                "INSERT INTO intent_family(id,project_id,cluster_id,stable_key,primary_task) VALUES (%s,%s,%s,%s,%s)",
                (family_id, project_id, cluster_id, case.family_key, case.task),
            )
        item = db.execute(
            "SELECT id,family_id FROM case_item WHERE project_id=%s AND stable_key=%s",
            (project_id, case.key),
        ).fetchone()
        item_id = item["id"] if item else uuid4()
        if item and item["family_id"] != family_id:
            raise DomainError("CASE_CONFLICT", "Case identity cannot move between families", 409)
        if not item:
            db.execute(
                "INSERT INTO case_item(id,project_id,family_id,stable_key) VALUES (%s,%s,%s,%s)",
                (item_id, project_id, family_id, case.key),
            )
        case_digest = digest(case.model_dump(exclude={"split"}))
        old = db.execute(
            "SELECT id,digest FROM case_revision WHERE case_item_id=%s AND revision_no=%s",
            (item_id, case.revision),
        ).fetchone()
        revision_id = old["id"] if old else uuid4()
        if old and old["digest"] != case_digest:
            raise DomainError(
                "REVISION_CONFLICT", "Changed content requires a new case revision", 409
            )
        if not old:
            db.execute(
                "INSERT INTO case_revision(id,project_id,case_item_id,revision_no,prompt,context,input_profile,output_profile,expected_contract,usage_class,creation_origin,digest,registry_payload) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    revision_id,
                    project_id,
                    item_id,
                    case.revision,
                    case.prompt,
                    case.context,
                    Jsonb(case.input_profile.model_dump()),
                    Jsonb(case.output_profile.model_dump()),
                    Jsonb(case.expected.model_dump()),
                    case.usage,
                    case.origin,
                    case_digest,
                    Jsonb(case.model_dump(exclude={"split"})),
                ),
            )
            source_id = uuid4()
            db.execute(
                "INSERT INTO source_record(id,project_id,source_kind,uri,license,external_revision,item_key,permission_note,sensitivity) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    source_id,
                    project_id,
                    case.origin,
                    case.source_uri,
                    case.license,
                    case.source_revision,
                    case.source_item_key,
                    case.permission_note,
                    case.sensitivity,
                ),
            )
            db.execute(
                "INSERT INTO case_source(project_id,case_revision_id,source_id) VALUES (%s,%s,%s)",
                (project_id, revision_id, source_id),
            )
        else:
            reused.add(case.key)
        revision_ids[case.key] = revision_id
        db.execute(
            "INSERT INTO release_case(project_id,release_id,case_revision_id,split,ordinal) VALUES (%s,%s,%s,%s,%s)",
            (project_id, release_id, revision_id, case.split, ordinal),
        )
    for case in batch.cases:
        if case.derivation and case.key in reused:
            old_parent = db.execute(
                "SELECT parent_revision_id FROM derivation_event WHERE child_revision_id=%s",
                (revision_ids[case.key],),
            ).fetchone()
            if (
                not old_parent
                or old_parent["parent_revision_id"] != revision_ids[case.derivation.parent_key]
            ):
                raise DomainError(
                    "PARENT_REVISION_CHANGED",
                    "Changed parent requires a new transformed case revision",
                    409,
                )
        if case.derivation and case.key not in reused:
            d = case.derivation
            db.execute(
                "INSERT INTO derivation_event(id,project_id,child_revision_id,parent_revision_id,operator_revision,relation,invariant,parameters) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    uuid4(),
                    project_id,
                    revision_ids[case.key],
                    revision_ids[d.parent_key],
                    d.operator_version,
                    d.relation,
                    d.invariant,
                    Jsonb(d.parameters),
                ),
            )
    db.execute(
        "INSERT INTO audit_event(id,project_id,action,target_id) VALUES (%s,%s,'BENCHMARK_IMPORTED',%s)",
        (uuid4(), project_id, release_id),
    )
    return release_id


def export_benchmark(db: psycopg.Connection, project_id: UUID, release_id: UUID) -> BenchmarkImport:
    release = db.execute(
        "SELECT b.name,r.version FROM benchmark_release r JOIN benchmark b ON b.id=r.benchmark_id WHERE r.id=%s AND r.project_id=%s",
        (release_id, project_id),
    ).fetchone()
    if not release:
        raise DomainError("NOT_FOUND", "Release not found", 404)
    rows = db.execute(
        "SELECT c.registry_payload,rc.split,rc.weight FROM release_case rc JOIN case_revision c ON c.id=rc.case_revision_id WHERE rc.release_id=%s ORDER BY rc.ordinal",
        (release_id,),
    ).fetchall()
    if any(not r["registry_payload"] or r["weight"] != 1 for r in rows):
        raise DomainError(
            "EXPORT_UNSUPPORTED",
            "Historical payload or custom weighting requires an extended export format",
            409,
        )
    return BenchmarkImport.model_validate(
        {**release, "cases": [{**r["registry_payload"], "split": r["split"]} for r in rows]}
    )


def release_manifest(db: psycopg.Connection, project_id: UUID, release_id: UUID) -> dict[str, Any]:
    release = db.execute(
        "SELECT version,schema_version,taxonomy_version FROM benchmark_release WHERE id=%s AND project_id=%s",
        (release_id, project_id),
    ).fetchone()
    if not release:
        raise DomainError("NOT_FOUND", "Release not found", 404)
    cases = db.execute(
        "SELECT c.digest,rc.split,rc.weight,rc.ordinal,i.stable_key,c.revision_no FROM release_case rc JOIN case_revision c ON c.id=rc.case_revision_id JOIN case_item i ON i.id=c.case_item_id WHERE rc.release_id=%s ORDER BY rc.ordinal",
        (release_id,),
    ).fetchall()
    return {
        "canonicalization": "json-v1",
        **release,
        "cases": [{**row, "weight": str(row["weight"])} for row in cases],
    }


def publish_release(db: psycopg.Connection, project_id: UUID, release_id: UUID) -> str:
    # Same lock order as imports: project first, then release. Serializes provenance and freeze.
    db.execute("SELECT id FROM project WHERE id=%s FOR UPDATE", (project_id,))
    release = db.execute(
        "SELECT state,manifest_digest FROM benchmark_release WHERE id=%s AND project_id=%s FOR UPDATE",
        (release_id, project_id),
    ).fetchone()
    if not release:
        raise DomainError("NOT_FOUND", "Release not found", 404)
    if release["state"] == "FROZEN":
        return release["manifest_digest"]
    manifest = release_manifest(db, project_id, release_id)
    manifest_digest = digest(manifest)
    db.execute(
        "UPDATE benchmark_release SET state='FROZEN',manifest=%s,manifest_digest=%s,published_at=now() WHERE id=%s",
        (Jsonb(manifest), manifest_digest, release_id),
    )
    db.execute(
        "INSERT INTO audit_event(id,project_id,action,target_id) VALUES (%s,%s,'BENCHMARK_FROZEN',%s)",
        (uuid4(), project_id, release_id),
    )
    return manifest_digest
