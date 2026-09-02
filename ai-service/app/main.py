"""FastAPI boundary for BankAI V0.4."""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import UTC, datetime
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from .audit import AuditLogger, AuditWriteError
from .config import Settings
from .core import AgentFactory, AgentProvider, CoreUnavailableError, health_details
from .schemas import ChatRequest, ChatResponse, DebugSQLResponse, HealthResponse, SQLData, Source


def _public_sources(result: dict[str, Any]) -> list[Source]:
    """Expose only document and database evidence, including its locator.

    V0.4 uses ``rag_result.references`` while the controlled V0.2 tools also
    return ``sources``.  Deduplicating here preserves one public evidence
    model for both paths without exposing prompts, SQL text, or credentials.
    """

    references = [
        *(result.get("sources") or []),
        *((result.get("rag_result") or {}).get("references") or []),
    ]
    sources: list[Source] = []
    seen: set[tuple[str, str | None, str | None]] = set()
    for item in references:
        document_name = str(item.get("source_filename") or item.get("title") or "未命名文件")
        locator = item.get("source_locator")
        quote = item.get("supporting_quote")
        key = (document_name, locator, quote)
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            Source(
                document_name=document_name,
                page_start=item.get("page_start"),
                page_end=item.get("page_end"),
                authority=item.get("authority_code"),
                quote=quote,
                locator=locator,
                url=item.get("official_url"),
                issuing_authority=item.get("issuing_authority"),
                policy_level=item.get("policy_level"),
                policy_status=item.get("status"),
                region=item.get("region"),
                effective_date=item.get("effective_date"),
                expiry_date=item.get("expiry_date"),
            )
        )
    return sources


def _public_sql_data(sql_result: dict[str, Any] | None) -> SQLData | None:
    query_result = (sql_result or {}).get("query_result")
    if not query_result:
        return None
    return SQLData(
        columns=list(query_result.get("columns") or []),
        rows=list(query_result.get("rows") or []),
    )


