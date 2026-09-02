"""Scope-safe SQL and deterministic calculations for public power statistics."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from .config import Settings
from .energy_sql import QueryResult, SpdbReadOnlyExecutor
from .metric_registry import MetricSpec, find_metric, metric_by_code, related_metric_for

_YEAR = re.compile(r"(?<!\d)(20\d{2})(?!\d)")
_REGIONS = {"全国": "CN", "中国": "CN", "广东": "GD", "深圳": "SZ", "广州": "GZ"}
_LEGACY_METRICS = (
    ("TOTAL_ELECTRICITY_CONSUMPTION", ("全社会用电量", "总用电量", "用电量", "电力消费"), "total_consumption_gwh", "全社会用电量"),
    ("MAXIMUM_POWER_LOAD", ("最大负荷", "最高负荷", "用电负荷"), "max_load_mw", "最大负荷"),
)


def public_metric_for(question: str) -> str | None:
    metric = find_metric(question)
    return metric.code if metric else None


def public_metric_label(metric_code: str) -> str:
    try:
        return metric_by_code(metric_code).label
    except StopIteration:
        return metric_code


def related_public_metric_for(question: str, active_metric_code: str) -> str | None:
    metric = related_metric_for(question, active_metric_code)
    return metric.code if metric else None


def public_region_for(question: str) -> str | None:
    return next((code for alias, code in _REGIONS.items() if alias in question), None)


def public_region_label(region_code: str) -> str:
    return next(alias for alias, code in _REGIONS.items() if code == region_code)


class PublicStatisticsAgent:
    """Answer registered direct metrics and deterministic derived metrics."""

    def __init__(self, settings: Settings, executor: SpdbReadOnlyExecutor | None = None) -> None:
        self.executor = executor or SpdbReadOnlyExecutor(settings)

    @staticmethod
    def supports(question: str) -> bool:
        lowered = question.casefold()
        return find_metric(question) is not None or any(
            alias in lowered for _, aliases, _, _ in _LEGACY_METRICS for alias in aliases
        )

    def run(self, question: str) -> dict[str, Any]:
        metric = find_metric(question)
        if metric is not None:
            return self._run_generation_metric(question, metric)
        return self._run_legacy_metric(question)

    def _run_generation_metric(self, question: str, metric: MetricSpec) -> dict[str, Any]:
        router = self._router(metric.code)
        region, year = public_region_for(question), self._year(question)
        if region is None or year is None:
            missing = "地区" if region is None else "年份"
            return self._missing(question, router, f"该问题属于电力统计范围，但需要明确{missing}后才能查询。")
        if metric.metric_type == "DIRECT_METRIC":
            record = self._load_generation_record(region, year, metric)
            if record is None:
                return self._missing(question, router | {"region_code": region, "year": year}, f"该问题属于电力统计范围，但当前本地数据库尚未收录 {public_region_label(region)}{year} 年的 {metric.label}。")
            return self._direct_result(question, metric, record)
        return self._derived_result(question, metric, region, year)

    def _load_generation_record(self, region: str, year: int, metric: MetricSpec) -> dict[str, Any] | None:
        assert metric.energy_type_code is not None
        sql = (
            "SELECT r.region_code,r.region_name,p.stat_year,p.metric_basis,p.scope_code,"
            "p.statistical_scope,p.energy_type_code,p.energy_type_name,p.metric_value,p.metric_unit,"
            "p.value_operator,p.disclosure_status,p.source_locator,p.data_quality,"
            "d.source_title,NULL AS source_url,d.source_org "
            "FROM power_source_structure_v2 p JOIN dim_region r ON r.region_id=p.region_id "
            "LEFT JOIN data_source d ON d.source_id=p.source_id "
            f"WHERE r.region_code='{region}' AND p.stat_year={year} "
            "AND p.metric_basis='GROSS_GENERATION' "
            f"AND p.energy_type_code='{metric.energy_type_code}' "
            "AND p.disclosure_status IN ('DISCLOSED','DERIVED') "
            "AND p.value_operator='EQ' AND p.metric_value IS NOT NULL ORDER BY p.scope_code LIMIT 2"
        )
        result = self.executor.execute(sql)
        if not result.rows:
            return None
        return dict(zip(result.columns, result.rows[0], strict=True))

    def _derived_result(self, question: str, metric: MetricSpec, region: str, year: int) -> dict[str, Any]:
        numerator = self._load_generation_record(region, year, metric_by_code(metric.numerator or ""))
        denominator = self._load_generation_record(region, year, metric_by_code(metric.denominator or ""))
        router = self._router(metric.code) | {"region_code": region, "year": year, "metric_type": "DERIVED_METRIC"}
        if numerator is None:
            return self._missing(question, router | {"calculation_status": "MISSING_NUMERATOR"}, f"当前缺少 {public_region_label(region)}{year} 年同口径{public_metric_label(metric.numerator or '')}，因此无法可靠计算{metric.label}。")
        if denominator is None:
            return self._missing(question, router | {"calculation_status": "MISSING_DENOMINATOR"}, f"当前缺少 {public_region_label(region)}{year} 年同口径发电总量，因此无法可靠计算{metric.label}。")
        compatible, fields = self._compatible(numerator, denominator)
        if not compatible:
            return self._incompatible_result(question, router, metric, numerator, denominator, fields)
        try:
            numerator_value = Decimal(str(numerator["metric_value"]))
            denominator_value = Decimal(str(denominator["metric_value"]))
            if denominator_value <= 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            return self._missing(question, router | {"calculation_status": "MISSING_DENOMINATOR"}, "分母不是可用于比率计算的正数，因此未执行占比计算。")
        ratio = numerator_value / denominator_value
        scope = str(numerator["statistical_scope"])
        answer = f"{numerator['region_name']}{year}年{metric.label}为 {ratio * Decimal('100'):.2f}%。"
        calculation = {
            "calculation_id": f"CALC:{region}:{year}:{metric.code}", "calculation_type": "RATIO",
            "formula": f"{public_metric_label(metric.numerator or '')} ÷ 发电总量 × 100%", "raw_value": str(ratio),
            "display_value": f"{ratio * Decimal('100'):.2f}%", "status": "CALCULABLE",
            "numerator": self._input_public_dict(numerator, metric.numerator or ""),
            "denominator": self._input_public_dict(denominator, metric.denominator or ""),
            "scope_validation": {"status": "COMPATIBLE", "checked_fields": ["region_code", "stat_year", "metric_basis", "scope_code", "statistical_scope", "metric_unit"]},
        }
        sources = self._sources([numerator, denominator])
        support_ids = [calculation["numerator"]["source_locator"], calculation["denominator"]["source_locator"], calculation["calculation_id"]]
        return {
            "agent_version": "EnergyComputeAI-V6.2", "question": question.strip(), "route": "SQL_CALC",
            "router": router | {"availability": "AVAILABLE", "calculation_status": "CALCULABLE", "statistical_scope": scope, "scope_code": numerator["scope_code"], "metric_basis": numerator["metric_basis"]},
            "decomposition": {"metric_type": "DERIVED_METRIC", "metric": metric.code, "required_metrics": [metric.numerator, metric.denominator]},
            "tool_calls": [{"order": 1, "tool": "PUBLIC_STATISTICS_SQL", "executed": True, "table": "power_source_structure_v2"}, {"order": 2, "tool": "METRIC_CALCULATOR", "executed": True, "calculation_type": "RATIO"}],
            "sql_result": {"generated_sql": "固定指标注册表查询：见两个基础事实来源。", "safety": {"safe": True, "tables": ["power_source_structure_v2", "dim_region", "data_source"]}, "query_result": {"columns": list(numerator), "rows": [list(numerator.values()), list(denominator.values())]}},
            "rag_result": None, "calculation_result": calculation,
            "interpretation": {"response_mode": "DERIVED_METRIC", "answer_status": "ANSWERED", "primary_conclusion": answer, "facts": [{"key": metric.code, "label": metric.label, "value": calculation["display_value"]}], "candidates": [], "warnings": [], "boundaries": [f"计算仅使用同地区、同年份、同一统计口径（{scope}）的两个公开结构化基础事实。"]},
            "synthesis": {"claims": [{"claim_type": "CALC_RESULT", "text": answer, "support_ids": support_ids}], "dropped_claims": []}, "sources": sources, "final_answer": answer,
        }

    def _direct_result(self, question: str, metric: MetricSpec, record: dict[str, Any]) -> dict[str, Any]:
        value = Decimal(str(record["metric_value"]))
        display = f"{value / Decimal('100'):,.2f}亿千瓦时（数据库原值为 GWh）"
        answer = f"{record['region_name']}{record['stat_year']}年{metric.label}为 {display}。"
        source = self._sources([record])[0]
        return {
            "agent_version": "EnergyComputeAI-V6.2", "question": question.strip(), "route": "SQL",
            "router": self._router(metric.code) | {"availability": "AVAILABLE", "metric_type": "DIRECT_METRIC", "region_code": record["region_code"], "year": int(record["stat_year"]), "statistical_scope": record["statistical_scope"], "scope_code": record["scope_code"], "metric_basis": record["metric_basis"]},
            "decomposition": {"metric_type": "DIRECT_METRIC", "metric": metric.code},
            "tool_calls": [{"order": 1, "tool": "PUBLIC_STATISTICS_SQL", "executed": True, "table": "power_source_structure_v2"}],
            "sql_result": {"generated_sql": "固定指标注册表查询：power_source_structure_v2。", "safety": {"safe": True, "tables": ["power_source_structure_v2", "dim_region", "data_source"]}, "query_result": {"columns": list(record), "rows": [list(record.values())]}},
            "rag_result": None,
            "interpretation": {"response_mode": "FACT_LOOKUP", "answer_status": "ANSWERED", "primary_conclusion": answer, "facts": [{"key": metric.code, "label": metric.label, "value": display}], "candidates": [], "warnings": [], "boundaries": [f"统计口径：{record['statistical_scope']}。"]},
            "synthesis": {"claims": [{"claim_type": "PUBLIC_STATISTIC_FACT", "text": answer, "support_ids": [source["source_locator"]]}], "dropped_claims": []}, "sources": [source], "final_answer": answer,
        }

    def _run_legacy_metric(self, question: str) -> dict[str, Any]:
        metric = next((item for item in _LEGACY_METRICS if any(alias in question.casefold() for alias in item[1])), None)
        router = {"route": "SQL", "domain": "POWER", "subdomain": "ELECTRICITY_STATISTICS", "scope": "IN_SCOPE", "source_plan": "PUBLIC_STATISTICS_SQL"}
        region, year = public_region_for(question), self._year(question)
        if metric is None or region is None or year is None:
            return self._missing(question, router, "该问题属于电力统计范围，但需要明确已支持的指标、地区和年份后才能查询。")
        code, _, column, label = metric
        sql = "SELECT r.region_code,r.region_name,s.year,s." + column + " AS metric_value,s.unit_original,s.data_quality,s.notes,d.source_title,d.source_url FROM regional_power_statistics s JOIN dim_region r ON r.region_id=s.region_id LEFT JOIN data_source d ON d.source_id=s.source_id WHERE r.region_code='" + region + "' AND s.year=" + str(year) + " LIMIT 2"
        result = self.executor.execute(sql)
        if not result.rows:
            return self._missing(question, router | {"metric_code": code, "region_code": region, "year": year}, f"该问题属于电力统计范围，但当前本地数据库尚未收录 {public_region_label(region)}{year} 年的 {label}。")
        row = dict(zip(result.columns, result.rows[0], strict=True))
        raw = Decimal(str(row["metric_value"]))
        display = f"{raw / Decimal('100'):,.2f}亿千瓦时（数据库原值为 GWh）" if column.endswith("_gwh") else f"{raw:,.2f}MW"
        answer = f"{row['region_name']}{year}年{label}为 {display}。"
        source = {"source_filename": str(row.get("source_title") or "区域电力统计"), "title": str(row.get("source_title") or "区域电力统计"), "authority_code": "PUBLIC_STATISTICS_DATABASE", "supporting_quote": "本回答基于本地收录的公开统计结构化记录。", "source_locator": f"regional_power_statistics:{region}:{year}:{column}", "official_url": row.get("source_url")}
        return {"agent_version": "EnergyComputeAI-V6.2", "question": question.strip(), "route": "SQL", "router": router | {"metric_code": code, "region_code": region, "year": year, "availability": "AVAILABLE"}, "decomposition": None, "tool_calls": [{"order": 1, "tool": "PUBLIC_STATISTICS_SQL", "executed": True, "table": "regional_power_statistics"}], "sql_result": {"generated_sql": sql, "safety": {"safe": True, "tables": ["regional_power_statistics", "dim_region", "data_source"]}, "query_result": {"columns": result.columns, "rows": result.rows}}, "rag_result": None, "interpretation": {"response_mode": "FACT_LOOKUP", "answer_status": "ANSWERED", "primary_conclusion": answer, "facts": [{"key": code, "label": label, "value": display}], "candidates": [], "warnings": [], "boundaries": []}, "synthesis": {"claims": [{"claim_type": "PUBLIC_STATISTIC_FACT", "text": answer, "support_ids": [source["source_locator"]]}], "dropped_claims": []}, "sources": [source], "final_answer": answer}

    @staticmethod
    def _compatible(numerator: dict[str, Any], denominator: dict[str, Any]) -> tuple[bool, list[str]]:
        fields = ("region_code", "stat_year", "metric_basis", "scope_code", "statistical_scope", "metric_unit")
        incompatible = [field for field in fields if str(numerator.get(field)) != str(denominator.get(field))]
        return not incompatible, incompatible

    @staticmethod
    def _input_public_dict(record: dict[str, Any], metric_code: str) -> dict[str, Any]:
        return {"metric": metric_code, "value": str(record["metric_value"]), "unit": str(record["metric_unit"]), "region_code": str(record["region_code"]), "year": int(record["stat_year"]), "metric_basis": str(record["metric_basis"]), "scope_code": str(record["scope_code"]), "statistical_scope": str(record["statistical_scope"]), "source_locator": f"power_source_structure_v2:{record['region_code']}:{record['stat_year']}:{record['scope_code']}:{record['energy_type_code']}"}

    def _incompatible_result(self, question: str, router: dict[str, Any], metric: MetricSpec, numerator: dict[str, Any], denominator: dict[str, Any], fields: list[str]) -> dict[str, Any]:
        answer = f"{metric.label}的分子与分母统计口径不兼容（差异字段：{'、'.join(fields)}），不能直接计算可靠占比。"
        return {"agent_version": "EnergyComputeAI-V6.2", "question": question.strip(), "route": "IN_SCOPE_DATA_MISSING", "router": router | {"availability": "INCOMPATIBLE_SCOPE", "calculation_status": "INCOMPATIBLE_SCOPE"}, "decomposition": {"metric_type": "DERIVED_METRIC", "metric": metric.code}, "tool_calls": [{"order": 1, "tool": "PUBLIC_STATISTICS_SQL", "executed": True, "table": "power_source_structure_v2"}, {"order": 2, "tool": "METRIC_CALCULATOR", "executed": False, "reason": "INCOMPATIBLE_SCOPE"}], "sql_result": None, "rag_result": None, "interpretation": {"response_mode": "IN_SCOPE_DATA_MISSING", "answer_status": "INCOMPATIBLE_SCOPE", "primary_conclusion": answer, "facts": [], "candidates": [], "warnings": [], "boundaries": ["统计口径不兼容时，系统不会执行计算。"]}, "synthesis": {"claims": [], "dropped_claims": []}, "sources": self._sources([numerator, denominator]), "final_answer": answer}

    @staticmethod
    def _sources(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        for record in records:
            locator = f"power_source_structure_v2:{record['region_code']}:{record['stat_year']}:{record['scope_code']}:{record['energy_type_code']}"
            if any(item["source_locator"] == locator for item in sources):
                continue
            sources.append({"source_filename": str(record.get("source_title") or "电源结构公开统计"), "title": str(record.get("source_title") or "电源结构公开统计"), "authority_code": "PUBLIC_STATISTICS_DATABASE", "supporting_quote": str(record.get("statistical_scope") or "公开统计结构化记录"), "source_locator": locator, "official_url": record.get("source_url"), "issuing_authority": record.get("source_org")})
        return sources

    @staticmethod
    def _router(metric_code: str) -> dict[str, Any]:
        return {"route": "SQL", "domain": "POWER", "subdomain": "ELECTRICITY_STATISTICS", "scope": "IN_SCOPE", "source_plan": "PUBLIC_STATISTICS_SQL", "metric_code": metric_code}

    @staticmethod
    def _year(question: str) -> int | None:
        matched = _YEAR.search(question)
        return int(matched.group(1)) if matched else None

    @staticmethod
    def _missing(question: str, router: dict[str, Any], message: str) -> dict[str, Any]:
        return {"agent_version": "EnergyComputeAI-V6.2", "question": question.strip(), "route": "IN_SCOPE_DATA_MISSING", "router": router | {"route": "IN_SCOPE_DATA_MISSING", "availability": "MISSING"}, "decomposition": None, "tool_calls": [{"order": 1, "tool": "PUBLIC_STATISTICS_SQL", "executed": False}], "sql_result": None, "rag_result": None, "interpretation": {"response_mode": "IN_SCOPE_DATA_MISSING", "answer_status": "MISSING", "primary_conclusion": message, "facts": [], "candidates": [], "warnings": [], "boundaries": ["该问题属于 EnergyComputeAI 的电力统计范围；当前结论仅表示本地数据源不可用。"]}, "synthesis": {"claims": [], "dropped_claims": []}, "sources": [], "final_answer": message}
