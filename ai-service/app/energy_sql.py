"""Auditable Text-to-SQL primitives for the V0.2 energy/compute scope."""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import StringIO
from pathlib import Path
from typing import Any, Protocol

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from .config import Settings


ALLOWED_SCHEMA = "spdb_power_finance"
ALLOWED_COLUMNS: dict[str, set[str]] = {
    "enterprise_data_center_v2": {
        "facility_v2_id", "facility_code", "official_name", "facility_alias", "facility_kind",
        "locality_scope", "province_name", "city_name", "district_name", "operator_company_id",
        "operator_name", "owner_name", "lifecycle_status", "operation_start_date",
        "physical_capacity_countable", "green_certification", "last_verified_date", "data_type",
        "data_quality", "notes",
    },
    "compute_facility_metric_v1": {
        "facility_metric_id", "facility_v2_id", "metric_code", "metric_scope", "metric_value",
        "metric_value_upper", "metric_text", "metric_unit", "compute_precision", "value_operator",
        "disclosure_status", "as_of_date", "statistical_scope", "usable_for_facility_model",
        "source_locator", "evidence_grade", "data_quality", "notes",
    },
    "compute_facility_operation_fact_v1": {
        "operation_fact_id", "facility_v2_id", "operation_scope_code", "operation_scope_name",
        "fact_year", "fact_period", "rack_capacity_count", "average_occupied_rack_count",
        "rack_utilization_ratio", "high_power_occupied_rack_count", "high_power_threshold_kw",
        "hosting_revenue_wanyuan", "hosting_cost_wanyuan", "hosting_gross_margin",
        "average_rack_price_yuan_month", "average_rack_cost_yuan_month", "electricity_consumption_kwh",
        "electricity_purchase_wanyuan", "electricity_purchase_tax_included_wanyuan",
        "electricity_purchase_price_yuan_kwh", "electricity_purchase_price_tax_included_flag",
        "electricity_cost_revenue_ratio", "hosting_revenue_yuan_kwh", "source_locator", "data_type",
        "data_quality", "notes",
    },
    "compute_facility_rack_price_tier_fact_v1": {
        "rack_price_tier_fact_id", "facility_v2_id", "building_scope_code", "fact_year", "fact_period",
        "power_tier_code", "power_from_kw", "power_to_kw", "upper_bound_inclusive",
        "actual_average_price_yuan_rack_month", "source_locator", "data_type", "data_quality", "notes",
    },
    "compute_platform_resource_listing_v1": {
        "listing_id", "platform_id", "facility_v2_id", "external_product_id", "product_name",
        "provider_name", "resource_type", "accelerator_model", "accelerator_count",
        "accelerator_memory_gb", "cpu_cores", "system_memory_gb", "compute_capacity_value",
        "compute_capacity_unit", "compute_precision", "platform_region_label", "available_zone",
        "physical_region_text", "locality_scope", "availability_status", "source_updated_at",
        "source_api_url", "captured_at", "data_quality", "notes",
    },
    "compute_listing_candidate_mapping_v1": {
        "candidate_mapping_id", "listing_id", "candidate_mapping_type", "candidate_entity_type",
        "candidate_name", "candidate_facility_v2_id", "mapping_status", "confidence_level",
        "confidence_score", "direct_sku_evidence_flag", "platform_relation_evidence_flag",
        "candidate_asset_evidence_flag", "source_locator", "evidence_summary", "boundary_note",
        "verified_at", "data_type", "data_quality", "model_version", "updated_at",
    },
    "enterprise_profile": {
        "company_id", "company_name", "company_alias", "city_name", "district_name", "industry_name",
        "power_chain_role", "energy_customer_type", "high_power_user_flag", "data_center_flag",
        "manufacturing_flag", "energy_company_flag", "existing_solar_flag", "existing_solar_mw",
        "existing_storage_flag", "existing_storage_mwh", "vpp_participant_flag", "green_power_flag",
        "green_power_ratio", "verification_priority", "business_verification_status", "notes",
    },
    "enterprise_monthly_power": {
        "record_id", "company_id", "load_scenario_id", "year", "month", "power_consumption_kwh",
        "power_yoy", "power_mom", "electricity_cost_yuan", "average_price_yuan_kwh", "peak_power_kwh",
        "flat_power_kwh", "valley_power_kwh", "critical_peak_kwh", "peak_ratio", "valley_ratio",
        "max_demand_kw", "energy_charge_yuan", "demand_charge_yuan", "basic_charge_method",
        "demand_price", "data_type", "data_quality", "is_derived", "calculation_formula", "notes",
    },
    "v_enterprise_annual_energy_summary": {
        "company_id", "year", "annual_power_kwh", "annual_electricity_cost_yuan", "avg_cost_yuan_kwh",
        "peak_plus_critical_ratio", "valley_ratio", "annual_max_demand_kw", "data_type",
    },
    "electricity_tariff": {
        "tariff_id", "region_id", "price_zone_id", "year", "month", "effective_date", "expiry_date",
        "customer_type", "voltage_level", "market_type", "time_period", "start_time_text", "end_time_text",
        "energy_price_yuan_kwh", "transmission_price_yuan_kwh", "line_loss_price_yuan_kwh",
        "system_operation_yuan_kwh", "government_fund_yuan_kwh", "capacity_price", "capacity_price_unit",
        "demand_price", "demand_price_unit", "final_price_yuan_kwh", "statistical_scope", "notes",
    },
    "analysis_run": {
        "run_id", "run_name", "model_version", "storage_version", "finance_version", "policy_version",
        "run_type", "analysis_year", "description", "created_time", "completed_time", "created_by", "status",
    },
    "analysis_result_snapshot": {
        "snapshot_id", "run_id", "company_id", "company_name", "snapshot_version", "analysis_date",
        "model_version", "storage_version", "finance_version", "policy_version", "data_type",
        "storage_power_mw", "storage_capacity_mwh", "storage_duration_hour", "storage_configuration",
        "capex_wanyuan", "annual_benefit_wanyuan", "npv_wanyuan", "irr", "payback_year",
        "base_debt_ratio", "base_loan_amount_wanyuan", "base_min_dscr", "max_debt_ratio",
        "max_loan_amount_wanyuan", "financing_status", "tariff_spread_risk", "capex_risk",
        "grid_capacity_risk", "degradation_risk", "overall_risk", "overall_sensitivity_risk",
        "opportunity_level", "readiness_level", "risk_level", "recommended_product",
        "recommended_product_status", "potential_financing_amount_wanyuan", "business_priority",
        "summary_title", "recommendation_text", "risk_summary", "created_time",
    },
}
ALL_COLUMNS = set().union(*ALLOWED_COLUMNS.values())
FORBIDDEN_NODE_NAMES = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "COMMAND", "MERGE", "GRANT",
    "REVOKE", "TRUNCATETABLE", "USE", "SET", "LOCK", "TRANSACTION", "COMMIT", "ROLLBACK",
    "INTO", "LOADDATA",
}
FORBIDDEN_FUNCTIONS = {"SLEEP", "BENCHMARK", "LOAD_FILE", "GET_LOCK", "RELEASE_LOCK"}
NOT_ANSWERABLE_SQL = "SELECT 'NOT_ANSWERABLE_FROM_DB' AS error_code LIMIT 1;"


