from __future__ import annotations

import sys
import unittest
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.config import Settings
from app.energy_sql import QueryResult
from app.public_statistics import PublicStatisticsAgent


COLUMNS = [
    "region_code", "region_name", "stat_year", "metric_basis", "scope_code",
    "statistical_scope", "energy_type_code", "energy_type_name", "metric_value",
    "metric_unit", "value_operator", "disclosure_status", "source_locator",
    "data_quality", "source_title", "source_url", "source_org",
]


def settings() -> Settings:
    return Settings(
        core_dir=None, audit_dir=SERVICE_ROOT / "runtime" / "test-audit", sql_login_path="unused",
        spdb_sql_login_path="unused", spdb_database="spdb_power_finance", mysql_binary=Path("/missing/mysql"),
        cors_allowed_origins=("http://localhost:5173",), max_concurrency=1, database_healthcheck=False,
        sql_debug_enabled=False, sql_debug_token="", policy_rag_index_dir=SERVICE_ROOT / "runtime" / "policy_vector_index" / "public_effective",
    )


def row(energy_type: str, value: str, *, scope: str = "CN_ALL_GROSS_GENERATION") -> list[str]:
    label = {"TOTAL": "全部电源", "THERMAL": "火电", "WIND": "风电"}[energy_type]
    return ["CN", "全国", "2024", "GROSS_GENERATION", scope, "全国全口径年度发电量", energy_type, label, value, "GWh", "EQ", "DISCLOSED", "p.1", "A", "国家能源局公开统计", "https://example.gov", "国家能源局"]


class StubExecutor:
    def __init__(self, records: dict[str, list[str]]) -> None:
        self.records = records
        self.sql: list[str] = []

    def execute(self, sql: str) -> QueryResult:
        self.sql.append(sql)
        energy_type = next((code for code in self.records if f"energy_type_code='{code}'" in sql), None)
        return QueryResult(COLUMNS, [self.records[energy_type]]) if energy_type else QueryResult([], [])


class PublicStatisticsTests(unittest.TestCase):
    def test_direct_generation_uses_registered_v2_metric_and_scope(self) -> None:
        executor = StubExecutor({"TOTAL": row("TOTAL", "10086880")})
        result = PublicStatisticsAgent(settings(), executor).run("全国2024年的发电总量是多少？")
        self.assertEqual(result["route"], "SQL")
        self.assertEqual(result["router"]["metric_code"], "total_generation")
        self.assertEqual(result["router"]["statistical_scope"], "全国全口径年度发电量")
        self.assertIn("100,868.80", result["final_answer"])
        self.assertIn("power_source_structure_v2", result["tool_calls"][0]["table"])

    def test_thermal_share_is_program_calculated_from_compatible_inputs(self) -> None:
        executor = StubExecutor({"THERMAL": row("THERMAL", "6374260"), "TOTAL": row("TOTAL", "10086880")})
        result = PublicStatisticsAgent(settings(), executor).run("全国2024年火力发电占比是多少？")
        self.assertEqual(result["route"], "SQL_CALC")
        self.assertEqual(result["router"]["calculation_status"], "CALCULABLE")
        self.assertEqual(result["calculation_result"]["display_value"], "63.19%")
        self.assertEqual(result["calculation_result"]["formula"], "火力发电量 ÷ 发电总量 × 100%")
        self.assertEqual(result["synthesis"]["claims"][0]["claim_type"], "CALC_RESULT")
        self.assertEqual(len(executor.sql), 2)

    def test_incompatible_scope_is_never_calculated(self) -> None:
        executor = StubExecutor({"THERMAL": row("THERMAL", "6374260", scope="CN_INDUSTRIAL"), "TOTAL": row("TOTAL", "10086880")})
        result = PublicStatisticsAgent(settings(), executor).run("全国2024年火电占比是多少？")
        self.assertEqual(result["route"], "IN_SCOPE_DATA_MISSING")
        self.assertEqual(result["router"]["calculation_status"], "INCOMPATIBLE_SCOPE")
        self.assertIn("不能直接计算", result["final_answer"])
        self.assertFalse(result["tool_calls"][1]["executed"])

    def test_missing_numerator_is_in_scope_data_missing_not_out_of_scope(self) -> None:
        executor = StubExecutor({"TOTAL": row("TOTAL", "10086880")})
        result = PublicStatisticsAgent(settings(), executor).run("全国2024年火力发电占比是多少？")
        self.assertEqual(result["route"], "IN_SCOPE_DATA_MISSING")
        self.assertEqual(result["router"]["calculation_status"], "MISSING_NUMERATOR")
        self.assertNotEqual(result["route"], "OUT_OF_SCOPE")

    def test_weather_is_not_claimed_as_public_power_statistic(self) -> None:
        self.assertFalse(PublicStatisticsAgent.supports("东京明天会下雨吗？"))


if __name__ == "__main__":
    unittest.main()
