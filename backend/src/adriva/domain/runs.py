from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb

from adriva.domain.hashing import digest
from adriva.errors import DomainError
from adriva.gateway.compatible import CompatibleAdapter
from adriva.gateway.contracts import ModelConfig
from adriva.gateway.fixture import FixtureAdapter


def register_model(db: psycopg.Connection, project_id: UUID, config: ModelConfig) -> UUID:
    if config.provider == "fixture":
        FixtureAdapter().validate(config)
    elif config.provider == "openai_compatible":
        CompatibleAdapter().validate(config)
    elif config.usage_class == "FIXTURE":
        raise DomainError("INVALID_MODEL", "Fixture configurations require fixture provider")
    # Only references to secrets are permitted, including inside arbitrary parameters.
    denied = {"api_key", "apikey", "password", "token", "secret", "authorization", "credential"}

    def has_secret(value: object) -> bool:
        if isinstance(value, dict):
            return any(str(k).lower() in denied or has_secret(v) for k, v in value.items())
        if isinstance(value, list):
            return any(has_secret(v) for v in value)
        return False

    if has_secret(config.parameters):
        raise DomainError(
            "SECRET_FIELD", "Store credentials in environment variables, never model parameters"
        )
    if config.endpoint_ref and ("://" in config.endpoint_ref or "@" in config.endpoint_ref):
        raise DomainError(
            "ENDPOINT_REFERENCE", "Use an approved endpoint configuration reference, not a URL"
        )
    model_digest = digest(config.model_dump())
    existing = db.execute(
        "SELECT id FROM model_configuration WHERE project_id=%s AND digest=%s",
        (project_id, model_digest),
    ).fetchone()
    if existing:
        return existing["id"]
    model_id = uuid4()
    db.execute(
        "INSERT INTO model_configuration(id,project_id,provider,requested_model,model_version,endpoint_ref,credential_ref,parameters,capabilities,usage_class,digest) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            model_id,
            project_id,
            config.provider,
            config.requested_model,
            config.model_version,
            config.endpoint_ref,
            config.credential_ref,
            Jsonb(config.parameters),
            Jsonb(config.capabilities),
            config.usage_class,
            model_digest,
        ),
    )
    return model_id


def create_run(
    db: psycopg.Connection, project_id: UUID, release_id: UUID, model_id: UUID, repetitions: int = 1
) -> UUID:
    if not 1 <= repetitions <= 10:
        raise DomainError("REPETITIONS", "Repetitions must be in 1..10")
    release = db.execute(
        "SELECT state,manifest_digest FROM benchmark_release WHERE id=%s AND project_id=%s",
        (release_id, project_id),
    ).fetchone()
    model = db.execute(
        "SELECT * FROM model_configuration WHERE id=%s AND project_id=%s", (model_id, project_id)
    ).fetchone()
    if not release or not model:
        raise DomainError("NOT_FOUND", "Release or model not found", 404)
    if release["state"] != "FROZEN":
        raise DomainError("NOT_FROZEN", "Run requires a frozen release")
    cases = db.execute(
        "SELECT c.id,c.digest,c.usage_class FROM release_case rc JOIN case_revision c ON c.id=rc.case_revision_id WHERE rc.release_id=%s ORDER BY rc.ordinal",
        (release_id,),
    ).fetchall()
    usages = {c["usage_class"] for c in cases}
    if len(usages) != 1:
        raise DomainError("MIXED_USAGE", "Run cannot mix fixture and scientific usage classes")
    usage = next(iter(usages))
    if model["usage_class"] == "FIXTURE" and usage != "FIXTURE":
        raise DomainError("FIXTURE_BOUNDARY", "Fixture adapter cannot run scientific benchmarks")
    if model["provider"] not in {"fixture", "openai_compatible"}:
        raise DomainError(
            "ADAPTER_UNAVAILABLE",
            "No executable adapter is installed for this provider",
            409,
        )
    protocol_digest = digest(
        {
            "version": "generation-v1",
            "repetitions": repetitions,
            "selection": "first-valid",
            "parameters": {k: v for k, v in model["parameters"].items() if k != "fixture_text"},
        }
    )
    run_id = uuid4()
    db.execute(
        "INSERT INTO run(id,project_id,release_id,model_config_id,protocol_digest,state,usage_class,repetitions) VALUES (%s,%s,%s,%s,%s,'QUEUED',%s,%s)",
        (run_id, project_id, release_id, model_id, protocol_digest, usage, repetitions),
    )
    for case in cases:
        for repetition in range(repetitions):
            item_id = uuid4()
            request_digest = digest(
                {"case": case["digest"], "model": model["digest"], "repetition": repetition}
            )
            db.execute(
                "INSERT INTO run_item(id,project_id,run_id,case_revision_id,repetition_index,request_digest,state) VALUES (%s,%s,%s,%s,%s,%s,'PENDING')",
                (item_id, project_id, run_id, case["id"], repetition, request_digest),
            )
            db.execute(
                "INSERT INTO job(id,project_id,run_item_id,state) VALUES (%s,%s,%s,'PENDING')",
                (uuid4(), project_id, item_id),
            )
    return run_id


def cancel_run(db: psycopg.Connection, project_id: UUID, run_id: UUID) -> None:
    run = db.execute(
        "SELECT state FROM run WHERE id=%s AND project_id=%s FOR UPDATE", (run_id, project_id)
    ).fetchone()
    if not run:
        raise DomainError("NOT_FOUND", "Run not found", 404)
    if run["state"] in {"COMPLETED", "FAILED", "PARTIAL"}:
        raise DomainError("TERMINAL_RUN", "Cannot cancel a completed run", 409)
    db.execute("UPDATE run SET state='CANCELLED' WHERE id=%s", (run_id,))
    db.execute(
        "UPDATE job SET state='CANCELLED' WHERE run_item_id IN (SELECT id FROM run_item WHERE run_id=%s) AND state IN ('PENDING','LEASED')",
        (run_id,),
    )
    db.execute(
        "UPDATE run_item SET state='CANCELLED' WHERE run_id=%s AND state='PENDING'", (run_id,)
    )