@dataclass(frozen=True)
class GeneratedSQL:
    question: str
    raw_sql: str
    model: str
    usage: dict[str, Any]


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[list[str]]


@dataclass(frozen=True)
class SafetyResult:
    safe: bool
    sql: str
    errors: tuple[str, ...]
    tables: tuple[str, ...] = ()


class SQLGenerator(Protocol):
    def generate(self, question: str) -> GeneratedSQL: ...


class SQLExecutor(Protocol):
    def execute(self, sql: str) -> QueryResult: ...


class ResultSummarizer(Protocol):
    def summarize(self, question: str, result: QueryResult) -> str: ...


SQL_SYSTEM_PROMPT = """You are the EnergyComputeAI V0.2 Text-to-SQL generator.

Generate one MySQL 8 read-only query using only the supplied AI Schema Dictionary.
Rules:
1. Use only SELECT or WITH ... SELECT. Never generate writes, DDL, locks, variables, file access, or system functions.
2. Use only documented objects, fields, enums, and joins. Do not invent facts, entities, fields, or relationships.
3. Detail queries require a constant LIMIT no greater than 100. Never use SELECT *.
4. The terms 上架率, 入住率, and 机柜利用率 mean rack_utilization_ratio only; never GPU, equipment, or storage utilization.
   For this metric use compute_facility_operation_fact_v1. That table has no metric_unit field; return operation_scope_name, fact_year, fact_period, and rack_utilization_ratio instead.
   When a user asks for a facility's annual metric without naming a building, select the whole-facility annual scope when it exists. For 深圳百旺信智算中心 this is operation_scope_code='WHOLE_FACILITY_BUILDING_1_4_SELF_BUILT' and fact_period='ANNUAL'; never mix it with BUILDING_1 or BUILDING_4 H1 values.
   For “平均机柜价格” or “平均机柜托管价格” without a specified building or power tier, use compute_facility_operation_fact_v1.average_rack_price_yuan_month in that same operation scope. Do not join compute_facility_rack_price_tier_fact_v1 unless the question explicitly asks for a building or power-tier price.
5. PUE must filter metric_code='PUE' and return metric_scope, as_of_date, disclosure_status, and metric_unit.
   When a single question asks PUE together with 上架率/平均机柜价格, every requested numeric value must be selected and returned.
   Use a UNION ALL result with common columns metric_name, metric_scope, metric_value, metric_unit, as_of_date, disclosure_status when the values are in different tables:
   - PUE: select m.metric_value and m.metric_unit from compute_facility_metric_v1 with metric_code='PUE'.
   - 上架率: select o.rack_utilization_ratio AS metric_value and literal 'RATIO' AS metric_unit from compute_facility_operation_fact_v1.
   - 平均机柜价格: select o.average_rack_price_yuan_month AS metric_value and literal 'CNY/RACK/MONTH' AS metric_unit from compute_facility_operation_fact_v1.
   A year such as 2025 applies to operation facts through fact_year; do not filter PUE by as_of_date unless the user explicitly asks for the PUE disclosure date.
6. Do not convert database units. Return raw field values with their documented unit columns or names.
7. A product-to-facility mapping is an actual facility mapping only when mapping_status='CONFIRMED'. Other states are candidates.
   For questions such as “B200-C4-1对应哪个数据中心”, query the listing and candidate-mapping objects and return mapping_status and boundary_note even when no mapping is CONFIRMED; do not use NOT_ANSWERABLE_FROM_DB for this case.
   For that product-mapping question, return only external_product_id, product_name, provider_name, platform_region_label, mapping_status, candidate_name, candidate_facility_v2_id, facility_code, official_name, source_locator, evidence_summary, and boundary_note as applicable. Never enumerate all listing, mapping, or facility fields; never use SELECT *.
8. analysis_result_snapshot contains research model snapshots; retrieve its facts but never draw a credit, finance-risk, policy, or quality conclusion.
9. For policy, green-loan eligibility, finance risk, subjective ranking, CEO, or unavailable information, output exactly:
SELECT 'NOT_ANSWERABLE_FROM_DB' AS error_code LIMIT 1;
10. Output SQL only, without Markdown or explanation.
"""

