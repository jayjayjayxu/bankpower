"""V0.2 SQL-only router for the power and compute database."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from .config import Settings
from .energy_sql import EnergyTextToSQLPipeline


_RESOURCE_DIR = Path(__file__).resolve().parents[1] / "resources"
_SCHEMA_PATH = _RESOURCE_DIR / "energy_compute_schema_v02.md"
_ENTITY_PATH = _RESOURCE_DIR / "entity_aliases.yaml"


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
        if not matches:
            return question.strip(), []
        details = "；".join(
            f"{item['entity_type']} {item['entity_id']} = {item['canonical_name']}"
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
        return any(term in lowered for term in cls._DOMAIN_TERMS) or any(
            term in lowered for term in cls._NON_SQL_JUDGMENT_TERMS
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
        resolved_question, entities = self.resolver.resolve(question)
        pipeline_result = self._pipeline_for_request().run(resolved_question)
        generated = pipeline_result["generated"]
        safety = pipeline_result["safety"]
        query_result = pipeline_result["result"]
        if pipeline_result["not_answerable"]:
            return self._out_of_scope(question, generated.raw_sql)
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
            "agent_version": "EnergyComputeAI-V0.2-SQL",
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
            },
            "rag_result": None,
            "synthesis": None,
            "sources": sources,
            "final_answer": pipeline_result["answer"],
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
            "agent_version": "EnergyComputeAI-V0.2-SQL",
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
