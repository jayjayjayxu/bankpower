"""Lazy adapter for the unchanged legacy BankAI V0.4 core."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Protocol

from .config import Settings
from .energy_compute import EnergyComputeAgent
from .policy_rag import PolicyRAGAgent
from .policy_workflow import EnergyPolicyBothAgent
from .public_statistics import PublicStatisticsAgent
from .v4_workflow import V4ProjectWorkflow


class AgentProtocol(Protocol):
    def run(self, question: str) -> dict[str, Any]: ...


class CoreUnavailableError(RuntimeError):
    """The API process cannot safely construct the legacy core."""


AgentFactory = Callable[[Settings], AgentProtocol]
_CORE_BUILD_DIRECTORY_LOCK = threading.Lock()


@contextmanager
def _legacy_core_working_directory(directory: Path):
    """Resolve the legacy index's relative local-model path during construction.

    `vector_index_v03/index_config.json` predates this API and records
    `storage/models/...` as a relative path. The directory is changed only
    while the single, lazily-created core is built, then restored immediately.
    """

    with _CORE_BUILD_DIRECTORY_LOCK:
        previous = Path.cwd()
        os.chdir(directory)
        try:
            yield
        finally:
            os.chdir(previous)


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
        with _legacy_core_working_directory(settings.core_dir):
            return build_default_agent_v04(
                schema_path=settings.core_dir / "docs" / "text_to_sql_schema.md",
                index_dir=settings.core_dir / "storage" / "vector_index_v03",
                cache_dir=settings.core_dir / "storage" / "huggingface",
                login_path=settings.sql_login_path,
                metadata_path=settings.core_dir / "metadata.csv",
            )
    except RuntimeError as exc:
        raise CoreUnavailableError("无法初始化 BankAI V0.4：" + str(exc)) from exc


class HybridAgent:
    """Route V0.3 policy questions before SQL facts and the legacy fallback.

    The legacy core remains untouched and is only initialized when a question is
    outside the energy/compute catalogue.  Consequently a structured database
    fact never depends on an LLM API key or an LLM-generated SQL statement.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._energy_agent = EnergyComputeAgent(settings)
        self._policy_agent = PolicyRAGAgent(settings)
        self._both_agent = EnergyPolicyBothAgent(settings, self._energy_agent, self._policy_agent)
        self._v4_agent = V4ProjectWorkflow(settings, self._energy_agent, self._policy_agent)
        self._public_statistics_agent = PublicStatisticsAgent(settings)
        self._legacy_agent: AgentProtocol | None = None
        self._legacy_lock = threading.Lock()

    def run(self, question: str) -> dict[str, Any]:
        if self._public_statistics_agent.supports(question):
            return self._public_statistics_agent.run(question)
        if self._v4_agent.supports(question):
            return self._v4_agent.run(question)
        if self._requires_final_credit_determination(question):
            return self._credit_boundary(question)
        if self._both_agent.supports(question):
            return self._both_agent.run(question)
        if self._policy_agent.supports(question):
            return self._policy_agent.run(question)
        if self._energy_agent.supports(question):
            return self._energy_agent.run(question)
        if self._legacy_agent is None:
            with self._legacy_lock:
                if self._legacy_agent is None:
                    self._legacy_agent = build_legacy_agent(self._settings)
        return self._legacy_agent.run(question)

    @staticmethod
    def _requires_final_credit_determination(question: str) -> bool:
        lowered = question.casefold()
        finality = ("一定", "最终", "直接")
        finance = ("绿色贷款", "贷款", "授信", "融资审批", "融资比例")
        return any(term in lowered for term in finality) and any(term in lowered for term in finance)

    @staticmethod
    def _credit_boundary(question: str) -> dict[str, Any]:
        return {
            "agent_version": "EnergyComputeAI-V0.3.1",
            "question": question.strip(), "route": "OUT_OF_SCOPE",
            "router": {"route": "OUT_OF_SCOPE", "reason": "V0.3 不作最终融资资格、授信或贷款比例决定。"},
            "decomposition": None, "tool_calls": [], "sql_result": None, "rag_result": None,
            "synthesis": None, "sources": [],
            "final_answer": (
                "当前版本可以查询项目事实和现行公开政策，但不能作最终绿色贷款资格、"
                "授信审批或融资比例决定。仍需核验项目用途、资金投向、节能量证明、"
                "建设与运营资料及完整融资材料。"
            ),
        }

    def debug_sql(self, question: str) -> dict[str, Any]:
        if not self._energy_agent.supports(question):
            return {
                "route": "OUT_OF_SCOPE",
                "answer": "仅支持查看 V0.2 电力/算力 SQL 调试结果。",
            }
        return self._energy_agent.debug_sql(question)


def build_default_agent(settings: Settings) -> AgentProtocol:
    """Construct the V0.3 router without eagerly starting a model or index."""

    return HybridAgent(settings)


class AgentProvider:
    """Lazily creates one core instance after the process has accepted health checks."""

    def __init__(self, settings: Settings, factory: AgentFactory = build_default_agent) -> None:
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

    def debug_sql(self, question: str) -> dict[str, Any]:
        if self._agent is None:
            with self._lock:
                if self._agent is None:
                    self._agent = self._factory(self._settings)
        debug_sql = getattr(self._agent, "debug_sql", None)
        if not callable(debug_sql):
            raise CoreUnavailableError("当前 AI 核心未启用 SQL 调试接口。")
        return debug_sql(question)


def health_details(settings: Settings) -> dict[str, str]:
    """Check local prerequisites without starting an embedding model or LLM call."""

    if settings.core_dir is None:
        rag_index = "not_configured"
    else:
        index_dir = settings.policy_rag_index_dir
        model_dir = settings.core_dir / "storage" / "models" / "bge-small-zh-v1.5"
        required = (
            index_dir / "chunks.faiss",
            index_dir / "records.jsonl",
            index_dir / "index_config.json",
            model_dir / "config.json",
            model_dir / "model.safetensors",
            model_dir / "tokenizer.json",
        )
        rag_index = "ok" if all(item.is_file() for item in required) else "missing"

    def check_database(login_path: str, database_name: str) -> str:
        if not settings.database_healthcheck:
            return "not_checked"
        if not settings.mysql_binary.is_file():
            return "missing_mysql_client"
        try:
            completed = subprocess.run(
                [
                    str(settings.mysql_binary),
                    f"--login-path={login_path}",
                    "--batch",
                    "--skip-column-names",
                    database_name,
                    "-e",
                    "SELECT 1",
                ],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            return "ok" if completed.returncode == 0 else "unavailable"
        except (OSError, subprocess.TimeoutExpired):
            return "unavailable"

    return {
        "rag_index": rag_index,
        "database": check_database(settings.sql_login_path, "bank_ai"),
        "spdb_database": check_database(settings.spdb_sql_login_path, settings.spdb_database),
    }
