from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[2]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.due_diligence.models import FieldStatus
from app.due_diligence.snapshot import ProjectSnapshotBuilder, RawProjectData


def raw_project(*, pue_date: str | None = None) -> RawProjectData:
    return RawProjectData(
        master={
            "facility_code": "SZCF016", "official_name": "深圳百旺信智算中心", "facility_kind": "AI_COMPUTE",
            "city_name": "深圳市", "operator_name": "深圳易信科技股份有限公司", "lifecycle_status": "OPERATING",
            "last_verified_date": "2026-08-26", "data_quality": "EXCHANGE_PUBLIC",
        },
        metrics=(
            {"metric_code": "CABINET_COUNT", "metric_scope": "PHASE_III", "metric_value": "1760", "metric_text": None, "metric_unit": "CABINET", "as_of_date": None, "source_id": "1", "source_locator": "p.1", "data_quality": "A"},
            {"metric_code": "CABINET_COUNT", "metric_scope": "WHOLE_FACILITY", "metric_value": "4000", "metric_text": None, "metric_unit": "CABINET", "as_of_date": None, "source_id": "2", "source_locator": "p.2", "data_quality": "B"},
            {"metric_code": "PUE", "metric_scope": "PHASE_III", "metric_value": "1.228", "metric_text": None, "metric_unit": "RATIO", "as_of_date": pue_date, "source_id": "3", "source_locator": "p.3", "data_quality": "A"},
            {"metric_code": "ANNUAL_ELECTRICITY_CONSUMPTION", "metric_scope": "PHASE_III", "metric_value": "48473300", "metric_text": None, "metric_unit": "KWH", "as_of_date": None, "source_id": "3", "source_locator": "p.3", "data_quality": "A"},
            {"metric_code": "GREEN_POWER_RATIO", "metric_scope": "OPERATOR_CASE", "metric_value": "1", "metric_text": None, "metric_unit": "RATIO", "as_of_date": None, "source_id": "4", "source_locator": "p.4", "data_quality": "B"},
            {"metric_code": "CAPEX", "metric_scope": "PHASE_III", "metric_value": "32000", "metric_text": None, "metric_unit": "WANYUAN", "as_of_date": None, "source_id": "3", "source_locator": "p.3", "data_quality": "A"},
        ),
        operations=(
            {"operation_scope_code": "WHOLE", "operation_scope_name": "1栋+4栋整体", "fact_year": "2025", "fact_period": "ANNUAL", "rack_utilization_ratio": "0.6542", "average_rack_price_yuan_month": "5346", "hosting_revenue_wanyuan": "100", "electricity_purchase_price_yuan_kwh": "0.65", "source_id": "5", "source_locator": "p.5", "data_quality": "A"},
        ),
    )


class ProjectSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = ProjectSnapshotBuilder()

    def fields(self, raw: RawProjectData, today: date = date(2026, 9, 2)):
        snapshot = self.builder.build("SZCF016", raw, today)
        return {item.field: item for item in snapshot.fields}, snapshot

    def test_profile_has_seven_domains_and_all_required_fields_are_deterministic(self) -> None:
        fields, _ = self.fields(raw_project())
        self.assertEqual({item.domain for item in fields.values()}, {"PROJECT_IDENTITY", "OPERATION", "ENERGY", "FINANCIAL", "FINANCING", "POLICY", "DATA_QUALITY"})
        self.assertTrue(all(item.required for item in fields.values()))

    def test_conflicting_disclosures_are_preserved_not_merged(self) -> None:
        fields, _ = self.fields(raw_project())
        racks = fields["rack_capacity"]
        self.assertEqual(racks.status, FieldStatus.CONFLICTING)
        self.assertEqual([item.value for item in racks.evidence], ["1760", "4000"])
        self.assertTrue(all(item.source_id.startswith("SQL:") for item in racks.evidence))

    def test_missing_cfads_and_documents_are_unknown_as_missing_not_zero(self) -> None:
        fields, _ = self.fields(raw_project())
        self.assertEqual(fields["cfads"].status, FieldStatus.MISSING)
        self.assertEqual(fields["energy_review_document"].status, FieldStatus.MISSING)
        self.assertEqual(fields["cfads"].evidence, ())

    def test_latest_operation_fact_is_available_with_scope_and_source(self) -> None:
        fields, _ = self.fields(raw_project())
        occupancy = fields["occupancy_rate"]
        self.assertEqual(occupancy.status, FieldStatus.AVAILABLE)
        self.assertEqual(occupancy.evidence[0].value, "0.6542")
        self.assertEqual(occupancy.evidence[0].scope, "1栋+4栋整体")

    def test_stale_date_is_distinct_from_missing(self) -> None:
        fields, _ = self.fields(raw_project(pue_date="2020-01-01"))
        self.assertEqual(fields["pue"].status, FieldStatus.STALE)

    def test_completeness_is_weighted_material_status_not_project_score(self) -> None:
        _, snapshot = self.fields(raw_project())
        public = snapshot.public_dict()
        self.assertGreater(public["data_completeness"]["required_weight"], public["data_completeness"]["available_weight"])
        self.assertIn("不表示项目质量", public["data_completeness"]["definition"])


if __name__ == "__main__":
    unittest.main()
