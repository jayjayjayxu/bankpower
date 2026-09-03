"""Stable, user-safe failure taxonomy for the V6 production API.

Tool implementations are free to retain their native exceptions.  This module
is the single translation point at the HTTP boundary: clients receive a small
business error code and a retry-safe message, while audit records retain a
sanitised technical cause for diagnosis.
"""

from __future__ import annotations

import re
import traceback
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    MODEL_TIMEOUT = "MODEL_TIMEOUT"
    MODEL_CONNECTION_ERROR = "MODEL_CONNECTION_ERROR"
    DB_CONNECTION_ERROR = "DB_CONNECTION_ERROR"
    SQL_VALIDATION_ERROR = "SQL_VALIDATION_ERROR"
    SQL_EXECUTION_ERROR = "SQL_EXECUTION_ERROR"
    RAG_NO_EVIDENCE = "RAG_NO_EVIDENCE"
    RAG_VALIDATION_ERROR = "RAG_VALIDATION_ERROR"
    RAG_INDEX_ERROR = "RAG_INDEX_ERROR"
    IN_SCOPE_DATA_MISSING = "IN_SCOPE_DATA_MISSING"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    CALCULATION_ERROR = "CALCULATION_ERROR"
    CONTEXT_RESOLUTION_ERROR = "CONTEXT_RESOLUTION_ERROR"
    SERVICE_CONFIGURATION_ERROR = "SERVICE_CONFIGURATION_ERROR"
    UNKNOWN_SERVICE_ERROR = "UNKNOWN_SERVICE_ERROR"


@dataclass(frozen=True)
class ErrorDescriptor:
    code: ErrorCode
    http_status: int
    user_message: str
    retryable: bool

    def public_dict(self, request_id: str) -> dict[str, Any]:
        return {
            "request_id": request_id,
            "code": self.code.value,
            "message": self.user_message,
            "retryable": self.retryable,
        }


_DESCRIPTORS: dict[ErrorCode, ErrorDescriptor] = {
    ErrorCode.MODEL_TIMEOUT: ErrorDescriptor(ErrorCode.MODEL_TIMEOUT, 503, "AI 服务响应超时，请稍后重试。", True),
    ErrorCode.MODEL_CONNECTION_ERROR: ErrorDescriptor(ErrorCode.MODEL_CONNECTION_ERROR, 503, "AI 服务暂时不可用，请稍后重试。", True),
    ErrorCode.DB_CONNECTION_ERROR: ErrorDescriptor(ErrorCode.DB_CONNECTION_ERROR, 503, "数据服务暂时不可用，请稍后重试。", True),
    ErrorCode.SQL_VALIDATION_ERROR: ErrorDescriptor(ErrorCode.SQL_VALIDATION_ERROR, 422, "查询未通过安全校验，未执行数据库操作。", False),
    ErrorCode.SQL_EXECUTION_ERROR: ErrorDescriptor(ErrorCode.SQL_EXECUTION_ERROR, 503, "查询暂时失败，请稍后重试。", True),
    ErrorCode.RAG_NO_EVIDENCE: ErrorDescriptor(ErrorCode.RAG_NO_EVIDENCE, 200, "当前知识库无法确定该问题。", False),
    ErrorCode.RAG_VALIDATION_ERROR: ErrorDescriptor(ErrorCode.RAG_VALIDATION_ERROR, 502, "政策证据校验未通过，本次未输出未经验证的回答。", True),
    ErrorCode.RAG_INDEX_ERROR: ErrorDescriptor(ErrorCode.RAG_INDEX_ERROR, 503, "政策知识库暂时不可用，请稍后重试。", True),
    ErrorCode.IN_SCOPE_DATA_MISSING: ErrorDescriptor(ErrorCode.IN_SCOPE_DATA_MISSING, 200, "该问题属于当前业务范围，但缺少可核验数据。", False),
    ErrorCode.OUT_OF_SCOPE: ErrorDescriptor(ErrorCode.OUT_OF_SCOPE, 200, "该问题超出当前系统支持范围。", False),
    ErrorCode.CALCULATION_ERROR: ErrorDescriptor(ErrorCode.CALCULATION_ERROR, 422, "计算输入不完整或不兼容，未执行推导计算。", False),
    ErrorCode.CONTEXT_RESOLUTION_ERROR: ErrorDescriptor(ErrorCode.CONTEXT_RESOLUTION_ERROR, 422, "无法可靠继承上一轮上下文，请明确项目、年份或指标。", False),
    ErrorCode.SERVICE_CONFIGURATION_ERROR: ErrorDescriptor(ErrorCode.SERVICE_CONFIGURATION_ERROR, 503, "AI 服务当前配置不可用，请联系管理员。", False),
    ErrorCode.UNKNOWN_SERVICE_ERROR: ErrorDescriptor(ErrorCode.UNKNOWN_SERVICE_ERROR, 502, "AI 服务执行失败，请稍后重试。", True),
}


