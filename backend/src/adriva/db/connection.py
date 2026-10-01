from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row

from adriva.config import Settings


@contextmanager
def connect(settings: Settings) -> Iterator[psycopg.Connection[dict[str, Any]]]:
    with psycopg.connect(
        settings.database_url.get_secret_value(),
        row_factory=dict_row,
        connect_timeout=3,
        options="-c statement_timeout=15000",
    ) as connection:
        yield connection
