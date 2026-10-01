import json
import logging
from typing import Any
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb

from adriva.config import Settings
from adriva.db.connection import connect
from adriva.domain.hashing import digest
from adriva.gateway.contracts import AdapterError, GenerationRequest, ModelAdapter, ModelConfig
from adriva.storage.local import LocalArtifactStore

logger = logging.getLogger("adriva.worker")


def claim(db: psycopg.Connection, owner: str, lease_seconds: int = 60) -> dict[str, Any] | None:
    if not 1 <= lease_seconds <= 3600:
        raise ValueError("Lease duration outside permitted range")
    exhausted = db.execute(
        "SELECT id,run_item_id FROM job WHERE state='LEASED' AND lease_until<now() AND attempt_count>=max_attempts FOR UPDATE SKIP LOCKED"
    ).fetchall()
    for item in exhausted:
        db.execute("UPDATE job SET state='FAILED' WHERE id=%s", (item["id"],))
        db.execute("UPDATE run_item SET state='FAILED' WHERE id=%s", (item["run_item_id"],))
        db.execute(
            "UPDATE execution_attempt SET outcome='STALE',finished_at=now(),error_class='LEASE_EXPIRED' WHERE run_item_id=%s AND outcome='RUNNING'",
            (item["run_item_id"],),
        )
    row = db.execute(
        "SELECT j.* FROM job j JOIN run_item i ON i.id=j.run_item_id JOIN run r ON r.id=i.run_id WHERE ((j.state='PENDING' AND j.available_at<=now()) OR (j.state='LEASED' AND j.lease_until<now())) AND j.attempt_count<j.max_attempts AND r.state IN ('QUEUED','RUNNING') ORDER BY j.available_at,j.id FOR UPDATE OF j SKIP LOCKED LIMIT 1"
    ).fetchone()
    if not row:
        return None
    token = uuid4()
    db.execute(
        "UPDATE execution_attempt SET outcome='STALE',finished_at=now(),error_class='LEASE_EXPIRED' WHERE run_item_id=%s AND outcome='RUNNING'",
        (row["run_item_id"],),
    )
    db.execute(
        "UPDATE job SET state='LEASED',lease_owner=%s,lease_token=%s,lease_until=now()+(%s * interval '1 second'),attempt_count=attempt_count+1 WHERE id=%s",
        (owner, token, lease_seconds, row["id"]),
    )
    attempt_id = uuid4()
    db.execute(
        "INSERT INTO execution_attempt(id,project_id,run_item_id,attempt_no,lease_token,outcome) VALUES (%s,%s,%s,%s,%s,'RUNNING')",
        (attempt_id, row["project_id"], row["run_item_id"], row["attempt_count"] + 1, token),
    )
    return {
        **row,
        "lease_token": token,
        "attempt_id": attempt_id,
        "attempt_count": row["attempt_count"] + 1,
    }


def refresh_runs(db: psycopg.Connection) -> None:
    db.execute("""UPDATE run r SET state=CASE
     WHEN EXISTS(SELECT 1 FROM run_item i WHERE i.run_id=r.id AND i.state='PENDING') THEN 'RUNNING'
     WHEN NOT EXISTS(SELECT 1 FROM run_item i WHERE i.run_id=r.id AND i.state<>'SUCCEEDED') THEN 'COMPLETED'
     WHEN EXISTS(SELECT 1 FROM run_item i WHERE i.run_id=r.id AND i.state='SUCCEEDED') THEN 'PARTIAL'
     ELSE 'FAILED' END WHERE r.state IN ('QUEUED','RUNNING')""")


