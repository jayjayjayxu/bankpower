"""V0.2 SQL-only router for the power and compute database."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import re
from typing import Any

import yaml

from .config import Settings
from .energy_sql import ALLOWED_COLUMNS, ALL_COLUMNS, EnergyTextToSQLPipeline
from .answer_validator import validate_or_fallback
from .result_interpreter import interpret_sql_result
from .sql_answer_renderer import render_sql_answer


_RESOURCE_DIR = Path(__file__).resolve().parents[1] / "resources"
_SCHEMA_PATH = _RESOURCE_DIR / "energy_compute_schema_v02.md"
_ENTITY_PATH = _RESOURCE_DIR / "entity_aliases.yaml"
_COMPANY_ID = re.compile(r"(?<![a-z0-9])(c\d{6})(?![a-z0-9])", re.IGNORECASE)


class EntityResolver:
    """Expand verified aliases into canonical identities for the SQL generator."""

    def __init__(self, path: Path = _ENTITY_PATH) -> None:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        self.entities = list(payload.get("entities") or [])

    def resolve(self, question: str) -> tuple[str, list[dict[str, str]]]:
        normalized = question.casefold()
        matches: list[dict[str, str]] = []
        for entity in self.entities:
            aliases = [str(alias).casefold() for alias in entity.get("aliases") or []]
            if any(alias and alias in normalized for alias in aliases):
                matches.append(
                    {
                        "entity_type": str(entity["entity_type"]),
                        "entity_id": str(entity["entity_id"]),
                        "canonical_name": str(entity["canonical_name"]),
                    }
                )
        # Benchmark and operational users often provide a controlled enterprise
        # key directly (for example C000001), rather than an alias.  Preserve it
        # as a database constraint; it is deliberately *not* a COMPANY entity,
        # so this does not send unknown enterprises into the corporate-analysis
        # route, which is reserved for registered corporate profiles.
        known_ids = {item["entity_id"] for item in matches}
        configured_by_id = {str(item["entity_id"]): item for item in self.entities}
        for found in _COMPANY_ID.finditer(question):
            company_id = found.group(1).upper()
            if company_id in known_ids:
                continue
            configured = configured_by_id.get(company_id)
            if configured is not None:
                matches.append(
                    {
                        "entity_type": str(configured["entity_type"]),
                        "entity_id": company_id,
                        "canonical_name": str(configured["canonical_name"]),
                    }
                )
            else:
                matches.append(
                    {
                        "entity_type": "DATABASE_COMPANY",
                        "entity_id": company_id,
                        "canonical_name": f"企业 {company_id}",
                    }
                )
            known_ids.add(company_id)
        if not matches:
            return question.strip(), []
        details = "；".join(
            (
                f"FACILITY: enterprise_data_center_v2.facility_code = '{item['entity_id']}'"
                f"（{item['canonical_name']}）"
                if item["entity_type"] == "FACILITY"
                else (
                    f"COMPANY: enterprise_profile.company_id = '{item['entity_id']}'"
                    f"（{item['canonical_name']}）"
                    if item["entity_type"] == "COMPANY"
                    else (
                        f"DATABASE_COMPANY: enterprise_profile.company_id = '{item['entity_id']}'"
                        f"（{item['canonical_name']}）"
                        if item["entity_type"] == "DATABASE_COMPANY"
                        else f"{item['entity_type']} {item['entity_id']} = {item['canonical_name']}"
                    )
                )
            )
            for item in matches
        )
        return f"{question.strip()}\n\n系统已解析实体（必须按此标识查询）：{details}", matches


class EnergyComputeAgent:
    """Route V0.2 in-domain questions through the protected SQL pipeline only."""

    _DOMAIN_TERMS = (
        "算力", "智算", "数据中心", "机柜", "上架率", "入住率", "机柜利用率", "pue",
        "电价", "度电", "用电量", "耗电", "电力", "负荷", "储能", "npv", "净现值",
        "dscr", "债务比例", "贷款比例", "gpu", "b200", "h200", "h800", "百旺信",
        "鹏城云脑", "超算", "数据机房",
        # Controlled structured-data vocabulary.  These terms are factual
        # schema concepts, not an expansion into subjective corporate advice.
        "企业", "年度用电", "月度用电", "平均电价", "最大需量", "既有储能",
        "目录电价", "终端电价", "工商业电价", "候选", "映射", "映射状态", "商品映射",
        "模型快照", "运行版本", "模型运行", "分析任务", "已完成分析", "物理容量", "idc", "储能方案",
        "平台资源", "资源清单", "月度电量", "电量", "数据来源类型",
        # Schema identifiers are a supported expert-user interface as well as
        # their Chinese business labels. Keep these at the router so a
        # read-only fact request cannot fall through to the optional legacy
        # core merely because it uses a documented identifier.
        "facility_v2_id", "facility_id", "商品清单", "直接确认", "确认设施",
        "peak_plus_critical_ratio", "尖峰合计占比", "尖峰负荷占比",
        "analysis_run", "analysis_result_snapshot", "completed", "分析运行",
        "完成任务", "任务版本", "运行状态",
    )
    _NON_SQL_JUDGMENT_TERMS = (
        "政策", "训力券", "绿色贷款", "绿色金融", "是否适合", "融资风险", "风险高吗",
        "风险高不高", "管理水平", "服务最好", "服务最", "老板", "ceo", "董事长",
        "授信建议", "贷款建议", "应该贷款", "可不可以贷款", "最值得贷款", "最满意",
        "真实项目cfads", "明天",
    )

    def __init__(
        self,
        settings: Settings,
        pipeline: EnergyTextToSQLPipeline | None = None,
        resolver: EntityResolver | None = None,
    ) -> None:
        self.settings = settings
        self._pipeline = pipeline
        self.resolver = resolver or EntityResolver()

    @classmethod
    def supports(cls, question: str) -> bool:
        lowered = question.casefold()
        return cls.has_sql_fact_signal(question) or any(
            term in lowered for term in cls._NON_SQL_JUDGMENT_TERMS
        )

    @classmethod
    def has_sql_fact_signal(cls, question: str) -> bool:
        """Return true only for a catalogue-backed factual domain signal.

        Judgment terms are deliberately excluded: a policy-only question must
        not acquire a fabricated database subtask in the V0.3 BOTH router.
        """

        lowered = question.casefold()
        # Use the audited schema as the routing vocabulary too. A newly
        # allowlisted field must not require another hand-maintained keyword.
        identifiers = set(re.findall(r"[a-z_][a-z0-9_]*", lowered))
        return bool(identifiers & (ALL_COLUMNS | ALLOWED_COLUMNS.keys())) or any(
            term in lowered for term in cls._DOMAIN_TERMS
        )

    def _pipeline_for_request(self) -> EnergyTextToSQLPipeline:
        if self._pipeline is None:
            self._pipeline = EnergyTextToSQLPipeline(self.settings, _SCHEMA_PATH)
        return self._pipeline

    def run(self, question: str) -> dict[str, Any]:
        if not question.strip():
            raise ValueError("问题不能为空。")
        if self._requires_non_sql_refusal(question):
            return self._out_of_scope(question)
        return self.run_sql_fact(question)

    def run_sql_fact(self, question: str) -> dict[str, Any]:
        """Execute an explicitly isolated database-fact subtask for V0.3 BOTH."""

        if not question.strip():
            raise ValueError("问题不能为空。")
        resolved_question, entities = self.resolver.resolve(question)
        pipeline_result = self._pipeline_for_request().run(resolved_question)
        generated = pipeline_result["generated"]
        safety = pipeline_result["safety"]
        query_result = pipeline_result["result"]
        if pipeline_result["not_answerable"]:
            return self._sql_generation_unavailable(question, generated.raw_sql)
        interpretation = None
        presentation = None
        answer = pipeline_result["answer"]
        if query_result is not None:
            interpreted = interpret_sql_result(question, query_result, entities)
            rendered = render_sql_answer(question, interpreted)
            answer, validation, fallback_used = validate_or_fallback(rendered, interpreted)
            interpretation = interpreted.public_dict()
            presentation = {
                "validator": {"valid": validation.valid, "errors": list(validation.errors)},
                "fallback_used": fallback_used,
            }
        sources = [
            {
                "source_filename": f"spdb_power_finance.{table}",
                "title": f"V0.2 受控 SQL 数据对象：{table}",
                "authority_code": "DATABASE_FACT",
                "supporting_quote": "本回答仅基于已执行的只读 SQL 返回值。",
                "source_locator": table,
            }
            for table in safety.tables
        ]
        return {
            "agent_version": "EnergyComputeAI-V0.3.1-SQL",
            "question": question.strip(),
            "route": "SQL",
            "router": {
                "route": "SQL",
                "reason": "命中电力/算力 SQL 事实查询范围。",
                "entity_resolution": entities,
            },
            "decomposition": None,
            "tool_calls": [
                {
                    "order": 1,
                    "tool": "ENERGY_TEXT_TO_SQL",
                    "schema_version": "V0.2",
                    "tables": list(safety.tables),
                    "executed": bool(safety.safe and query_result is not None),
                }
            ],
            "sql_result": {
                "generated_sql": generated.raw_sql,
                "model": generated.model,
                "usage": generated.usage,
                "safety": asdict(safety),
                "query_result": (
                    {"columns": query_result.columns, "rows": query_result.rows}
                    if query_result is not None
                    else None
                ),
                "presentation": presentation,
            },
            "rag_result": None,
            "interpretation": interpretation,
            "synthesis": None,
            "sources": sources,
            "final_answer": answer,
        }

    def debug_sql(self, question: str) -> dict[str, Any]:
        """Return audit-safe development evidence; caller must apply access control."""

        if self._requires_non_sql_refusal(question):
            return {"route": "OUT_OF_SCOPE", "answer": self._out_of_scope(question)["final_answer"]}
        result = self.run(question)
        if result["route"] != "SQL":
            return {"route": result["route"], "answer": result["final_answer"]}
        sql_result = result["sql_result"]
        return {
            "route": result["route"],
            "generated_sql": sql_result["generated_sql"],
            "safety": sql_result["safety"],
            "query_result": sql_result["query_result"],
            "answer": result["final_answer"],
            "entity_resolution": result["router"].get("entity_resolution", []),
        }

    def _requires_non_sql_refusal(self, question: str) -> bool:
        lowered = question.casefold()
        return any(term in lowered for term in self._NON_SQL_JUDGMENT_TERMS)

    @staticmethod
    def _out_of_scope(question: str, generated_sql: str | None = None) -> dict[str, Any]:
        result = {
            "agent_version": "EnergyComputeAI-V0.3.1-SQL",
            "question": question.strip(),
            "route": "OUT_OF_SCOPE",
            "router": {
                "route": "OUT_OF_SCOPE",
                "reason": "该问题需要政策、融资判断或主观评价，不属于 V0.2 SQL 事实查询。",
            },
            "decomposition": None,
            "tool_calls": [],
            "sql_result": None,
            "rag_result": None,
            "interpretation": None,
            "synthesis": None,
            "sources": [],
            "final_answer": (
                "当前 V0.2 仅回答可由电力/算力数据库直接核验的事实，"
                "不对政策、绿色贷款资格、融资风险或主观优劣作出判断。"
            ),
        }
        if generated_sql:
            result["router"]["generated_sql"] = generated_sql
        return result

    @staticmethod
    def _sql_generation_unavailable(question: str, generated_sql: str) -> dict[str, Any]:
        """Keep a generator abstention distinct from a business scope refusal."""

        return {
            "agent_version": "EnergyComputeAI-V0.3.1-SQL", "question": question.strip(),
            "route": "SQL_GENERATION_UNAVAILABLE",
            "router": {
                "route": "SQL_GENERATION_UNAVAILABLE", "reason": "问题已进入受控 SQL 数据域，但查询生成器未生成可验证 SQL。",
                "generation_status": "NOT_ANSWERABLE_FROM_DB",
            },
            "decomposition": None,
            "tool_calls": [{"order": 1, "tool": "ENERGY_TEXT_TO_SQL", "executed": False, "reason": "NOT_ANSWERABLE_FROM_DB"}],
            "sql_result": {"generated_sql": generated_sql, "safety": {"safe": True, "tables": []}, "query_result": None},
            "rag_result": None, "interpretation": {
                "response_mode": "SQL_GENERATION_UNAVAILABLE", "answer_status": "NOT_ANSWERABLE_FROM_DB",
                "primary_conclusion": "该问题属于当前受控 SQL 数据范围，但当前生成器未形成可验证查询。",
                "facts": [], "candidates": [], "warnings": ["本次未执行数据库查询。"],
                "boundaries": ["该状态不表示数据库不存在相关数据，也不应替代业务判断。"],
            },
            "synthesis": {"claims": [], "dropped_claims": []}, "sources": [],
            "final_answer": "该问题属于当前受控 SQL 数据范围，但当前查询生成器未形成可验证查询；本次未执行数据库查询。这不表示数据库不存在相关数据。",
        }
