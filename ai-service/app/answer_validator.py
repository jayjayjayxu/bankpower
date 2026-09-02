"""Validate rendered SQL answers and preserve a deterministic safe fallback."""

from __future__ import annotations

from dataclasses import dataclass

from .result_interpreter import InterpretedSQLResult
from .sql_answer_renderer import deterministic_sql_answer


RAW_FIELD_LEAKS = (
    "candidate_facility_v2_id=", "facility_v2_id=", "external_product_id=", "mapping_status=",
    "source_locator=", "boundary_note=", "evidence_summary=", "NULL",
)
UNCONFIRMED_MAPPING_FORBIDDEN = ("已确认映射", "对应的是", "部署于", "位于", "确认属于")


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...]


def validate_sql_answer(answer: str, interpreted: InterpretedSQLResult) -> ValidationResult:
    errors: list[str] = []
    if interpreted.primary_conclusion not in answer:
        errors.append("缺少或改变了程序生成的 primary_conclusion。")
    if any(token in answer for token in RAW_FIELD_LEAKS):
        errors.append("普通回答泄露了原始字段名或 NULL。")
    if interpreted.answer_status == "UNCONFIRMED_MAPPING":
        if any(token in answer for token in UNCONFIRMED_MAPPING_FORBIDDEN):
            errors.append("未确认映射被升级为确认关系。")
    if interpreted.boundaries and not any(boundary in answer for boundary in interpreted.boundaries):
        errors.append("未保留证据边界。")
    for fact in interpreted.facts:
        if str(fact["value"]) not in answer:
            errors.append(f"关键数值或单位未按程序格式保留：{fact['key']}。")
    return ValidationResult(not errors, tuple(dict.fromkeys(errors)))


def validate_or_fallback(answer: str, interpreted: InterpretedSQLResult) -> tuple[str, ValidationResult, bool]:
    validation = validate_sql_answer(answer, interpreted)
    if validation.valid:
        return answer, validation, False
    fallback = deterministic_sql_answer(interpreted)
    fallback_validation = validate_sql_answer(fallback, interpreted)
    if not fallback_validation.valid:
        raise RuntimeError("SQL 解释层的确定性回退未通过自身校验。")
    return fallback, validation, True
