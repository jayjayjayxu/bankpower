from __future__ import annotations

import sys
import unittest
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.config import Settings
from app.corporate_analysis import CorporateAnalysisAgent
from app.energy_sql import QueryResult


def test_settings() -> Settings:
    return Settings(
        core_dir=None,
        audit_dir=Path("runtime/audit"),
        sql_login_path="bank_ai_reader",
        spdb_sql_login_path="bank_ai_local",
        spdb_database="spdb_power_finance",
        mysql_binary=Path("/usr/bin/false"),
        cors_allowed_origins=("http://localhost:5173",),
        max_concurrency=1,
        database_healthcheck=False,
        sql_debug_enabled=False,
        sql_debug_token="",
        policy_rag_index_dir=Path("runtime/policy-index"),
    )


class StubExecutor:
    def __init__(self, financial_rows: list[list[str]] | None = None) -> None:
        self.financial_rows = financial_rows or []
        self.queries: list[str] = []

    def execute(self, sql: str) -> QueryResult:
        self.queries.append(sql)
        if "enterprise_financial" in sql:
            return QueryResult(
                ["company_id", "financial_year", "revenue_wanyuan", "revenue_growth", "net_profit_wanyuan", "total_assets_wanyuan", "total_liabilities_wanyuan", "total_equity_wanyuan", "debt_ratio", "operating_cashflow_wanyuan", "currency", "data_quality", "statistical_scope"],
                self.financial_rows,
            )
        if "v_enterprise_annual_energy_summary" in sql:
            return QueryResult(["company_id", "year", "annual_power_kwh", "annual_electricity_cost_yuan", "avg_cost_yuan_kwh", "annual_max_demand_kw", "data_type"], [["C000020", "2025", "2269000000", "", "", "", "PUBLIC"]])
        if "enterprise_energy_features" in sql:
            return QueryResult(["company_id", "analysis_year", "annual_power_kwh", "avg_price_yuan_kwh", "max_load_kw", "peak_plus_critical_ratio", "data_type", "feature_confidence"], [["C000020", "2026", "420000000", "0.94", "99072", "0.2", "SIMULATED", "SIM_HOURLY"]])
        if "enterprise_bank_observation" in sql:
            return QueryResult(["company_id", "as_of_date", "project_finance_potential", "green_finance_potential", "bankability_score", "potential_bank_product", "scenario_basis"], [["C000020", "", "MEDIUM", "HIGH", "", "储能融资", "营销初筛"]])
        if "enterprise_finance_opportunity_v1" in sql:
            return QueryResult(["company_id", "analysis_year", "project_capex_wanyuan", "project_npv_wanyuan", "project_irr", "base_min_dscr", "max_feasible_debt_ratio", "opportunity_level", "readiness_level", "risk_level", "opportunity_reason", "key_risk_notes", "next_action", "data_type"], [["C000020", "2026", "10209", "6177", "0.2", "1.43", "0.83", "HIGH", "PARTIAL", "MEDIUM", "", "", "", "SIMULATED"]])
        if "enterprise_policy_assessment_v1" in sql:
            return QueryResult(["company_id", "assessment_scope", "applicability_status", "evidence_status", "missing_evidence", "model_gate_status", "resulting_action", "assessment_confidence"], [["C000020", "STORAGE_PROJECT", "POTENTIALLY_ELIGIBLE", "PARTIAL", "", "REVIEW_REQUIRED", "补充资料", "HIGH"]])
        if "enterprise_profile" in sql:
            return QueryResult(
                ["company_id", "company_name", "ownership_type", "industry_name", "power_chain_role", "energy_customer_type", "business_verification_status", "notes"],
                [["C000020", "深圳市地铁集团有限公司", "地方国企", "城市轨道交通运营", "POWER_USER", "重点用能企业/项目业主", "A-官方名单基础核验", ""]],
            )
        return QueryResult(
            ["company_id", "company_name", "analysis_date", "data_type", "storage_power_mw", "storage_capacity_mwh", "capex_wanyuan", "npv_wanyuan", "irr", "base_min_dscr", "max_debt_ratio", "financing_status", "overall_risk", "recommended_product", "recommendation_text", "risk_summary"],
            [["C000020", "深圳市地铁集团有限公司", "2026-08-24", "MIXED", "160.5677", "642.2708", "100000", "36112.9828", "0.2206", "1.512576", "0.88", "PASS", "MEDIUM", "项目融资", "", "需核验实际负荷、电价及接入容量。"]],
        )


class CorporateAnalysisTests(unittest.TestCase):
    def test_data_coverage_answers_what_is_stored(self) -> None:
        executor = StubExecutor()
        result = CorporateAnalysisAgent(test_settings(), executor=executor).run("深圳地铁目前有哪些数据？")
        self.assertEqual(result["route"], "CORPORATE_DATA_COVERAGE")
        inventory = result["corporate_result"]["data_inventory"]
        self.assertIn("年度用电", [item["category"] for item in inventory if item["status"] == "AVAILABLE"])
        self.assertIn("项目融资机会", [item["category"] for item in inventory if item["status"] == "AVAILABLE"])
        self.assertIn("客运运营数据", [item["category"] for item in inventory if item["status"] == "NOT_STORED"])
        self.assertNotIn("当前数据库缺少该企业的营业收入", result["final_answer"])
        self.assertEqual(len(executor.queries), 8)

    def test_missing_financial_and_passenger_data_is_in_scope_gap(self) -> None:
        executor = StubExecutor()
        result = CorporateAnalysisAgent(test_settings(), executor=executor).run("深圳地铁集团2024年营收、负债、客运量是多少？")
        self.assertEqual(result["route"], "IN_SCOPE_DATA_MISSING")
        self.assertEqual(result["router"]["domain"], "CORPORATE")
        self.assertIn("营业收入、总负债、客运量", result["final_answer"])
        self.assertNotIn("不在当前能力范围内", result["final_answer"])
        self.assertEqual(len(executor.queries), 1)

    def test_registered_financial_facts_are_program_formatted(self) -> None:
        executor = StubExecutor([["C000020", "2024", "123456.78", "0.01", "2345.6", "999999", "555555", "444444", "0.5556", "3456.7", "CNY", "A", "合并口径"]])
        result = CorporateAnalysisAgent(test_settings(), executor=executor).run("深圳地铁集团2024年营收、负债是多少？")
        self.assertEqual(result["route"], "CORPORATE_FACT")
        self.assertIn("123,456.78 万元", result["final_answer"])
        self.assertIn("555,555 万元", result["final_answer"])
        self.assertEqual(result["sql_result"]["safety"]["tables"], ("enterprise_financial",))

    def test_corporate_analysis_marks_scenario_and_credit_boundary(self) -> None:
        executor = StubExecutor()
        result = CorporateAnalysisAgent(test_settings(), executor=executor).run("深圳地铁目前有哪些投资优势和风险？")
        self.assertEqual(result["route"], "CORPORATE_ANALYSIS")
        self.assertEqual(result["corporate_result"]["status"], "FURTHER_RESEARCH_REQUIRED")
        self.assertTrue(result["corporate_result"]["scenario_data_available"])
        self.assertIn("不能作为集团真实财务或授信结论", result["final_answer"])
        self.assertEqual(result["interpretation"]["facts"][0]["label"], "企业名称")
        self.assertEqual(result["interpretation"]["facts"][1]["label"], "储能项目 NPV")
        self.assertEqual(len(executor.queries), 6)


if __name__ == "__main__":
    unittest.main()
