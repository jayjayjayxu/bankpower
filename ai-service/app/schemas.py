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


class ChatResponse(BaseModel):
    request_id: str
    question: str
    route: str
    answer: str
    data: dict[str, SQLData | None]
    sources: list[Source]
    claims: list[dict[str, Any]]
    warnings: list[str]
    timing: dict[str, int]


class HealthResponse(BaseModel):
    status: str
    agent_version: str = "V0.4"
    database: str
    rag_index: str
