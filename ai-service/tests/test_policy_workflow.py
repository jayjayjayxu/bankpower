from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.config import Settings
from app.energy_compute import EntityResolver
from app.policy_workflow import EnergyPolicyBothAgent


def test_settings() -> Settings:
    return Settings(
        core_dir=None,
        audit_dir=Path("runtime/audit"),
        sql_login_path="bank_ai_reader",
        spdb_sql_login_path="bank_ai_local",
        spdb_database="spdb_power_finance",
        mysql_binary=Path("/usr/local/mysql/bin/mysql"),
        cors_allowed_origins=("http://localhost:5173",),
        max_concurrency=1,
        database_healthcheck=False,
        sql_debug_enabled=False,
        sql_debug_token="",
        policy_rag_index_dir=Path("runtime/policy-index"),
    )


class StubSQLAgent:
    def __init__(self, rows: list[list[Any]], events: list[str]) -> None:
        self.rows, self.events = rows, events
        self.resolver = EntityResolver()
        self.questions: list[str] = []

    @staticmethod
    def has_sql_fact_signal(question: str) -> bool:
        return "百旺信" in question or "pue" in question.casefold() or "数据中心" in question

    def run_sql_fact(self, question: str) -> dict[str, Any]:
        self.events.append("sql")
        self.questions.append(question)
        return {
            "route": "SQL",
            "final_answer": "数据库返回了项目 PUE 披露记录。",
            "sources": [{"source_filename": "spdb_power_finance.compute_facility_metric_v1", "authority_code": "DATABASE_FACT"}],
            "sql_result": {
                "query_result": {
                    "columns": ["facility_name", "metric_code", "metric_scope", "metric_value", "metric_unit"],
                    "rows": self.rows,
                }
            },
        }


class StubPolicyAgent:
    def __init__(self, quote: str, events: list[str]) -> None:
        self.quote, self.events = quote, events
        self.questions: list[str] = []

    @staticmethod
    def supports(question: str) -> bool:
        return any(term in question for term in ("政策", "绿色贷款", "绿色金融", "要求"))

    def run(self, question: str) -> dict[str, Any]:
        self.events.append("rag")
        self.questions.append(question)
        return {
            "route": "RAG",
            "router": {"rag_scope": ["DATA_CENTER"]},
            "final_answer": "现行公开政策对数据中心能效提出了要求。",
            "rag_result": {
                "answerable": True,
                "references": [{
                    "chunk_id": "POL-029-C0002",
                    "supporting_quote": self.quote,
                    "source_filename": "数据中心绿色低碳发展专项行动计划.pdf",
                    "title": "数据中心绿色低碳发展专项行动计划",
                }],
            },
        }


class PolicyWorkflowTests(unittest.TestCase):
    def test_both_runs_sql_before_rag_and_refuses_ambiguous_pue_scope(self) -> None:
        events: list[str] = []
        sql = StubSQLAgent([
            ["深圳百旺信智算中心", "PUE", "一期机房", "1.210", "ratio"],
            ["深圳百旺信智算中心", "PUE", "三期机房", "1.228", "ratio"],
        ], events)
        rag = StubPolicyAgent("新建及改扩建大型和超大型数据中心电能利用效率降至1.25以内。", events)
        agent = EnergyPolicyBothAgent(test_settings(), sql_agent=sql, policy_agent=rag)  # type: ignore[arg-type]

        result = agent.run("百旺信智算中心的 PUE 是否符合绿色贷款政策要求？")

        self.assertEqual(events, ["sql", "rag"])
        self.assertNotIn("政策", sql.questions[0])
        self.assertEqual(rag.questions[0], "数据中心 PUE 能效阈值、适用范围以及国家枢纽项目要求是什么？")
        self.assertEqual(result["route"], "BOTH")
        comparison = result["policy_comparison"]
        self.assertEqual(comparison["status"], "INSUFFICIENT_EVIDENCE")
        self.assertIn("多个 PUE 披露口径", comparison["reason"])
        claim = result["synthesis"]["claims"][-1]
        self.assertEqual(claim["claim_type"], "POLICY_COMPARISON")
        self.assertEqual(claim["support_ids"], ["SQL1", "R1"])
        self.assertIn("不能据此判断项目整体政策资格", result["final_answer"])

    def test_single_disclosed_scope_can_only_return_single_metric_match(self) -> None:
        events: list[str] = []
        sql = StubSQLAgent([["深圳百旺信智算中心", "PUE", "新建大型数据中心", "1.210", "ratio"]], events)
        rag = StubPolicyAgent("新建大型数据中心 PUE 不得高于1.25。", events)
        agent = EnergyPolicyBothAgent(test_settings(), sql_agent=sql, policy_agent=rag)  # type: ignore[arg-type]

        result = agent.run("百旺信智算中心 PUE 是否符合政策要求？")

        self.assertEqual(result["policy_comparison"]["status"], "MATCH")
        self.assertIn("PUE 这一单项指标", result["final_answer"])
        self.assertIn("不是项目整体政策资格", result["final_answer"])

    def test_both_router_requires_a_resolved_project_entity(self) -> None:
        events: list[str] = []
        agent = EnergyPolicyBothAgent(
            test_settings(),
            sql_agent=StubSQLAgent([], events),  # type: ignore[arg-type]
            policy_agent=StubPolicyAgent("PUE 不高于1.25。", events),  # type: ignore[arg-type]
        )
        self.assertFalse(agent.supports("新建数据中心 PUE 政策要求是什么？"))
        self.assertTrue(agent.supports("百旺信智算中心 PUE 政策要求是什么？"))


if __name__ == "__main__":
    unittest.main()
