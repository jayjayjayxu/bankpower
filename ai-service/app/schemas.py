"""Public HTTP contracts. Internal prompt and model traces never appear here."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)

    @field_validator("question")
    @classmethod
    def non_blank_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("问题不能为空。")
        return value


class SQLData(BaseModel):
    columns: list[str]
    rows: list[list[Any]]


class Source(BaseModel):
    document_name: str
    page_start: int | None = None
    page_end: int | None = None
    authority: str | None = None
    quote: str | None = None
    locator: str | None = None
    url: str | None = None
    issuing_authority: str | None = None
    policy_level: str | None = None
    policy_status: str | None = None
    region: str | None = None
    effective_date: str | None = None
    expiry_date: str | None = None


class ChatResponse(BaseModel):
    request_id: str
    question: str
    route: str
    answer: str
    data: dict[str, SQLData | dict[str, Any] | None]
    interpretation: dict[str, Any] | None = None
    structured_data: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    debug_available: bool = False
    sources: list[Source]
    claims: list[dict[str, Any]]
    warnings: list[str]
    timing: dict[str, int]


class HealthResponse(BaseModel):
    status: str
    agent_version: str = "EnergyComputeAI-V4.0-C"
    database: str
    spdb_database: str
    rag_index: str


class DebugSQLResponse(BaseModel):
    route: str
    generated_sql: str | None = None
    safety: dict[str, Any] | None = None
    query_result: SQLData | None = None
    answer: str
    entity_resolution: list[dict[str, str]] = Field(default_factory=list)
