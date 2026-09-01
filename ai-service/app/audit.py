"""Append-only, request-scoped audit records for the API layer."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class AuditWriteError(RuntimeError):
    """Raised when a response cannot be made auditable."""


class AuditLogger:
    """Writes one immutable JSON document per request using an atomic rename."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def write(self, request_id: str, payload: dict[str, Any]) -> Path:
        day = datetime.now(UTC).strftime("%Y-%m-%d")
        destination_dir = self.directory / day
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / f"{request_id}.json"
        temporary = destination.with_suffix(".json.tmp")
        try:
            with temporary.open("w", encoding="utf-8") as output:
                json.dump(payload, output, ensure_ascii=False, sort_keys=True, default=str)
                output.write("\n")
            os.replace(temporary, destination)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise AuditWriteError("无法写入请求审计记录。") from exc
        return destination