def complete(
    db: psycopg.Connection,
    claimed: dict[str, Any],
    result: Any,
    store: LocalArtifactStore,
    request: GenerationRequest,
    error: AdapterError | None = None,
) -> bool:
    item = db.execute(
        "SELECT run_id FROM run_item WHERE id=%s", (claimed["run_item_id"],)
    ).fetchone()
    run = db.execute("SELECT state FROM run WHERE id=%s FOR UPDATE", (item["run_id"],)).fetchone()
    job = db.execute(
        "SELECT *,lease_until>now() AS live FROM job WHERE id=%s FOR UPDATE", (claimed["id"],)
    ).fetchone()
    if (
        run["state"] == "CANCELLED"
        or job["state"] != "LEASED"
        or job["lease_token"] != claimed["lease_token"]
        or not job["live"]
    ):
        db.execute(
            "UPDATE execution_attempt SET outcome='STALE',finished_at=now(),error_class='STALE_LEASE' WHERE id=%s",
            (claimed["attempt_id"],),
        )
        return False
    if error:
        retry = error.retryable and claimed["attempt_count"] < job["max_attempts"]
        db.execute(
            "UPDATE execution_attempt SET outcome='FAILED',error_class=%s,finished_at=now() WHERE id=%s",
            (error.code, claimed["attempt_id"]),
        )
        db.execute(
            "UPDATE job SET state=%s,available_at=now()+(%s * interval '1 second') WHERE id=%s",
            (
                "PENDING" if retry else "FAILED",
                min(60, 2 ** claimed["attempt_count"]),
                claimed["id"],
            ),
        )
        if not retry:
            db.execute("UPDATE run_item SET state='FAILED' WHERE id=%s", (claimed["run_item_id"],))
        return False
    artifact_data = json.dumps(
        {"request": request.model_dump(mode="json"), "result": result.model_dump()},
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    checksum, key = store.put(claimed["project_id"], artifact_data)
    artifact_id = uuid4()
    artifact = db.execute(
        "INSERT INTO artifact(id,project_id,content_hash,storage_key,size_bytes,media_type) VALUES (%s,%s,%s,%s,%s,'application/json') ON CONFLICT(project_id,content_hash) DO UPDATE SET storage_key=EXCLUDED.storage_key RETURNING id",
        (artifact_id, claimed["project_id"], checksum, key, len(artifact_data)),
    ).fetchone()
    db.execute(
        "UPDATE execution_attempt SET outcome='SUCCEEDED',finished_at=now(),returned_model=%s,provider_request_id=%s,usage=%s WHERE id=%s",
        (
            result.returned_model,
            result.provider_request_id,
            Jsonb(result.usage),
            claimed["attempt_id"],
        ),
    )
    db.execute(
        "INSERT INTO response(id,project_id,run_item_id,attempt_id,raw_artifact_id,normalized_text,finish_reason,digest) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            uuid4(),
            claimed["project_id"],
            claimed["run_item_id"],
            claimed["attempt_id"],
            artifact["id"],
            result.text,
            result.finish_reason,
            digest(result.model_dump()),
        ),
    )
    db.execute("UPDATE job SET state='SUCCEEDED' WHERE id=%s", (claimed["id"],))
    db.execute("UPDATE run_item SET state='SUCCEEDED' WHERE id=%s", (claimed["run_item_id"],))
    return True


def run_once(
    settings: Settings, owner: str = "local-worker", adapter: ModelAdapter | None = None
) -> bool:
    with connect(settings) as db:
        claimed = claim(db, owner)
    if not claimed:
        with connect(settings) as db:
            refresh_runs(db)
        return False
    with connect(settings) as db:
        data = db.execute(
            "SELECT c.prompt,c.context,m.provider,m.requested_model,m.model_version,m.endpoint_ref,m.credential_ref,m.parameters,m.capabilities,m.usage_class FROM run_item i JOIN run r ON r.id=i.run_id JOIN model_configuration m ON m.id=r.model_config_id JOIN case_revision c ON c.id=i.case_revision_id WHERE i.id=%s",
            (claimed["run_item_id"],),
        ).fetchone()
    config = ModelConfig.model_validate(
        {k: v for k, v in data.items() if k not in {"prompt", "context"}}
    )
    request = GenerationRequest(
        logical_request_id=claimed["run_item_id"],
        prompt=data["prompt"],
        context=data["context"],
        parameters=config.parameters,
    )
    from adriva.gateway.compatible import select_adapter

    selected = adapter or select_adapter(config.provider)
    result = None
    error = None
    try:
        selected.validate(config)
        result = selected.generate(request)  # No open DB transaction during model execution.
    except AdapterError as exc:
        error = exc
    except Exception:
        error = AdapterError("INTERNAL_ADAPTER_ERROR")
    with connect(settings) as db:
        committed = complete(
            db, claimed, result, LocalArtifactStore(settings.artifact_root), request, error
        )
    with connect(settings) as db:
        refresh_runs(db)
    logger.info(
        "job_finished",
        extra={
            "job_id": str(claimed["id"]),
            "status": "SUCCEEDED" if committed else "NOT_COMMITTED",
        },
    )
    return True


def main() -> None:
    import argparse

    from adriva.logging import configure_logging

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--watch", action="store_true", help="Poll queue and publish heartbeat until interrupted"
    )
    parser.add_argument("--once", action="store_true", help="Process at most one available job")
    args = parser.parse_args()
    configure_logging()
    settings = Settings()
    if args.watch:
        import socket
        import time

        owner = socket.gethostname() + "-watch"
        while True:
            with connect(settings) as db:
                db.execute(
                    "INSERT INTO worker_heartbeat(owner,state) VALUES (%s,'POLLING') ON CONFLICT(owner) DO UPDATE SET last_seen=now(),state='POLLING'",
                    (owner,),
                )
            if not run_once(settings, owner=owner):
                time.sleep(2)
    elif args.once:
        run_once(settings)
    else:
        # Drain currently available work; no hidden infinite background loop.
        while run_once(settings):
            pass


if __name__ == "__main__":
    main()