SUMMARY_SYSTEM_PROMPT = """You summarize already-executed EnergyComputeAI V0.2 SQL results in concise Chinese.
Use only the supplied columns and rows. Never generate SQL, add external knowledge, change number precision or unit, treat scenarios as verified facts, treat a candidate mapping as confirmed, or make policy, credit, financing-risk, or subjective-quality conclusions. If rows are empty, reply exactly: 没有查询到符合条件的数据。"""


class DeepSeekEnergySQLGenerator:
    def __init__(self, schema_text: str) -> None:
        self.schema_text = schema_text
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not self.api_key:
            raise RuntimeError("未设置 DEEPSEEK_API_KEY。")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

    def generate(self, question: str) -> GeneratedSQL:
        from openai import OpenAI

        response = OpenAI(api_key=self.api_key, base_url=self.base_url).chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SQL_SYSTEM_PROMPT},
                {"role": "user", "content": f"AI Schema Dictionary:\n{self.schema_text}\n\n用户问题:\n{question}"},
            ],
            temperature=0,
            max_tokens=1_200,
            stream=False,
            extra_body={"thinking": {"type": "disabled"}},
        )
        return GeneratedSQL(
            question=question,
            raw_sql=response.choices[0].message.content or "",
            model=response.model or self.model,
            usage=response.usage.model_dump() if response.usage else {},
        )


