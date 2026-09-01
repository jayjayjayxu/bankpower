"""Lazy adapter for the unchanged legacy BankAI V0.4 core."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Protocol

from .config import Settings


class AgentProtocol(Protocol):
    def run(self, question: str) -> dict[str, Any]: ...


class CoreUnavailableError(RuntimeError):
    """The API process cannot safely construct the legacy core."""


AgentFactory = Callable[[Settings], AgentProtocol]


def build_legacy_agent(settings: Settings) -> AgentProtocol:
    """Construct BankAI V0.4 with explicit absolute asset paths.

    The API layer does not reimplement Router, RAG, SQL, BOTH, Claim Grounding,
    or SQL safety. It delegates those responsibilities to the existing core.
    """

    if settings.core_dir is None:
        raise CoreUnavailableError("未设置 BANKAI_CORE_DIR。")
    if not os.getenv("DEEPSEEK_API_KEY", "").strip():
        raise CoreUnavailableError("未设置 DEEPSEEK_API_KEY。")
    source_dir = settings.core_dir / "src"
    required = (
        source_dir / "bank_agent_v04.py",
        settings.core_dir / "docs" / "text_to_sql_schema.md",
        settings.core_dir / "metadata.csv",
        settings.core_dir / "storage" / "vector_index_v03" / "chunks.faiss",
        settings.core_dir / "storage" / "vector_index_v03" / "records.jsonl",
    )
    missing = [str(item) for item in required if not item.is_file()]
    if missing:
        raise CoreUnavailableError("BankAI Core 资源缺失：" + "；".join(missing))
    source_dir_text = str(source_dir)
    if source_dir_text not in sys.path:
        sys.path.insert(0, source_dir_text)
    try:
        from bank_agent_v04 import build_default_agent_v04
    except ImportError as exc:
        raise CoreUnavailableError("无法加载 BankAI V0.4 依赖。") from exc
    try:
        return build_default_agent_v04(
            schema_path=settings.core_dir / "docs" / "text_to_sql_schema.md",
            index_dir=settings.core_dir / "storage" / "vector_index_v03",
            cache_dir=settings.core_dir / "storage" / "huggingface",
            login_path=settings.sql_login_path,
            metadata_path=settings.core_dir / "metadata.csv",
        )
    except RuntimeError as exc:
        raise CoreUnavailableError("无法初始化 BankAI V0.4：" + str(exc)) from exc


class AgentProvider:
    """Lazily creates one core instance after the process has accepted health checks."""

    def __init__(self, settings: Settings, factory: AgentFactory = build_legacy_agent) -> None:
        self._settings = settings
        self._factory = factory
        self._agent: AgentProtocol | None = None
        self._lock = threading.Lock()

    def run(self, question: str) -> dict[str, Any]:
        if self._agent is None:
            with self._lock:
                if self._agent is None:
                    self._agent = self._factory(self._settings)
        return self._agent.run(question)


def health_details(settings: Settings) -> dict[str, str]:
    """Check local prerequisites without starting an embedding model or LLM call."""

    if settings.core_dir is None:
        rag_index = "not_configured"
    else:
        index_dir = settings.core_dir / "storage" / "vector_index_v03"
        required = (index_dir / "chunks.faiss", index_dir / "records.jsonl")
        rag_index = "ok" if all(item.is_file() for item in required) else "missing"

    if not settings.database_healthcheck:
        database = "not_checked"
    elif not settings.mysql_binary.is_file():
        database = "missing_mysql_client"
    else:
        try:
            completed = subprocess.run(
                [
                    str(settings.mysql_binary),
                    f"--login-path={settings.sql_login_path}",
                    "--batch",
                    "--skip-column-names",
                    "bank_ai",
                    "-e",
                    "SELECT 1",
                ],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            database = "ok" if completed.returncode == 0 else "unavailable"
        except (OSError, subprocess.TimeoutExpired):
            database = "unavailable"
    return {"rag_index": rag_index, "database": database}
