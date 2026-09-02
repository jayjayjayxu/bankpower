from __future__ import annotations

import sys
import unittest
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.conversation import ConversationService


class ConversationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.questions: list[str] = []

        def run_agent(question: str) -> dict:
            self.questions.append(question)
            return {
                "question": question,
                "route": "SQL",
                "router": {
                    "route": "SQL",
                    "entity_resolution": [{
                        "entity_type": "FACILITY", "entity_id": "SZCF016",
                        "canonical_name": "深圳百旺信智算中心",
                    }],
                },
                "sql_result": {"query_result": {"columns": ["metric_value"], "rows": [["0.6542"]]}},
                "rag_result": None,
                "interpretation": {"facts": [{"label": "上架率", "value": "65.42%"}]},
                "sources": [{"title": "受控 SQL", "source_locator": "compute_facility_operation_fact_v1"}],
                "synthesis": {"claims": [], "dropped_claims": []},
                "final_answer": "测试结果。",
            }

        self.service = ConversationService(run_agent)

    def test_year_metric_and_provenance_followups_reuse_only_verified_context(self) -> None:
        state, first, first_effective = self.service.run("百旺信2025年上架率多少？")
        self.assertEqual(first_effective, "百旺信2025年上架率多少？")
        self.assertEqual(state.active_entities[0]["id"], "SZCF016")
        self.assertEqual(state.active_year, 2025)
        self.assertEqual(state.active_metrics, ["rack_occupancy_rate"])

        state, second, second_effective = self.service.run("那2024年呢？", state.session_id)
        self.assertIn("深圳百旺信智算中心2024年上架率是多少", second_effective)
        self.assertEqual(state.active_year, 2024)

        state, third, third_effective = self.service.run("再看看PUE。", state.session_id)
        self.assertIn("深圳百旺信智算中心2024年PUE是多少", third_effective)
        self.assertEqual(state.active_metrics, ["pue"])

        state, provenance, effective = self.service.run("这个PUE数据来源是什么？", state.session_id)
        self.assertEqual(provenance["route"], "PROVENANCE")
        self.assertEqual(effective, "这个PUE数据来源是什么？")
        self.assertEqual(len(self.questions), 3)
        self.assertEqual(provenance["sql_result"], third["sql_result"])

    def test_ambiguous_utilization_asks_for_clarification_without_tool_execution(self) -> None:
        state, result, _ = self.service.run("利用率是多少？")
        self.assertEqual(result["route"], "CLARIFICATION")
        self.assertIn("机柜上架率", result["final_answer"])
        self.assertEqual(self.questions, [])
        self.assertEqual(state.active_entities, [])

    def test_candidate_result_cannot_become_active_entity(self) -> None:
        def candidate_agent(question: str) -> dict:
            return {
                "question": question, "route": "SQL", "router": {"route": "SQL", "entity_resolution": []},
                "sql_result": None, "rag_result": None,
                "interpretation": {"candidates": [{"name": "候选中心", "role": "CANDIDATE"}]},
                "sources": [], "synthesis": {"claims": [], "dropped_claims": []}, "final_answer": "候选参照。",
            }
        state, _, _ = ConversationService(candidate_agent).run("B200 对应哪里？")
        self.assertEqual(state.active_entities, [])


if __name__ == "__main__":
    unittest.main()