class DeepSeekEnergyResultSummarizer:
    def __init__(self) -> None:
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not self.api_key:
            raise RuntimeError("未设置 DEEPSEEK_API_KEY。")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

    def summarize(self, question: str, result: QueryResult) -> str:
        if not result.rows:
            return "没有查询到符合条件的数据。"
        if len(result.rows) > 100:
            raise ValueError("查询结果超过 100 行，拒绝交给总结模型。")
        from openai import OpenAI

        evidence = json.dumps(
            {"columns": result.columns, "rows": result.rows},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        response = OpenAI(api_key=self.api_key, base_url=self.base_url).chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": f"用户问题:\n{question}\n\n已执行 SQL 的结果:\n{evidence}"},
            ],
            temperature=0,
            max_tokens=1_200,
            stream=False,
            extra_body={"thinking": {"type": "disabled"}},
        )
        answer = (response.choices[0].message.content or "").strip()
        if not answer:
            raise RuntimeError("结果总结模型返回空内容。")
        return answer


class DeterministicResultPresenter:
    """Present executed values verbatim so the model cannot alter units or precision."""

    _RATIO_FIELDS = {
        "rack_utilization_ratio", "hosting_gross_margin", "electricity_cost_revenue_ratio",
        "power_yoy", "power_mom", "peak_ratio", "valley_ratio", "green_power_ratio",
        "peak_plus_critical_ratio", "irr", "base_debt_ratio", "base_min_dscr", "max_debt_ratio",
    }
    _FIELD_UNITS = {
        "rack_capacity_count": "柜", "average_occupied_rack_count": "柜",
        "high_power_occupied_rack_count": "柜", "high_power_threshold_kw": "kW",
        "average_rack_price_yuan_month": "元/柜/月",
        "average_rack_cost_yuan_month": "元/柜/月",
        "actual_average_price_yuan_rack_month": "元/柜/月",
        "electricity_consumption_kwh": "kWh", "electricity_purchase_wanyuan": "万元",
        "electricity_purchase_tax_included_wanyuan": "万元",
        "electricity_purchase_price_yuan_kwh": "元/kWh",
        "hosting_revenue_yuan_kwh": "元/kWh", "annual_power_kwh": "kWh",
        "annual_electricity_cost_yuan": "元", "avg_cost_yuan_kwh": "元/kWh",
        "annual_max_demand_kw": "kW", "power_consumption_kwh": "kWh",
        "electricity_cost_yuan": "元", "max_demand_kw": "kW", "final_price_yuan_kwh": "元/kWh",
        "storage_power_mw": "MW", "storage_capacity_mwh": "MWh",
        "capex_wanyuan": "万元", "annual_benefit_wanyuan": "万元", "npv_wanyuan": "万元",
        "base_loan_amount_wanyuan": "万元", "max_loan_amount_wanyuan": "万元",
        "potential_financing_amount_wanyuan": "万元",
    }

    def summarize(self, question: str, result: QueryResult) -> str:
        if not result.rows:
            return "没有查询到符合条件的数据。"
        if len(result.rows) > 20:
            return (
                f"查询已完成，共返回 {len(result.rows)} 条记录。"
                "请以“数据依据”中的数据库原始值、字段名和单位口径为准。"
            )
        lines = ["查询已完成。以下值保持数据库原始精度和单位口径："]
        for index, row in enumerate(result.rows, start=1):
            pairs = "；".join(
                self._format_value(column, value)
                for column, value in zip(result.columns, row, strict=True)
            )
            lines.append(f"{index}. {pairs}")
        return "\n".join(lines)

    @classmethod
    def _format_value(cls, column: str, value: str) -> str:
        if column in cls._RATIO_FIELDS:
            try:
                percentage = (Decimal(value) * 100).normalize()
            except (InvalidOperation, ValueError):
                return f"{column}={value}（数据库小数比率）"
            percentage_text = format(percentage, "f").rstrip("0").rstrip(".") or "0"
            return f"{column}={value}（数据库小数比率；程序换算 {percentage_text}%）"
        unit = cls._FIELD_UNITS.get(column)
        return f"{column}={value}" + (f"（{unit}）" if unit else "")