def descriptor(code: ErrorCode) -> ErrorDescriptor:
    return _DESCRIPTORS[code]


def result_error_code(result: dict[str, Any]) -> ErrorCode | None:
    """Classify safe, completed business outcomes without treating them as 5xx."""

    route = str(result.get("route") or "").upper()
    if route == "OUT_OF_SCOPE":
        return ErrorCode.OUT_OF_SCOPE
    if route == "IN_SCOPE_DATA_MISSING":
        return ErrorCode.IN_SCOPE_DATA_MISSING
    if route in {"CLARIFICATION", "CONTEXT_RESET"}:
        return ErrorCode.CONTEXT_RESOLUTION_ERROR if route == "CLARIFICATION" else None
    sql_safety = (result.get("sql_result") or {}).get("safety") or {}
    if sql_safety and not sql_safety.get("safe", True):
        return ErrorCode.SQL_VALIDATION_ERROR
    rag_result = result.get("rag_result") or {}
    if rag_result.get("answerable") is False:
        return ErrorCode.RAG_NO_EVIDENCE
    calculation = result.get("calculation_result") or {}
    if calculation.get("status") in {"ERROR", "FAILED"}:
        return ErrorCode.CALCULATION_ERROR
    return None


def classify_exception(exc: Exception) -> ErrorDescriptor:
    """Map native library failures without coupling to optional SDK imports."""

    chain = list(_exception_chain(exc))
    names = " ".join(type(item).__name__.casefold() for item in chain)
    modules = " ".join(type(item).__module__.casefold() for item in chain)
    messages = " ".join(str(item).casefold() for item in chain)
    fingerprint = f"{names} {modules} {messages}"

    if "coreunavailable" in names or "未设置 deepseek_api_key" in messages:
        return descriptor(ErrorCode.SERVICE_CONFIGURATION_ERROR)
    if "timeout" in names or "timeout" in fingerprint or "timed out" in fingerprint:
        if any(marker in fingerprint for marker in ("mysql", "pymysql", "database", "spdb_power_finance")):
            return descriptor(ErrorCode.DB_CONNECTION_ERROR)
        return descriptor(ErrorCode.MODEL_TIMEOUT)
    if any(marker in names for marker in ("apiconnectionerror", "connectionerror", "connecterror")):
        if any(marker in fingerprint for marker in ("mysql", "pymysql", "database", "spdb_power_finance")):
            return descriptor(ErrorCode.DB_CONNECTION_ERROR)
        return descriptor(ErrorCode.MODEL_CONNECTION_ERROR)
    if any(marker in fingerprint for marker in ("pymysql", "mysql", "operationalerror", "interfaceerror")):
        if any(marker in fingerprint for marker in ("connect", "connection", "server has gone away", "lost connection")):
            return descriptor(ErrorCode.DB_CONNECTION_ERROR)
        return descriptor(ErrorCode.SQL_EXECUTION_ERROR)
    if "查询失败" in messages or "query failed" in messages:
        return descriptor(ErrorCode.SQL_EXECUTION_ERROR)
    if "policyragerror" in names:
        if any(marker in messages for marker in ("索引", "index", "语料")):
            return descriptor(ErrorCode.RAG_INDEX_ERROR)
        return descriptor(ErrorCode.RAG_VALIDATION_ERROR)
    if "zerodivisionerror" in names or "invalidoperation" in names:
        return descriptor(ErrorCode.CALCULATION_ERROR)
    if "keyerror" in names or "conversation" in modules:
        return descriptor(ErrorCode.CONTEXT_RESOLUTION_ERROR)
    return descriptor(ErrorCode.UNKNOWN_SERVICE_ERROR)


def audit_error_details(exc: Exception) -> dict[str, Any]:
    """Store diagnosis data without credentials, tokens, or response trace leaks."""

    chain = list(_exception_chain(exc))
    return {
        "exception_type": type(exc).__name__,
        "exception_message": _redact(str(exc))[:2_000],
        "exception_chain": [
            {"type": type(item).__name__, "message": _redact(str(item))[:1_000]}
            for item in chain
        ],
        "traceback": _redact("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))[:12_000],
    }


def _exception_chain(exc: Exception):
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


_SECRET_PATTERNS = (
    re.compile(r"(?i)authorization\s*:\s*bearer\s+[^\s,;]+"),
    re.compile(r"(?i)\bbearer\s+[^\s,;]+"),
    re.compile(r"(?i)(api[_ -]?key|authorization|bearer|password|mysql_pwd)\s*[=:]\s*[^\s,;]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
)


def _redact(value: str) -> str:
    redacted = value
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted
