from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.conversation import ConversationService, SQLiteConversationStore
from app.finance import FinanceCalculator, FinanceInput, ProvenancedValue, RepaymentMethod, SourceType


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

    def test_finance_followup_changes_only_explicit_user_assumption(self) -> None:
        inputs = FinanceInput(
            project_id="SZCF016",
            capex=ProvenancedValue.of("100000000", "CNY", SourceType.FACT, "SQL:CAPEX"),
            debt_ratio=ProvenancedValue.of("0.60", "RATIO", SourceType.ASSUMPTION, "USER:debt_ratio"),
            interest_rate=ProvenancedValue.of("0.035", "RATIO", SourceType.ASSUMPTION, "USER:interest_rate"),
            loan_term_years=ProvenancedValue.of("2", "YEAR", SourceType.ASSUMPTION, "USER:loan_term_years"),
            repayment_method=RepaymentMethod.EQUAL_PRINCIPAL,
            annual_cfads=(
                ProvenancedValue.of("50000000", "CNY", SourceType.ASSUMPTION, "USER:annual_cfads:1"),
                ProvenancedValue.of("50000000", "CNY", SourceType.ASSUMPTION, "USER:annual_cfads:2"),
            ),
            required_min_dscr=ProvenancedValue.of("1.20", "RATIO", SourceType.ASSUMPTION, "USER:required_min_dscr"),
        )
        original = FinanceCalculator().calculate(inputs).public_dict()
        calls: list[str] = []

        def finance_agent(question: str) -> dict:
            calls.append(question)
            return {
                "question": question, "route": "BOTH",
                "router": {"route": "BOTH", "entity_resolution": [{"entity_type": "FACILITY", "entity_id": "SZCF016", "canonical_name": "深圳百旺信智算中心"}]},
                "sql_result": {"query_result": {"columns": [], "rows": []}}, "rag_result": None,
                "interpretation": None, "finance_result": original, "eligibility_result": {},
                "sources": [], "synthesis": {"claims": [], "dropped_claims": []}, "final_answer": "初始测算。",
            }

        service = ConversationService(finance_agent)
        state, _, _ = service.run("百旺信按60%贷款、2年期、3.5%利率，CFADS分别为5000、5000万元，最低DSCR是多少？")
        state, modified, _ = service.run("改成70%。", state.session_id)
        self.assertEqual(modified["route"], "FINANCE_FOLLOW_UP")
        self.assertEqual(modified["finance_result"]["inputs"]["debt_ratio"]["value"], "0.7")
        self.assertEqual(modified["finance_result"]["inputs"]["interest_rate"]["value"], "0.035")
        self.assertEqual(len(calls), 1)

        _, changed_rate, _ = service.run("利率改成4%。", state.session_id)
        self.assertEqual(changed_rate["finance_result"]["inputs"]["debt_ratio"]["value"], "0.7")
        self.assertEqual(changed_rate["finance_result"]["inputs"]["interest_rate"]["value"], "0.04")
        self.assertEqual(len(calls), 1)

        service.clear_finance_assumptions(state.session_id)
        _, cleared, _ = service.run("改成80%。", state.session_id)
        self.assertEqual(cleared["route"], "CLARIFICATION")
        self.assertIn("已清除", cleared["final_answer"])
        self.assertEqual(len(calls), 1)

    def test_due_diligence_followup_reuses_completed_snapshot_without_rerun(self) -> None:
        runs: list[str] = []

        def due_runner(project_id: str) -> dict:
            runs.append(project_id)
            return {
                "project_id": project_id,
                "snapshot": {"data_completeness": {"score": "30", "status_counts": {}}},
                "risks": [
                    {"level": "MEDIUM", "trigger": "资料口径冲突"},
                    {"level": "HIGH", "trigger": "缺少项目单独 CFADS"},
                ],
                "evidence_gaps": [{"required_evidence": "项目单独账套和现金流量表。"}],
                "claims": [], "warning": "初步尽调辅助。",
            }

        def resolver(question: str):
            return question, [{"entity_type": "FACILITY", "entity_id": "SZCF016", "canonical_name": "深圳百旺信智算中心"}]

        service = ConversationService(lambda question: self.fail("不应调用通用 Agent"), due_runner, resolver)
        state, first, _ = service.run("对百旺信做初步尽调")
        self.assertEqual(first["route"], "DUE_DILIGENCE")
        self.assertEqual(runs, ["SZCF016"])
        self.assertTrue(first["due_diligence_result"]["valid_for_followup"])

        _, second, _ = service.run("最大风险是什么？", state.session_id)
        self.assertEqual(second["route"], "DUE_DILIGENCE_FOLLOW_UP")
        self.assertIn("缺少项目单独 CFADS", second["final_answer"])
        self.assertEqual(runs, ["SZCF016"])

        _, third, _ = service.run("还缺哪些资料？", state.session_id)
        self.assertEqual(third["route"], "DUE_DILIGENCE_FOLLOW_UP")
        self.assertIn("项目单独账套", third["final_answer"])
        self.assertEqual(runs, ["SZCF016"])

    def test_two_year_comparison_and_numeric_provenance_reuse_completed_sql_results(self) -> None:
        calls: list[str] = []

        def agent(question: str) -> dict:
            calls.append(question)
            value = "0.6542" if "2025" in question else "0.555"
            return {
                "question": question, "route": "SQL",
                "router": {"route": "SQL", "entity_resolution": [{"entity_type": "FACILITY", "entity_id": "SZCF016", "canonical_name": "深圳百旺信智算中心"}]},
                "sql_result": {"query_result": {"columns": ["rack_utilization_ratio"], "rows": [[value]]}},
                "rag_result": None, "interpretation": None, "sources": [{"title": "SQL 来源"}],
                "synthesis": {"claims": [], "dropped_claims": []}, "final_answer": value,
            }

        service = ConversationService(agent)
        state, _, _ = service.run("百旺信2025年上架率是多少？")
        state, _, _ = service.run("2024呢？", state.session_id)
        _, comparison, _ = service.run("两年差多少？", state.session_id)
        self.assertEqual(comparison["route"], "COMPARISON_REUSE")
        self.assertIn("+9.92 个百分点", comparison["final_answer"])
        self.assertEqual(len(calls), 2)

        _, provenance, _ = service.run("0.6542这个数据哪里来的？", state.session_id)
        self.assertEqual(provenance["route"], "PROVENANCE")
        self.assertIn("2025年", provenance["final_answer"])
        self.assertEqual(len(calls), 2)

    def test_context_reset_prevents_old_entity_and_results_from_being_reused(self) -> None:
        state, _, _ = self.service.run("百旺信2025年上架率多少？")
        cleared = self.service.reset_context(state.session_id)
        self.assertEqual(cleared.active_entities, [])
        self.assertEqual(cleared.turns, [])
        _, result, _ = self.service.run("两年差多少？", state.session_id)
        self.assertEqual(result["route"], "CLARIFICATION")

    def test_completed_context_survives_service_restart_without_private_agent_trace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteConversationStore(Path(directory) / "conversation.sqlite3")
            calls: list[str] = []

            def agent(question: str) -> dict:
                calls.append(question)
                return {
                    "question": question, "route": "SQL",
                    "router": {"route": "SQL", "entity_resolution": [{"entity_type": "FACILITY", "entity_id": "SZCF016", "canonical_name": "深圳百旺信智算中心"}]},
                    "sql_result": {"generated_sql": "SELECT secret_prompt_trace", "query_result": {"columns": ["rack_utilization_ratio"], "rows": [["0.6542"]]}},
                    "rag_result": None, "interpretation": None, "sources": [],
                    "synthesis": {"claims": [], "dropped_claims": []}, "final_answer": "已查询。",
                }

            first_service = ConversationService(agent, store=store)
            state, _, _ = first_service.run("百旺信2025年上架率是多少？")
            recovered_service = ConversationService(agent, store=store)
            _, _, effective = recovered_service.run("2024呢？", state.session_id)
            self.assertIn("深圳百旺信智算中心2024年上架率", effective)
            saved = store.load(state.session_id)
            self.assertIsNotNone(saved)
            self.assertNotIn("generated_sql", str(saved))


if __name__ == "__main__":
    unittest.main()