class SpdbReadOnlyExecutor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def execute(self, sql: str) -> QueryResult:
        payload = (
            "SET SESSION MAX_EXECUTION_TIME=5000;\n"
            "START TRANSACTION READ ONLY;\n"
            + sql.rstrip(";\n")
            + ";\nROLLBACK;\n"
        )
        completed = subprocess.run(
            [
                str(self.settings.mysql_binary),
                f"--login-path={self.settings.spdb_sql_login_path}",
                "--default-character-set=utf8mb4",
                "--batch",
                "--raw",
                self.settings.spdb_database,
            ],
            input=payload,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
        if completed.returncode:
            raise RuntimeError(completed.stderr.strip() or "spdb_power_finance 查询失败。")
        if not completed.stdout.strip():
            return QueryResult([], [])
        parsed = list(csv.reader(StringIO(completed.stdout), delimiter="\t"))
        return QueryResult(parsed[0], parsed[1:])


def is_not_answerable_sql(raw_sql: str) -> bool:
    normalized = re.sub(r"\s+", " ", raw_sql.strip().rstrip(";")).upper()
    return normalized == "SELECT 'NOT_ANSWERABLE_FROM_DB' AS ERROR_CODE LIMIT 1"


def validate_energy_sql(raw_sql: str) -> SafetyResult:
    errors: list[str] = []
    sql = raw_sql.strip()
    if not sql:
        return SafetyResult(False, "", ("SQL 为空。",))
    if chr(96) * 3 in sql:
        errors.append("输出包含 Markdown 代码围栏，不是纯 SQL。")
    if re.search(r"(?i)\bINTO\s+(OUTFILE|DUMPFILE)\b", sql):
        errors.append("包含禁止的文件写出操作。")
    if not re.match(r"(?is)^(SELECT|WITH)\b", sql):
        errors.append("SQL 必须以 SELECT 或 WITH 开始。")
    try:
        statements = sqlglot.parse(sql, read="mysql")
    except ParseError as exc:
        return SafetyResult(False, sql, tuple(errors + [f"MySQL 语法解析失败: {exc}"]))
    if len(statements) != 1:
        errors.append("只允许一个 SQL 语句。")
    if not statements:
        return SafetyResult(False, sql, tuple(errors + ["没有可解析的 SQL 语句。"]))
    tree = statements[0]
    if not isinstance(tree, exp.Query):
        errors.append("根语句不是只读查询。")
    for star in tree.find_all(exp.Star):
        if not isinstance(star.parent, exp.Count):
            errors.append("禁止 SELECT *，必须显式列出白名单字段。")
    for node in tree.walk():
        if type(node).__name__.upper() in FORBIDDEN_NODE_NAMES:
            errors.append(f"包含禁止的 SQL 节点: {type(node).__name__}")
    canonical = tree.sql(dialect="mysql", pretty=True)
    if re.search(r"(?i)\b(FOR\s+UPDATE|LOCK\s+IN\s+SHARE\s+MODE|INTO\s+(OUTFILE|DUMPFILE))\b", canonical):
        errors.append("包含锁定或文件写出操作。")
    if "@" in canonical:
        errors.append("禁止使用 MySQL 用户变量或系统变量。")
    for function in tree.find_all(exp.Func):
        name = (function.name if isinstance(function, exp.Anonymous) else function.sql_name()).upper()
        if name in FORBIDDEN_FUNCTIONS:
            errors.append(f"包含禁止函数: {name}")

    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    real_tables: list[str] = []
    aliases: dict[str, str] = {}
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        if name in cte_names:
            continue
        database = (table.db or "").lower()
        if database and database != ALLOWED_SCHEMA:
            errors.append(f"禁止访问数据库: {database}")
        if name not in ALLOWED_COLUMNS:
            errors.append(f"禁止或不存在的表/视图: {name}")
            continue
        real_tables.append(name)
        aliases[(table.alias_or_name or name).lower()] = name
        aliases[name] = name
    if not real_tables:
        errors.append("查询必须访问 V0.2 白名单表或视图。")
    if len(set(real_tables)) > 4:
        errors.append("单个查询最多访问 4 个白名单表或视图。")


    projection_aliases = {
        projection.alias.lower()
        for select in tree.find_all(exp.Select)
        for projection in select.expressions
        if projection.alias
    }
    for column in tree.find_all(exp.Column):
        name = column.name.lower()
        qualifier = (column.table or "").lower()
        if qualifier in cte_names:
            continue
        if qualifier and qualifier in aliases:
            table_name = aliases[qualifier]
            if name not in ALLOWED_COLUMNS[table_name]:
                errors.append(f"表/视图 {table_name} 不存在字段: {name}")
        elif qualifier and qualifier not in aliases:
            continue
        elif name not in ALL_COLUMNS and name not in projection_aliases:
            errors.append(f"V0.2 白名单中不存在字段: {name}")

    limit = tree.args.get("limit")
    has_grouping = bool(tree.find(exp.Group))
    has_aggregate = any(True for _ in tree.find_all(exp.AggFunc))
    has_distinct = any(bool(select.args.get("distinct")) for select in tree.find_all(exp.Select))
    if not (has_grouping or has_aggregate or has_distinct) and limit is None:
        errors.append("明细查询必须包含 LIMIT，默认应为 LIMIT 100。")
    if limit is not None:
        expression = limit.expression
        if not isinstance(expression, exp.Literal) or not expression.is_int:
            errors.append("LIMIT 必须是整数常量。")
        elif int(expression.this) > 100:
            errors.append("LIMIT 不得超过 100。")
    return SafetyResult(
        safe=not errors,
        sql=canonical.rstrip(";") + ";",
        errors=tuple(dict.fromkeys(errors)),
        tables=tuple(sorted(set(real_tables))),
    )


class EnergyTextToSQLPipeline:
    """Generate, validate, execute and summarize a V0.2 SQL question."""

    def __init__(
        self,
        settings: Settings,
        schema_path: Path,
        generator: SQLGenerator | None = None,
        executor: SQLExecutor | None = None,
        summarizer: ResultSummarizer | None = None,
    ) -> None:
        self.generator = generator or DeepSeekEnergySQLGenerator(schema_path.read_text(encoding="utf-8"))
        self.executor = executor or SpdbReadOnlyExecutor(settings)
        self.summarizer = summarizer or DeterministicResultPresenter()

    def run(self, question: str) -> dict[str, Any]:
        generated = self.generator.generate(question)
        if is_not_answerable_sql(generated.raw_sql):
            return {
                "generated": generated,
                "safety": SafetyResult(True, NOT_ANSWERABLE_SQL, (), ()),
                "result": None,
                "answer": "当前 V0.2 SQL 数据库无法回答该问题；它只提供可核验的电力、算力和模型结果事实，不做政策、融资风险或主观优劣判断。",
                "not_answerable": True,
            }
        safety = validate_energy_sql(generated.raw_sql)
        attempts = [generated.raw_sql]
        if not safety.safe:
            repair_question = (
                f"{question}\n\n上一次生成的 SQL 未通过校验。只修复下列错误后重新输出一条纯 SQL："
                f"{'；'.join(safety.errors)}\n上一次 SQL：\n{generated.raw_sql}"
            )
            generated = self.generator.generate(repair_question)
            attempts.append(generated.raw_sql)
            if is_not_answerable_sql(generated.raw_sql):
                return {
                    "generated": generated,
                    "generated_attempts": attempts,
                    "safety": SafetyResult(True, NOT_ANSWERABLE_SQL, (), ()),
                    "result": None,
                    "answer": "当前 V0.2 SQL 数据库无法回答该问题；它只提供可核验的电力、算力和模型结果事实，不做政策、融资风险或主观优劣判断。",
                    "not_answerable": True,
                }
            safety = validate_energy_sql(generated.raw_sql)
        if not safety.safe:
            return {
                "generated": generated,
                "generated_attempts": attempts,
                "safety": safety,
                "result": None,
                "answer": "该问题未执行查询：生成的 SQL 未通过只读安全和 Schema 白名单校验。",
                "not_answerable": False,
            }
        result = self.executor.execute(safety.sql)
        try:
            answer = self.summarizer.summarize(question, result)
        except Exception:
            answer = "查询已完成；请以“数据依据”中的原始结果为准。"
        return {
            "generated": generated,
            "generated_attempts": attempts,
            "safety": safety,
            "result": result,
            "answer": answer,
            "not_answerable": False,
        }
