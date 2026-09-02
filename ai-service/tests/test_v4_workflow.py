from __future__ import annotations

import sys
import unittest
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.config import Settings
from app.v4_workflow import V4ProjectWorkflow


class StubResolver:
    def resolve(self, question: str):
        if "百旺信" not in question:
            return question, []
        return question, [{"entity_type": "FACILITY", "entity_id": "SZCF016", "canonical_name": "百旺信云数据中心三期"}]


class StubSQLAgent:
    def __init__(self, events: list[str]) -> None:
        self.resolver = StubResolver()
        self.events = events

    def run_sql_fact(self, question: str) -> dict:
        self.events.append("SQL")
        return {
            "sql_result": {
                "query_result": {
                    "columns": ["metric_code", "metric_scope", "metric_value", "metric_unit", "source_id"],
                    "rows": [
                        ["CAPEX", "PHASE_III_EXCHANGE_DISCLOSURE", "32000", "WANYUAN", "EXCHANGE:CAPEX"],
                        ["PUE", "PHASE_III_EXCHANGE_DISCLOSURE", "1.228", "RATIO", "EXCHANGE:PUE"],
                    ],
                },
            },
            "interpretation": {"facts": [], "candidates": [], "boundaries": [], "warnings": []},
            "sources": [{"source_filename": "spdb_power_finance.compute_facility_metric_v1", "source_locator": "compute_facility_metric_v1"}],
        }


class StubPolicyAgent:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def run(self, question: str) -> dict:
        self.events.append("RAG")
        return {
            "rag_result": {
                "answerable": True,
                "references": [{"chunk_id": "POL-029-C0002", "source_filename": "数据中心绿色低碳发展专项行动计划.pdf", "supporting_quote": "严格数据中心项目节能审查。"}],
            },
            "final_answer": "政策检索测试结果。",
        }


def settings() -> Settings:
    return Settings(
        core_dir=None, audit_dir=SERVICE_ROOT / "runtime" / "test-audit", sql_login_path="unused",
        spdb_sql_login_path="unused", spdb_database="spdb_power_finance", mysql_binary=Path("/missing/mysql"),
        cors_allowed_origins=("http://localhost:5173",), max_concurrency=1, database_healthcheck=False,
        sql_debug_enabled=False, sql_debug_token="", policy_rag_index_dir=SERVICE_ROOT / "runtime" / "policy_vector_index" / "public_effective",
    )


class V4ProjectWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.events: list[str] = []
        self.workflow = V4ProjectWorkflow(settings(), StubSQLAgent(self.events), StubPolicyAgent(self.events))  # type: ignore[arg-type]

    def test_support_requires_project_entity_and_finance_or_eligibility_intent(self) -> None:
        self.assertTrue(self.workflow.supports("百旺信按70%贷款、8年期、3.5%利率测算 DSCR"))
        self.assertFalse(self.workflow.supports("数据中心绿色金融政策有哪些？"))
        self.assertFalse(self.workflow.supports("百旺信一定符合绿色贷款吗？"))

    def test_fixed_tool_order_calculates_only_from_sql_fact_and_user_assumptions(self) -> None:
        result = self.workflow.run(
            "百旺信按70%贷款、8年期、3.5%利率，CFADS分别为4800、5100、5400、5500、5600、5700、5800、6000万元，最低DSCR是多少？"
        )
        self.assertEqual(self.events, ["SQL", "RAG"])
        self.assertEqual(result["route"], "BOTH")
        self.assertEqual([item["tool"] for item in result["tool_calls"]], [
            "ENERGY_TEXT_TO_SQL", "POLICY_RAG", "FINANCE_CALCULATOR", "POLICY_ELIGIBILITY_ENGINE", "CLAIM_GROUNDING", "ANSWER_RENDERER",
        ])
        finance = result["finance_result"]
        self.assertEqual(finance["results"]["loan_amount"], "224000000.0")
        self.assertEqual(finance["inputs"]["capex"]["source_type"], "FACT")
        self.assertTrue(all(item["source_type"] == "ASSUMPTION" for item in finance["inputs"]["annual_cfads"]))
        self.assertEqual(result["eligibility_result"]["overall_status"], "INSUFFICIENT_EVIDENCE")
        self.assertTrue(any(item["claim_type"] == "CALC_RESULT" for item in result["synthesis"]["claims"]))
        self.assertIn("不构成绿色贷款认定", result["final_answer"])

    def test_missing_cfads_refuses_calculation_but_still_returns_rule_gaps(self) -> None:
        result = self.workflow.run("百旺信按70%贷款、8年期、3.5%利率，结合绿色金融政策还缺哪些条件？")
        self.assertIsNone(result["finance_result"])
        self.assertIn("逐年 CFADS", result["finance_boundary"])
        self.assertEqual(result["eligibility_result"]["overall_status"], "INSUFFICIENT_EVIDENCE")
        self.assertTrue(any(item["status"] == "UNKNOWN" for item in result["eligibility_result"]["evaluations"]))


if __name__ == "__main__":
    unittest.main()
