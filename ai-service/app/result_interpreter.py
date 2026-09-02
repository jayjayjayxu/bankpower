"""Convert raw, already-executed SQL rows into auditable business semantics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .domain_semantics import mapping_boundaries, normalized_mapping_status
from .energy_sql import QueryResult
from .value_formatter import format_field, format_metric_value, is_null, label_for


RAW_FIELD_NAMES = frozenset({
    "candidate_facility_v2_id", "facility_v2_id", "facility_code", "source_locator",
    "external_product_id", "mapping_status", "boundary_note", "evidence_summary",
})


@dataclass(frozen=True)
class InterpretedSQLResult:
    response_mode: str
    answer_status: str
    primary_conclusion: str
    facts: list[dict[str, Any]]
    candidates: list[dict[str, Any]]
    warnings: list[str]
    boundaries: list[str]
    raw_columns: list[str]
    raw_rows: list[list[str]]

    def public_dict(self) -> dict[str, Any]:
        return {
            "response_mode": self.response_mode,
            "answer_status": self.answer_status,
            "primary_conclusion": self.primary_conclusion,
            "facts": [
                {"key": item["key"], "label": item["label"], "value": item["value"]}
                for item in self.facts
            ],
            "candidates": self.candidates,
            "warnings": self.warnings,
            "boundaries": self.boundaries,
        }


def _rows(result: QueryResult) -> list[dict[str, str]]:
    return [dict(zip(result.columns, row, strict=True)) for row in result.rows]


def _response_mode(question: str, columns: list[str]) -> str:
    lowered = question.casefold()
    names = set(columns)
    if {"mapping_status", "external_product_id"} & names or "对应哪个数据中心" in question:
        return "ENTITY_MAPPING"
    if any(term in lowered for term in ("排名", "最低", "最高", "top", "排序", "前3", "前三", "前5", "前五")):
        return "RANKING"
    if any(term in lowered for term in ("变化", "趋势", "历年", "时间序列")):
        return "TIME_SERIES"
    if any(term in lowered for term in ("平均", "合计", "总计", "总数", "数量")) and len(columns) <= 4:
        return "AGGREGATION"
    if any(term in lowered for term in ("比较", "对比", "哪个", "差异")):
        return "COMPARISON"
    if any(term in lowered for term in ("哪些", "列出", "所有", "名单")):
        return "LIST"
    if columns and len(names) <= 8 and "metric_value" not in names:
        return "LIST" if "哪些" in question else "FACT_LOOKUP"
    return "FACT_LOOKUP"


def _fact(key: str, value: Any, *, label: str | None = None, raw_value: Any | None = None) -> dict[str, Any]:
    return {
        "key": key,
        "label": label or label_for(key),
        "value": value,
        "raw_value": raw_value if raw_value is not None else value,
    }


def _mapping_interpretation(question: str, result: QueryResult, rows: list[dict[str, str]]) -> InterpretedSQLResult:
    if not rows:
        return InterpretedSQLResult(
            "ENTITY_MAPPING", "NO_DATA", "当前数据库中尚无该商品的设施映射信息。", [], [],
            ["未查询到可核验的商品映射记录。"], ["当前数据库尚无该商品的设施映射信息。"],
            result.columns, result.rows,
        )
    row = rows[0]
    product = row.get("external_product_id") or row.get("product_name") or "该商品"
    status = normalized_mapping_status(row.get("mapping_status"))
    official_name, candidate_name = row.get("official_name"), row.get("candidate_name")
    if status == "CONFIRMED" and not is_null(official_name):
        conclusion, answer_status = f"{product} 已确认映射至 {official_name}。", "CONFIRMED_MAPPING"
    elif status == "CANDIDATE" and not is_null(candidate_name):
        conclusion, answer_status = f"当前数据库仅将 {candidate_name} 记录为 {product} 的候选设施，尚未完成确认映射。", "UNCONFIRMED_MAPPING"
    elif status == "UNMAPPED":
        conclusion, answer_status = f"目前无法确认 {product} 对应具体数据中心。", "UNCONFIRMED_MAPPING"
    elif status == "NO_DATA":
        conclusion, answer_status = f"当前数据库中尚无 {product} 的设施映射信息。", "NO_DATA"
    else:
        conclusion, answer_status = f"{product} 的设施映射证据存在冲突，暂不能确认具体数据中心。", "UNCONFIRMED_MAPPING"
    facts = []
    for key in ("external_product_id", "product_name", "provider_name", "platform_region_label", "mapping_status"):
        display = format_field(key, row.get(key))
        if display is not None:
            facts.append(_fact(key, display, raw_value=row.get(key)))
    candidates = []
    if not is_null(candidate_name):
        candidates.append({
            "name": candidate_name,
            "role": "REFERENCE_ONLY" if status == "UNMAPPED" else "CANDIDATE",
            "reason": row.get("evidence_summary") or "当前记录未提供候选依据说明。",
        })
    boundaries = mapping_boundaries(status, candidate_name, row.get("boundary_note"))
    warnings = ["映射状态不是已确认；请勿将候选参照理解为实际部署或运营关系。"] if status != "CONFIRMED" else []
    return InterpretedSQLResult("ENTITY_MAPPING", answer_status, conclusion, facts, candidates, warnings, boundaries, result.columns, result.rows)


def _metric_facts(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for row in rows:
        if "metric_value" in row:
            metric_name = row.get("metric_name") or row.get("metric_code") or "指标值"
            display = format_metric_value(metric_name, row.get("metric_value"), row.get("metric_unit"))
            if display is not None:
                facts.append(_fact(str(metric_name), display, label=str(metric_name), raw_value=row.get("metric_value")))
        for key in ("rack_utilization_ratio", "average_rack_price_yuan_month"):
            if key in row:
                display = format_field(key, row.get(key))
                if display is not None:
                    facts.append(_fact(key, display, raw_value=row.get(key)))
    return facts


def _general_interpretation(
    question: str, result: QueryResult, rows: list[dict[str, str]], entity_name: str | None = None
) -> InterpretedSQLResult:
    mode = _response_mode(question, result.columns)
    if not rows:
        return InterpretedSQLResult(mode, "NO_DATA", "没有查询到符合条件的可核验数据。", [], [], ["当前查询条件未返回记录。"], [], result.columns, result.rows)
    facts = _metric_facts(rows)
    first = rows[0]
    facility = first.get("official_name") or first.get("facility_name") or entity_name or "该查询对象"
    year = format_field("fact_year", first.get("fact_year"))
    prefix = f"{facility}{year or ''}".strip()
    if facts:
        values = "，".join(f"{item['label']}为{item['value']}" for item in facts[:4])
        conclusion = f"{prefix}的已披露数据为：{values}。"
    elif mode == "RANKING":
        conclusion = f"当前数据库按查询条件返回 {len(rows)} 条排名记录。"
    elif mode == "LIST":
        conclusion = f"当前数据库找到 {len(rows)} 条符合条件的记录。"
    else:
        conclusion = f"当前数据库返回 {len(rows)} 条可核验记录。"
    # Add neutral, human labels for useful non-technical fields that do not
    # duplicate metrics or expose database implementation identifiers.
    if not facts:
        for key, value in first.items():
            if key in RAW_FIELD_NAMES or is_null(value):
                continue
            display = format_field(key, value)
            if display is not None:
                facts.append(_fact(key, display, raw_value=value))
            if len(facts) >= 6:
                break
    return InterpretedSQLResult(mode, "ANSWERED", conclusion, facts, [], [], [], result.columns, result.rows)


def interpret_sql_result(
    question: str, result: QueryResult, entities: list[dict[str, str]] | None = None
) -> InterpretedSQLResult:
    """Interpret executed evidence only; it never queries or infers new data."""

    rows = _rows(result)
    if (
        "mapping_status" in result.columns
        or "external_product_id" in result.columns
        or "对应哪个数据中心" in question
    ):
        return _mapping_interpretation(question, result, rows)
    entity_name = "、".join(item["canonical_name"] for item in entities or [] if item.get("canonical_name")) or None
    return _general_interpretation(question, result, rows, entity_name)
