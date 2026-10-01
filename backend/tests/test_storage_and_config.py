import json
import logging
from uuid import uuid4

import pytest
from adriva.config import Settings
from adriva.logging import JsonFormatter
from adriva.storage.local import LocalArtifactStore
from pydantic import ValidationError


def test_artifact_integrity_and_traversal(tmp_path) -> None:
    store = LocalArtifactStore(tmp_path)
    checksum, key = store.put(uuid4(), b'{"usage":"FIXTURE"}')
    assert store.read(key, checksum) == b'{"usage":"FIXTURE"}'
    with pytest.raises(ValueError):
        store.read("../outside", checksum)
    with pytest.raises(ValueError):
        store.read(key, "0" * 64)


def test_production_is_blocked_and_secret_repr() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production")
    assert "a-password" not in repr(
        Settings(database_url="postgresql://user:a-password@localhost/db")
    )


def test_logging_excludes_arbitrary_payload() -> None:
    record = logging.LogRecord("adriva", 20, "", 0, "test_event", (), None)
    record.prompt = "PRIVATE_PROMPT"
    record.request_id = "test-id"
    rendered = JsonFormatter().format(record)
    assert "PRIVATE_PROMPT" not in rendered
    assert json.loads(rendered)["request_id"] == "test-id"
