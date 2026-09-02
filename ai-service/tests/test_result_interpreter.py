from __future__ import annotations

import sys
import unittest
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.answer_validator import validate_or_fallback, validate_sql_answer
from app.energy_sql import QueryResult
from app.result_interpreter import interpret_sql_result
from app.sql_answer_renderer import render_sql_answer


class ResultInterpreterTests(unittest.TestCase):
    def test_unmapped_entity_mapping_has_program_owned_boundary_and_no_null_leak(self) -> None:
        result = QueryResult(
            [
                "external_product_id", "product_name", "provider_name", "platform_region_label",
                "mapping_status", "candidate_name", "candidate_facility_v2_id", "facility_code",
                "official_name", "source_locator", "evidence_summary", "boundary_note",
            ],
            [[
                "B200-C4-1", "B200 * 8 - C4 - 1", "公有云", "北京", "UNMAPPED",
                "北京超级云计算中心 N61B2B分区", "NULL", "NULL", "NULL", "资源页N61B2B分区",
                "公开资源页显示 B200×8，形态相似。", "未找到 B200-C4-1 与 N61B2B 的直接对应证据。",
            ]],
        )
        interpreted = interpret_sql_result("B200-C4-1对应哪个数据中心？", result)
        answer = render_sql_answer("B200-C4-1对应哪个数据中心？", interpreted)

        self.assertEqual(interpreted.response_mode, "ENTITY_MAPPING")
        self.assertEqual(interpreted.answer_status, "UNCONFIRMED_MAPPING")
        self.assertEqual(interpreted.primary_conclusion, "目前无法确认 B200-C4-1 对应具体数据中心。")
        self.assertEqual(interpreted.candidates[0]["role"], "REFERENCE_ONLY")
        self.assertIn("同型资源参照不构成该商品的正式设施映射。", interpreted.boundaries)
        self.assertNotIn("NULL", answer)
        self.assertNotIn("candidate_facility_v2_id=", answer)
        self.assertTrue(validate_sql_answer(answer, interpreted).valid)
        self.assertNotIn("raw_rows", interpreted.public_dict())
        self.assertNotIn("raw_value", interpreted.public_dict()["facts"][0])

    def test_validator_rejects_mapping_status_upgrade_and_uses_fallback(self) -> None:
        result = QueryResult(
            ["external_product_id", "mapping_status", "candidate_name", "boundary_note"],
            [["B200-C4-1", "UNMAPPED", "N61B2B", "没有直接映射证据。"]],
        )
        interpreted = interpret_sql_result("B200-C4-1对应哪个数据中心？", result)
        invalid = "B200-C4-1 已确认映射并部署于 N61B2B。"
        answer, validation, fallback_used = validate_or_fallback(invalid, interpreted)

        self.assertFalse(validation.valid)
        self.assertTrue(fallback_used)
        self.assertIn("目前无法确认", answer)
        self.assertNotIn("部署于", answer)

    def test_fact_lookup_formats_ratio_price_and_pue_without_raw_dump(self) -> None:
        result = QueryResult(
            ["official_name", "metric_name", "metric_scope", "metric_value", "metric_unit", "fact_year"],
            [
                ["深圳百旺信智算中心", "PUE", "全设施", "1.21000000", "RATIO", "2025"],
                ["深圳百旺信智算中心", "上架率", "全设施", "0.65420000", "RATIO", "2025"],
                ["深圳百旺信智算中心", "平均机柜价格", "全设施", "5346.0000", "CNY/RACK/MONTH", "2025"],
            ],
        )
        interpreted = interpret_sql_result("百旺信2025年PUE、上架率和平均机柜价格是多少？", result)
        answer = render_sql_answer("", interpreted)

        self.assertEqual(interpreted.response_mode, "FACT_LOOKUP")
        self.assertIn("PUE为1.21", interpreted.primary_conclusion)
        self.assertIn("上架率为65.42%", interpreted.primary_conclusion)
        self.assertIn("平均机柜价格为5,346 元/柜/月", interpreted.primary_conclusion)
        self.assertNotIn("metric_value=", answer)
        self.assertTrue(validate_sql_answer(answer, interpreted).valid)

    def test_entity_resolution_supplies_human_subject_when_sql_does_not_select_name(self) -> None:
        interpreted = interpret_sql_result(
            "百旺信2025年上架率是多少？",
            QueryResult(["fact_year", "rack_utilization_ratio"], [["2025", "0.6542"]]),
            [{"canonical_name": "深圳百旺信智算中心"}],
        )
        self.assertTrue(interpreted.primary_conclusion.startswith("深圳百旺信智算中心2025年"))

    def test_seven_response_mode_heuristics(self) -> None:
        result = QueryResult(["official_name", "metric_value"], [["A中心", "1.21"]])
        expected = {
            "PUE最低的3个中心": "RANKING",
            "哪些中心PUE低于1.3": "LIST",
            "A中心和B中心PUE比较": "COMPARISON",
            "深圳设施平均PUE多少": "AGGREGATION",
        }
        for question, mode in expected.items():
            with self.subTest(question=question):
                self.assertEqual(interpret_sql_result(question, result).response_mode, mode)
        time_result = QueryResult(["fact_year", "rack_utilization_ratio"], [["2023", "0.3762"], ["2025", "0.6542"]])
        self.assertEqual(interpret_sql_result("百旺信2023-2025上架率变化", time_result).response_mode, "TIME_SERIES")
        self.assertEqual(interpret_sql_result("当前数据是什么", QueryResult(["official_name"], [["A中心"]])).response_mode, "FACT_LOOKUP")
        self.assertEqual(interpret_sql_result("B200-C4-1对应哪个数据中心", QueryResult(["mapping_status"], [["NO_DATA"]])).response_mode, "ENTITY_MAPPING")

    def test_empty_result_is_no_data_not_zero(self) -> None:
        interpreted = interpret_sql_result("百旺信上架率是多少？", QueryResult(["rack_utilization_ratio"], []))
        self.assertEqual(interpreted.answer_status, "NO_DATA")
        self.assertIn("没有查询到", interpreted.primary_conclusion)
        self.assertNotIn("0", interpreted.primary_conclusion)


if __name__ == "__main__":
    unittest.main()
