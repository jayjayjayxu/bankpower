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


def settings() -> Settings:
    return Settings(
        core_dir=None, audit_dir=SERVICE_ROOT / "runtime" / "test-audit", sql_login_path="unused",
        spdb_sql_login_path="unused", spdb_database="spdb_power_finance", mysql_binary=Path("/missing/mysql"),
        cors_allowed_origins=("http://localhost:5173",), max_concurrency=1, database_healthcheck=False,
        sql_debug_enabled=False, sql_debug_token="", policy_rag_index_dir=SERVICE_ROOT / "runtime" / "policy_vector_index" / "public_effective",
    )


class StubExecutor:
    def __init__(self, result: QueryResult) -> None:
        self.result = result
        self.sql: list[str] = []

    def execute(self, sql: str) -> QueryResult:
        self.sql.append(sql)
        return self.result


class PublicStatisticsTests(unittest.TestCase):
    def test_national_generation_is_in_scope_sql_and_preserves_industrial_scope(self) -> None:
        executor = StubExecutor(QueryResult(
            ["region_code", "region_name", "region_level", "year", "metric_value", "unit_original", "data_quality", "notes", "source_title", "source_url"],
            [["CN", "全国", "COUNTRY", "2024", "9418100", "电量", "A/B", "", "规模以上工业发电量", "https://example.gov"]],
        ))
        result = PublicStatisticsAgent(settings(), executor).run("全国2024年的发电总量是多少？")
        self.assertEqual(result["route"], "SQL")
        self.assertEqual(result["router"]["domain"], "POWER")
        self.assertEqual(result["router"]["scope"], "IN_SCOPE")
        self.assertEqual(result["router"]["source_plan"], "PUBLIC_STATISTICS_SQL")
        self.assertIn("94,181.00", result["final_answer"])
        self.assertIn("规模以上工业发电量", result["final_answer"])
        self.assertIn("不能替代", result["final_answer"])
        self.assertIn("region_code='CN'", executor.sql[0])

    def test_missing_local_statistic_is_in_scope_data_missing_not_out_of_scope(self) -> None:
        executor = StubExecutor(QueryResult([], []))
        result = PublicStatisticsAgent(settings(), executor).run("全国2020年发电总量是多少？")
        self.assertEqual(result["route"], "IN_SCOPE_DATA_MISSING")
        self.assertEqual(result["router"]["domain"], "POWER")
        self.assertEqual(result["router"]["scope"], "IN_SCOPE")
        self.assertNotEqual(result["route"], "OUT_OF_SCOPE")

    def test_weather_is_not_claimed_as_public_power_statistic(self) -> None:
        self.assertFalse(PublicStatisticsAgent.supports("东京明天会下雨吗？"))


if __name__ == "__main__":
    unittest.main()
