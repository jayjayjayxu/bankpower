"""Runtime configuration for the API wrapper around BankAI V0.4."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _csv_setting(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    """Configuration intentionally keeps secrets in the environment only."""

    core_dir: Path | None
    audit_dir: Path
    sql_login_path: str
    mysql_binary: Path
    cors_allowed_origins: tuple[str, ...]
    max_concurrency: int
    database_healthcheck: bool
    max_question_chars: int = 2_000

    @classmethod
    def from_environment(cls) -> "Settings":
        core_dir_text = os.getenv("BANKAI_CORE_DIR", "").strip()
        audit_dir = Path(os.getenv("AI_API_AUDIT_DIR", "runtime/audit"))
        origins = _csv_setting(
            os.getenv(
                "AI_API_CORS_ALLOWED_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173,"
                "http://localhost:8080,http://127.0.0.1:8080",
            )
        )
        max_concurrency = int(os.getenv("AI_API_MAX_CONCURRENCY", "1"))
        if max_concurrency < 1:
            raise ValueError("AI_API_MAX_CONCURRENCY 必须大于 0。")
        return cls(
            core_dir=Path(core_dir_text).expanduser() if core_dir_text else None,
            audit_dir=audit_dir.expanduser(),
            sql_login_path=os.getenv("BANKAI_SQL_LOGIN_PATH", "bank_ai_reader").strip(),
            mysql_binary=Path(os.getenv("MYSQL_BINARY", "/usr/local/mysql/bin/mysql")),
            cors_allowed_origins=origins,
            max_concurrency=max_concurrency,
            database_healthcheck=os.getenv("AI_API_DATABASE_HEALTHCHECK", "true").lower()
            in {"1", "true", "yes"},
        )
