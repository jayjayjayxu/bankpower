from __future__ import annotations

import sys
import unittest
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.energy_sql import DeterministicResultPresenter, QueryResult, repair_display_text, repair_query_result, validate_energy_sql


class EnergySQLSafetyTests(unittest.TestCase):

    def test_repairs_only_known_utf8_as_cp1252_import_artefacts(self) -> None:
        self.assertEqual(repair_display_text("ç™¾æ—ºä¿¡"), "百旺信")
        self.assertEqual(repair_display_text("深圳百旺信智算中心"), "深圳百旺信智算中心")
        self.assertEqual(repair_display_text("5346.0000"), "5346.0000")
        repaired = repair_query_result(QueryResult(["operation_scope_name"], [["ç™¾æ—ºä¿¡"]]))
        self.assertEqual(repaired.rows, [["百旺信"]])

    def test_program_owned_presenter_keeps_raw_value_and_applies_documented_units(self) -> None:
        answer = DeterministicResultPresenter().summarize(
            "测试",
            QueryResult(
                ["rack_utilization_ratio", "average_rack_price_yuan_month"],
                [["0.65420000", "5346"]],
            ),
        )
        self.assertIn("rack_utilization_ratio=0.65420000", answer)
        self.assertIn("程序换算 65.42%", answer)
        self.assertIn("average_rack_price_yuan_month=5346（元/柜/月）", answer)

    def test_allows_documented_facility_join(self) -> None:
        result = validate_energy_sql(
            """
            SELECT f.official_name, m.metric_value, m.metric_unit, m.metric_scope, m.as_of_date,
                   m.disclosure_status
            FROM enterprise_data_center_v2 AS f
            JOIN compute_facility_metric_v1 AS m ON m.facility_v2_id = f.facility_v2_id
            WHERE m.metric_code = 'PUE'
            ORDER BY m.metric_value ASC
            LIMIT 5
            """
        )
        self.assertTrue(result.safe, result.errors)
        self.assertEqual(result.tables, ("compute_facility_metric_v1", "enterprise_data_center_v2"))

    def test_allows_aggregate_and_completed_model_run_join(self) -> None:
        result = validate_energy_sql(
            """
            SELECT s.company_name, s.npv_wanyuan, s.base_min_dscr, s.max_debt_ratio
            FROM analysis_result_snapshot AS s
            JOIN analysis_run AS r ON r.run_id = s.run_id
            WHERE r.status = 'COMPLETED'
              AND s.npv_wanyuan > 0
              AND s.base_min_dscr > 1.2
            ORDER BY s.npv_wanyuan DESC
            LIMIT 20
            """
        )
        self.assertTrue(result.safe, result.errors)

    def test_rejects_writes_files_unlisted_objects_and_unlimited_detail(self) -> None:
        cases = {
            "DELETE FROM enterprise_profile": "根语句不是只读查询",
            "SELECT * FROM enterprise_profile LIMIT 1": "禁止 SELECT *",
            "SELECT ceo_name FROM enterprise_profile LIMIT 1": "不存在字段",
            "SELECT company_name FROM customers LIMIT 1": "禁止或不存在",
            "SELECT company_name FROM other_schema.enterprise_profile LIMIT 1": "禁止访问数据库",
            "SELECT company_name FROM enterprise_profile": "明细查询必须包含 LIMIT",
            "SELECT company_name FROM enterprise_profile LIMIT 101": "LIMIT 不得超过 100",
            "SELECT SLEEP(1) FROM enterprise_profile LIMIT 1": "包含禁止函数",
            "SELECT company_name INTO OUTFILE '/tmp/x' FROM enterprise_profile LIMIT 1": "禁止",
        }
        for sql, expected_error in cases.items():
            with self.subTest(sql=sql):
                result = validate_energy_sql(sql)
                self.assertFalse(result.safe)
                self.assertTrue(any(expected_error in error for error in result.errors), result.errors)

    def test_rejects_more_than_four_objects_and_multiple_statements(self) -> None:
        too_many = """
            SELECT f.official_name
            FROM enterprise_data_center_v2 f
            JOIN compute_facility_metric_v1 m ON m.facility_v2_id=f.facility_v2_id
            JOIN compute_facility_operation_fact_v1 o ON o.facility_v2_id=f.facility_v2_id
            JOIN compute_facility_rack_price_tier_fact_v1 p ON p.facility_v2_id=f.facility_v2_id
            JOIN compute_platform_resource_listing_v1 l ON l.facility_v2_id=f.facility_v2_id
            LIMIT 10
        """
        self.assertFalse(validate_energy_sql(too_many).safe)
        self.assertFalse(
            validate_energy_sql("SELECT company_name FROM enterprise_profile LIMIT 1; SELECT 1").safe
        )


if __name__ == "__main__":
    unittest.main()
