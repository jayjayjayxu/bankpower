"""V6.1 scope-aware routing for local public electricity statistics."""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from .config import Settings
from .energy_sql import QueryResult, SpdbReadOnlyExecutor


_YEAR = re.compile(r"(?<!\d)(20\d{2})(?!\d)")
_REGIONS = {"全国": "CN", "中国": "CN", "广东": "GD", "深圳": "SZ", "广州": "GZ"}
_METRICS = (
    ("ABOVE_DESIGNATED_INDUSTRIAL_GENERATION", ("发电总量", "总发电量", "发电量", "年发电量"), "total_generation_gwh", "规模以上工业发电量"),
    ("TOTAL_ELECTRICITY_CONSUMPTION", ("全社会用电量", "总用电量", "用电量", "电力消费"), "total_consumption_gwh", "全社会用电量"),
    ("MAXIMUM_POWER_LOAD", ("最大负荷", "最高负荷", "用电负荷"), "max_load_mw", "最大负荷"),
)


class PublicStatisticsAgent:
    """Classify in-scope power statistics before choosing the fixed SQL source.

    The regional table has a source-specific generation field. Its current
    national provenance says “规模以上工业发电量”; this class preserves that
    scope instead of silently promoting it to all-calibre generation.
    """

    def __init__(self, settings: Settings, executor: SpdbReadOnlyExecutor | None = None) -> None:
        self.executor = executor or SpdbReadOnlyExecutor(settings)

    @staticmethod
    def supports(question: str) -> bool:
        lowered = question.casefold()
        return any(
            alias in lowered
            for _, aliases, _, _ in _METRICS
            for alias in aliases
        )

    def run(self, question: str) -> dict[str, Any]:
        metric = self._metric(question)
        region = self._region(question)
        year = self._year(question)
        router = {
            "route": "SQL", "domain": "POWER", "subdomain": "ELECTRICITY_STATISTICS",
            "scope": "IN_SCOPE", "source_plan": "PUBLIC_STATISTICS_SQL",
        }
        if metric is None:
            return self._missing(question, router, "当前电力统计问题尚未映射到受支持指标。")
        if region is None or year is None:
            missing = "地区" if region is None else "年份"
            return self._missing(question, router, f"该问题属于电力统计范围，但需要明确{missing}后才能查询。")
        metric_code, _, column, label = metric
        region_name = self._region_name(region)
        sql = (
            "SELECT r.region_code,r.region_name,r.region_level,s.year,"
            f"s.{column} AS metric_value,s.unit_original,s.data_quality,s.notes,"
            "d.source_title,d.source_url "
            "FROM regional_power_statistics s "
            "JOIN dim_region r ON r.region_id=s.region_id "
            "LEFT JOIN data_source d ON d.source_id=s.source_id "
            f"WHERE r.region_code='{region}' AND s.year={year} LIMIT 2"
        )
        result = self.executor.execute(sql)
        if not result.rows or self._value(result) is None:
            return self._missing(
                question, router | {"metric_code": metric_code, "region_code": region, "year": year},
                f"该问题属于电力统计范围，但当前本地数据库尚未收录 {region_name}{year} 年的 {label}。",
            )
        row = dict(zip(result.columns, result.rows[0], strict=True))
        raw = Decimal(str(row["metric_value"]))
        value_text, unit = self._format(metric_code, raw)
        generation_scope_warning = metric_code == "ABOVE_DESIGNATED_INDUSTRIAL_GENERATION"
        scope_note = (
            "来源标题明确为“规模以上工业发电量”；该值不能替代或表述为全国全口径发电总量。"
            if generation_scope_warning else ""
        )
        answer = f"{row['region_name']}{year}年{label}为 {value_text}{unit}。"
        if scope_note:
            answer += scope_note
        source = {
            "source_filename": str(row.get("source_title") or "区域电力统计"),
            "title": str(row.get("source_title") or "区域电力统计"),
            "authority_code": "PUBLIC_STATISTICS_DATABASE",
            "supporting_quote": scope_note or "本回答基于本地收录的公开统计结构化记录。",
            "source_locator": f"regional_power_statistics:{region}:{year}:{column}",
            "official_url": row.get("source_url"),
        }
        return {
            "agent_version": "EnergyComputeAI-V6.1",
            "question": question.strip(), "route": "SQL",
            "router": router | {"metric_code": metric_code, "region_code": region, "year": year, "availability": "AVAILABLE"},
            "decomposition": None,
            "tool_calls": [{"order": 1, "tool": "PUBLIC_STATISTICS_SQL", "executed": True, "table": "regional_power_statistics"}],
            "sql_result": {"generated_sql": sql, "safety": {"safe": True, "tables": ["regional_power_statistics", "dim_region", "data_source"]}, "query_result": {"columns": result.columns, "rows": result.rows}},
            "rag_result": None,
            "interpretation": {"response_mode": "FACT_LOOKUP", "answer_status": "ANSWERED", "primary_conclusion": answer, "facts": [{"key": metric_code, "label": label, "value": f"{value_text}{unit}"}], "candidates": [], "warnings": [scope_note] if scope_note else [], "boundaries": [scope_note] if scope_note else []},
            "synthesis": {"claims": [{"claim_type": "PUBLIC_STATISTIC_FACT", "text": answer, "support_ids": [source["source_locator"]]}], "dropped_claims": []},
            "sources": [source], "final_answer": answer,
        }

    @staticmethod
    def _metric(question: str) -> tuple[str, tuple[str, ...], str, str] | None:
        return next((item for item in _METRICS if any(alias in question.casefold() for alias in item[1])), None)

    @staticmethod
    def _region(question: str) -> str | None:
        return next((code for alias, code in _REGIONS.items() if alias in question), None)

    @staticmethod
    def _year(question: str) -> int | None:
        matched = _YEAR.search(question)
        return int(matched.group(1)) if matched else None

    @staticmethod
    def _region_name(region_code: str) -> str:
        return next(alias for alias, code in _REGIONS.items() if code == region_code)

    @staticmethod
    def _value(result: QueryResult) -> str | None:
        index = result.columns.index("metric_value") if "metric_value" in result.columns else -1
        return result.rows[0][index] if index >= 0 else None

    @staticmethod
    def _format(metric_code: str, value: Decimal) -> tuple[str, str]:
        if metric_code in {"ABOVE_DESIGNATED_INDUSTRIAL_GENERATION", "TOTAL_ELECTRICITY_CONSUMPTION"}:
            return f"{value / Decimal('100'):,.2f}", "亿千瓦时（数据库原值为 GWh）"
        return f"{value:,.2f}", "MW"

    @staticmethod
    def _missing(question: str, router: dict[str, Any], message: str) -> dict[str, Any]:
        return {
            "agent_version": "EnergyComputeAI-V6.1", "question": question.strip(), "route": "IN_SCOPE_DATA_MISSING",
            "router": router | {"route": "IN_SCOPE_DATA_MISSING", "availability": "MISSING"},
            "decomposition": None, "tool_calls": [{"order": 1, "tool": "PUBLIC_STATISTICS_SQL", "executed": False}],
            "sql_result": None, "rag_result": None, "interpretation": {"response_mode": "IN_SCOPE_DATA_MISSING", "answer_status": "MISSING", "primary_conclusion": message, "facts": [], "candidates": [], "warnings": [], "boundaries": ["该问题属于 EnergyComputeAI 的电力统计范围；当前结论仅表示本地数据源不可用。"]},
            "synthesis": {"claims": [], "dropped_claims": []}, "sources": [], "final_answer": message,
        }
