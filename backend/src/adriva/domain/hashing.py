import hashlib
import json
from typing import Any


def digest(value: Any) -> str:
    """Canonical v1: UTF-8 sorted keys, compact JSON, no NaN; original text preserved."""
    encoded = json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
