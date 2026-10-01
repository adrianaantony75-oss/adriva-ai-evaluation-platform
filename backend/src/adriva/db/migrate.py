from hashlib import sha256
from importlib.resources import files

from adriva.config import Settings
from adriva.db.connection import connect


def migrations() -> list[tuple[str, str, str]]:
    root = files("adriva.db").joinpath("migrations")
    return [
        (path.name, path.read_text(encoding="utf-8"), sha256(path.read_bytes()).hexdigest())
        for path in sorted(root.iterdir(), key=lambda p: p.name)
        if path.name.endswith(".sql")
    ]


def migrate(settings: Settings) -> list[str]:
    if settings.migration_database_url:
        settings = settings.model_copy(update={"database_url": settings.migration_database_url})
    applied: list[str] = []
    with connect(settings) as db:
        db.execute("SELECT pg_advisory_xact_lock(728413250)")
        db.execute(
            "CREATE TABLE IF NOT EXISTS schema_migration (version text PRIMARY KEY, checksum text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        recorded = {
            r["version"]: r["checksum"]
            for r in db.execute("SELECT version,checksum FROM schema_migration")
        }
        expected = {name: digest for name, _, digest in migrations()}
        if any(
            name not in expected or expected[name] != digest for name, digest in recorded.items()
        ):
            raise RuntimeError("Migration history differs from packaged checksums")
        seen_pending = False
        for name, sql, digest in migrations():
            if name in recorded:
                if seen_pending:
                    raise RuntimeError("Migration history is not a contiguous prefix")
                continue
            seen_pending = True
            db.execute(sql)
            db.execute(
                "INSERT INTO schema_migration(version,checksum) VALUES (%s,%s)", (name, digest)
            )
            applied.append(name)
    return applied


def ready(settings: Settings) -> bool:
    with connect(settings) as db:
        recorded = {
            r["version"]: r["checksum"]
            for r in db.execute("SELECT version,checksum FROM schema_migration")
        }
        return recorded == {name: digest for name, _, digest in migrations()}