def _public_warnings(result: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    rag_result = result.get("rag_result") or {}
    if rag_result.get("answerable") is False:
        warnings.append(str(rag_result.get("insufficiency_reason") or "政策证据不足。"))
    synthesis = result.get("synthesis") or {}
    dropped = synthesis.get("dropped_claims") or []
    if dropped:
        warnings.append(f"{len(dropped)} 条缺乏充分依据的结论未向用户展示。")
    sql_result = result.get("sql_result") or {}
    safety = sql_result.get("safety") or {}
    if safety and not safety.get("safe", True):
        warnings.append("SQL 安全校验未通过，未执行数据库查询。")
    interpretation = result.get("interpretation") or {}
    warnings.extend(str(item) for item in interpretation.get("warnings") or [])
    warnings.extend(str(item) for item in (result.get("finance_result") or {}).get("warnings") or [])
    warnings.extend(str(item) for item in (result.get("eligibility_result") or {}).get("warnings") or [])
    if result.get("finance_boundary"):
        warnings.append(str(result["finance_boundary"]))
    return warnings


def _public_response(
    request_id: str, result: dict[str, Any], elapsed_ms: int, debug_available: bool = False
) -> ChatResponse:
    synthesis = result.get("synthesis") or {}
    interpretation = result.get("interpretation") or None
    return ChatResponse(
        request_id=request_id,
        question=str(result["question"]),
        route=str(result["route"]),
        answer=str(result["final_answer"]),
        data={
            "sql": _public_sql_data(result.get("sql_result")),
            "comparison": result.get("policy_comparison"),
            "finance": result.get("finance_result"),
            "max_debt": result.get("max_debt_result"),
            "eligibility": result.get("eligibility_result"),
        },
        interpretation=interpretation,
        structured_data={
            "facts": list((interpretation or {}).get("facts") or []),
            "candidates": list((interpretation or {}).get("candidates") or []),
            "boundaries": [
                {"message": str(item)} for item in ((interpretation or {}).get("boundaries") or [])
            ],
        },
        debug_available=debug_available,
        sources=_public_sources(result),
        claims=list(synthesis.get("claims") or []),
        warnings=_public_warnings(result),
        timing={"total_ms": elapsed_ms},
    )


def create_app(
    settings: Settings | None = None,
    agent_factory: AgentFactory | None = None,
    audit_logger: AuditLogger | None = None,
    health_checker: Callable[[Settings], dict[str, str]] = health_details,
) -> FastAPI:
    """Create a testable API without constructing the heavy legacy core at import time."""

    settings = settings or Settings.from_environment()
    provider = AgentProvider(settings, agent_factory) if agent_factory else AgentProvider(settings)
    audit_logger = audit_logger or AuditLogger(settings.audit_dir)

    app = FastAPI(title="EnergyComputeAI", version="4.0-C")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Request-ID", "X-Admin-Token"],
    )
    app.state.run_gate = asyncio.Semaphore(settings.max_concurrency)

    @app.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        details = await asyncio.to_thread(health_checker, settings)
        status = (
            "ok"
            if details["database"] in {"ok", "not_checked"}
            and details["spdb_database"] in {"ok", "not_checked"}
            and details["rag_index"] == "ok"
            else "degraded"
        )
        return HealthResponse(
            status=status,
            database=details["database"],
            spdb_database=details["spdb_database"],
            rag_index=details["rag_index"],
        )

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        started = time.perf_counter()
        audit_base: dict[str, Any] = {
            "request_id": request_id,
            "received_at": datetime.now(UTC).isoformat(),
            "question": payload.question,
            "api_version": "4.0-C",
        }
        try:
            async with app.state.run_gate:
                result = await asyncio.to_thread(provider.run, payload.question)
            elapsed_ms = round((time.perf_counter() - started) * 1_000)
            response = _public_response(request_id, result, elapsed_ms, settings.sql_debug_enabled)
            audit_logger.write(
                request_id,
                {
                    **audit_base,
                    "status": "succeeded",
                    "timing": response.timing,
                    "route": response.route,
                    "public_response": response.model_dump(mode="json"),
                    "agent_result": result,
                },
            )
            return response
        except CoreUnavailableError as exc:
            status_code, code, message = 503, "core_unavailable", str(exc)
        except AuditWriteError as exc:
            status_code, code, message = 500, "audit_write_failed", str(exc)
        except Exception as exc:  # The full exception class stays in the audit record.
            status_code, code, message = 502, "agent_execution_failed", "AI 服务执行失败，请稍后重试。"
            audit_base["exception_type"] = type(exc).__name__
        try:
            audit_logger.write(
                request_id,
                {
                    **audit_base,
                    "status": "failed",
                    "error_code": code,
                    "error_message": message,
                    "timing": {"total_ms": round((time.perf_counter() - started) * 1_000)},
                },
            )
        except AuditWriteError:
            pass
        raise HTTPException(status_code=status_code, detail={"request_id": request_id, "code": code, "message": message})

    @app.post("/api/debug/sql", response_model=DebugSQLResponse, include_in_schema=False)
    async def debug_sql(payload: ChatRequest, request: Request) -> DebugSQLResponse:
        if not settings.sql_debug_enabled:
            raise HTTPException(status_code=404, detail="Not Found")
        if not settings.sql_debug_token or request.headers.get("X-Admin-Token") != settings.sql_debug_token:
            raise HTTPException(status_code=403, detail="Forbidden")
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        started = time.perf_counter()
        try:
            async with app.state.run_gate:
                result = await asyncio.to_thread(provider.debug_sql, payload.question)
            response = DebugSQLResponse(
                route=str(result["route"]),
                generated_sql=result.get("generated_sql"),
                safety=result.get("safety"),
                query_result=_public_sql_data({"query_result": result.get("query_result")}),
                answer=str(result["answer"]),
                entity_resolution=list(result.get("entity_resolution") or []),
            )
            audit_logger.write(
                request_id,
                {
                    "request_id": request_id,
                    "received_at": datetime.now(UTC).isoformat(),
                    "status": "succeeded",
                    "operation": "debug_sql",
                    "question": payload.question,
                    "timing": {"total_ms": round((time.perf_counter() - started) * 1_000)},
                    "debug_result": result,
                },
            )
            return response
        except CoreUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    return app


app = create_app()
