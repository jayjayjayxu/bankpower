from __future__ import annotations

import sys
import unittest
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.config import Settings
from app.energy_compute import EnergyComputeAgent, QueryResult


class FakeSpdbRunner:
    """Small deterministic fixture for the controlled query catalogue."""

    def execute(self, sql: str) -> QueryResult:
        if "FROM enterprise_data_center_v2" in sql:
            return QueryResult(
                ["facility_code", "official_name", "facility_alias"],
                [["SZCF016", "深圳百旺信智算中心", "百旺信云数据中心三期"]],
            )
        if "FROM compute_facility_operation_fact_v1" in sql:
            return QueryResult(
                [
                    "official_name", "operation_scope_name", "fact_year", "fact_period",
                    "rack_capacity_count", "average_occupied_rack_count", "rack_utilization_ratio",
                    "average_rack_price_yuan_month", "source_title", "source_url", "source_locator",
                ],
                [[
                    "深圳百旺信智算中心", "1栋和4栋自建服务器托管整体", "2025", "全年", "3780", "2473",
                    "0.6542", "5346", "企业经营披露", "", "PDF第85-86页",
                ]],
            )
        if "FROM v_compute_facility_project_cashflow_summary_v1" in sql:
            return QueryResult(
                [
                    "scenario_code", "scenario_name", "reference_historical_capex_yuan", "reference_pue",
                    "year1_rack_occupancy_ratio", "steady_state_rack_occupancy_ratio",
                    "year1_pre_tax_cashflow_proxy_yuan", "hypothetical_greenfield_npv_proxy_yuan",
                    "result_status", "assumption_note",
                ],
                [["BASE", "基准情景", "320000000", "1.228", "0.6542", "0.7", "1", "1", "REFERENCE", "研究情景"]],
            )
        if "FROM v_compute_facility_project_due_diligence_v1" in sql:
            return QueryResult(
                [
                    "check_code", "check_name", "evidence_status", "risk_level", "evidence_summary",
                    "required_evidence", "due_diligence_action",
                ],
                [["PHASE3_CASHFLOW", "三期现金流", "PENDING", "BLOCKING", "缺失", "独立收入、成本和债务本息", "补充材料"]],
            )
        if "FROM policy_rule_v1" in sql and "COMPUTE_VOUCHER" in sql:
            return QueryResult(
                [
                    "file_name", "document_title", "policy_level", "official_url", "rule_code", "rule_title",
                    "applicability_summary", "requirement_summary", "required_evidence", "source_locator", "model_impact_type",
                ],
                [[
                    "深圳市训力券申请指南.pdf", "2026年度深圳市训力券申请指南", "LOCAL_POLICY", "",
                    "SZ_TRAINING_VOUCHER_2026_DEMAND", "需求方申请", "需求方", "购买非关联智能算力后可申请抵扣",
                    "合同与结算材料", "第3页", "NO_AUTOMATIC_EFFECT",
                ]],
            )
        if "FROM policy_rule_v1" in sql:
            return QueryResult(
                [
                    "file_name", "document_title", "policy_level", "official_url", "rule_code", "rule_title",
                    "applicability_summary", "requirement_summary", "required_evidence", "source_locator", "model_impact_type",
                ],
                [[
                    "绿色金融支持项目目录（2025年版）.pdf", "绿色金融支持项目目录（2025年版）", "NATIONAL", "",
                    "NAT_GREEN_FINANCE_2025_GREEN_DC", "绿色数据中心", "建设改造", "满足GB 40879二级能效及尽调要求",
                    "PUE、资金用途证明", "6.6.2", "GATE",
                ]],
            )
        raise AssertionError(f"Unexpected controlled query: {sql}")


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
    )


class EnergyComputeAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = EnergyComputeAgent(test_settings(), runner=FakeSpdbRunner())

    def test_operation_question_is_controlled_sql_with_disclosed_values(self) -> None:
        result = self.agent.run("深圳百旺信智算中心2025年的上架率和平均机柜价格是多少？")
        self.assertEqual(result["route"], "SQL")
        self.assertIn("65.42%", result["final_answer"])
        self.assertIn("5,346.00 元/柜/月", result["final_answer"])
        self.assertIn("独立经营指标", result["final_answer"])
        self.assertEqual(result["sources"][0]["source_locator"], "PDF第85-86页")

    def test_training_voucher_question_is_policy_retrieval_not_revenue_fabrication(self) -> None:
        result = self.agent.run("深圳训力券对算力服务商是否构成直接收入？")
        self.assertEqual(result["route"], "RAG")
        self.assertIn("不能仅凭深圳训力券政策", result["final_answer"])
        self.assertIn("不应自动计入服务商收入", result["final_answer"])
        self.assertTrue(result["rag_result"]["references"])

    def test_green_loan_question_requires_cfad_before_any_ratio(self) -> None:
        result = self.agent.run("百旺信这种项目是否适合做绿色贷款，预计能做到多少贷款比例？")
        self.assertEqual(result["route"], "BOTH")
        self.assertEqual(result["finance_result"]["status"], "INSUFFICIENT_INPUT")
        self.assertIn("CFADS", result["final_answer"])
        self.assertIn("不能给出可贷比例", result["final_answer"])
        self.assertTrue(result["finance_result"]["missing_evidence"])


if __name__ == "__main__":
    unittest.main()
