from __future__ import annotations

import sys
import unittest
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.config import Settings
from app.energy_compute import EnergyComputeAgent
from app.energy_sql import (
    EnergyTextToSQLPipeline,
    GeneratedSQL,
    QueryResult,
)


class FakeGenerator:
    def __init__(self, sql: str) -> None:
        self.sql = sql
        self.questions: list[str] = []

    def generate(self, question: str) -> GeneratedSQL:
        self.questions.append(question)
        return GeneratedSQL(question, self.sql, "fake-sql-model", {})


class FakeExecutor:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def execute(self, sql: str) -> QueryResult:
        self.queries.append(sql)
        return QueryResult(
            ["official_name", "fact_year", "rack_utilization_ratio"],
            [["深圳百旺信智算中心", "2025", "0.65420000"]],
        )


class FakeSummarizer:
    def summarize(self, question: str, result: QueryResult) -> str:
        return "查询结果显示：深圳百旺信智算中心 2025 年机柜上架率为 0.65420000。"


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


class EnergyComputeAgentTests(unittest.TestCase):
    def make_agent(self, sql: str) -> tuple[EnergyComputeAgent, FakeGenerator, FakeExecutor]:
        generator = FakeGenerator(sql)
        executor = FakeExecutor()
        pipeline = EnergyTextToSQLPipeline(
            test_settings(),
            Path("unused-schema.md"),
            generator=generator,
            executor=executor,
            summarizer=FakeSummarizer(),
        )
        return EnergyComputeAgent(test_settings(), pipeline=pipeline), generator, executor

    def test_facility_alias_is_resolved_before_sql_generation(self) -> None:
        agent, generator, executor = self.make_agent(
            """
            SELECT f.official_name, o.fact_year, o.rack_utilization_ratio
            FROM enterprise_data_center_v2 AS f
            JOIN compute_facility_operation_fact_v1 AS o ON o.facility_v2_id = f.facility_v2_id
            WHERE f.facility_code = 'SZCF016'
              AND o.fact_year = 2025
              AND o.operation_scope_code = 'WHOLE_FACILITY_BUILDING_1_4_SELF_BUILT'
            LIMIT 1
            """
        )
        result = agent.run("百旺信2025年上架率是多少？")
        self.assertEqual(result["route"], "SQL")
        self.assertEqual(result["router"]["entity_resolution"][0]["entity_id"], "SZCF016")
        self.assertIn("SZCF016", generator.questions[0])
        self.assertEqual(len(executor.queries), 1)
        self.assertEqual(result["sql_result"]["query_result"]["rows"][0][-1], "0.65420000")
        self.assertIn("compute_facility_operation_fact_v1", result["sql_result"]["safety"]["tables"])

    def test_policy_and_credit_judgment_are_not_sent_to_sql(self) -> None:
        agent, generator, executor = self.make_agent("SELECT 'NOT_ANSWERABLE_FROM_DB' AS error_code LIMIT 1")
        for question in (
            "深圳训力券对算力服务商是否构成直接收入？",
            "百旺信项目是否适合做绿色贷款？",
            "哪个数据中心服务最好？",
        ):
            with self.subTest(question=question):
                result = agent.run(question)
                self.assertEqual(result["route"], "OUT_OF_SCOPE")
        self.assertEqual(generator.questions, [])
        self.assertEqual(executor.queries, [])

    def test_not_answerable_marker_returns_boundary_without_execution(self) -> None:
        agent, generator, executor = self.make_agent("SELECT 'NOT_ANSWERABLE_FROM_DB' AS error_code LIMIT 1")
        result = agent.run("百旺信老板是谁？")
        self.assertEqual(result["route"], "OUT_OF_SCOPE")
        self.assertEqual(generator.questions, [])
        self.assertEqual(executor.queries, [])

    def test_rejected_sql_is_never_executed(self) -> None:
        agent, _, executor = self.make_agent("SELECT unknown_metric FROM compute_facility_metric_v1 LIMIT 1")
        result = agent.run("深圳哪些算力中心PUE最低？")
        self.assertEqual(result["route"], "SQL")
        self.assertFalse(result["sql_result"]["safety"]["safe"])
        self.assertIsNone(result["sql_result"]["query_result"])
        self.assertEqual(executor.queries, [])


if __name__ == "__main__":
    unittest.main()
