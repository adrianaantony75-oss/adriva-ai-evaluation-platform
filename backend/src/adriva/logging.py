import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
            "logger": record.name,
        }
        for key in ("request_id", "run_id", "job_id", "status", "duration_ms", "error_code"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        # Do not serialize exception strings, request bodies, connection URLs or arbitrary extras.
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("adriva")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
