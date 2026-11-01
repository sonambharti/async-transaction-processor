import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger("webhook_service")


def configure_logging() -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def log_event(level: int, event: str, **fields: Any) -> None:
    record = {"time": datetime.now(UTC).isoformat(), "event": event, **fields}
    logger.log(level, json.dumps(record, default=str))
