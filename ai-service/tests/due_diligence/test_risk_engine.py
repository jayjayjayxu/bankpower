from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[2]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.due_diligence import EvidenceGapAnalyzer, RiskEngine
from app.due_diligence.snapshot import ProjectSnapshotBuilder
from .test_snapshot import raw_project


class RiskAndGapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot = ProjectSnapshotBuilder().build("SZCF016", raw_project(), date(2026, 9, 2))

    def test_risks_are_triggered_by_snapshot_statuses_not_llm_judgment(self) -> None:
        risks = RiskEngine().evaluate(self.snapshot)
        codes = {item.code for item in risks}
        self.assertIn("DATA_CONFLICTING_DISCLOSURES", codes)
        self.assertIn("DATA_REQUIRED_FIELD_MISSING", codes)
        self.assertTrue(all(item.source_id for item in risks))

    def test_scenario_dscr_thresholds_are_explicit_and_traceable(self) -> None:
        risks = RiskEngine().evaluate(self.snapshot, [{"scenario": "SEVERE", "results": {"min_dscr": "0.95"}}])
        flag = next(item for item in risks if item.code == "FIN_DSCR_BELOW_1")
        self.assertEqual(flag.level.value, "HIGH")
        self.assertEqual(flag.threshold, "1.00")

    def test_policy_unknown_generates_rule_based_gap(self) -> None:
        eligibility = {"overall_status": "INSUFFICIENT_EVIDENCE", "evaluations": [{"rule_id": "DC_RENEWABLE_PLAN_001", "status": "UNKNOWN", "reason": "缺少材料", "condition": {"target_field": "renewable_energy_plan"}}]}
        risks = RiskEngine().evaluate(self.snapshot, eligibility=eligibility)
        gaps = EvidenceGapAnalyzer().analyze(self.snapshot, eligibility, risks)
        by_code = {item.code: item for item in gaps}
        self.assertIn("RULE:DC_RENEWABLE_PLAN_001", by_code)
        self.assertIn("绿电合同", by_code["RULE:DC_RENEWABLE_PLAN_001"].required_evidence)

    def test_cfads_gap_is_high_priority_and_not_created_from_free_text(self) -> None:
        gaps = EvidenceGapAnalyzer().analyze(self.snapshot)
        cfads = next(item for item in gaps if item.code == "SNAPSHOT:cfads")
        self.assertEqual(cfads.priority.value, "HIGH")
        self.assertIn("现金流量表", cfads.required_evidence)


if __name__ == "__main__":
    unittest.main()
