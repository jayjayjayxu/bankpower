from __future__ import annotations

import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[2]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.eligibility import (
    EligibilityEngine,
    EligibilityRuleError,
    EvaluationStatus,
    OverallStatus,
    ProjectFact,
    load_rule_catalog,
    validate_evidence_references,
)
from app.eligibility.rules import rule_from_dict
from app.finance.models import SourceType


def fact(value: object, unit: str, source_id: str = "SQL:TEST") -> ProjectFact:
    return ProjectFact(value, unit, SourceType.FACT, source_id)


class EligibilityEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.version, cls.rules = load_rule_catalog(SERVICE_ROOT / "resources" / "eligibility_rules_v04.json")

    def setUp(self) -> None:
        self.engine = EligibilityEngine()

    def evaluate(self, facts: dict[str, ProjectFact]):
        return self.engine.evaluate(
            project_id="SZCF016-PHASE-III",
            rule_catalog_version=self.version,
            rules=self.rules,
            facts=facts,
            as_of_date=date(2026, 1, 1),
        )

    @staticmethod
    def complete_facts() -> dict[str, ProjectFact]:
        return {
            "project_stage": fact("NEW", "ENUM"),
            "facility_scale": fact("LARGE", "ENUM"),
            "is_national_hub": fact(False, "BOOLEAN"),
            "pue": fact(Decimal("1.228"), "RATIO", "SQL:compute_facility_metric_v1:SZCF016:PUE"),
            "energy_review_completed": fact(True, "BOOLEAN", "DOC:ENERGY_REVIEW"),
            "server_energy_efficiency_level": fact("STANDARD_COMPLIANT", "ENUM", "DOC:SERVER_EFFICIENCY"),
            "renewable_energy_plan": fact(True, "DOCUMENT", "DOC:RENEWABLE_PLAN"),
        }

    def test_catalog_is_versioned_and_every_rule_has_policy_chunk_evidence(self) -> None:
        self.assertEqual(self.version, "V4.0-B.1")
        self.assertEqual(len(self.rules), 5)
        self.assertTrue(all(rule.evidence.policy_id == "POL-029" for rule in self.rules))
        self.assertTrue(all(rule.evidence.evidence_chunk_id.startswith("POL-029-C") for rule in self.rules))
        validate_evidence_references(
            self.rules,
            SERVICE_ROOT / "runtime" / "policy_corpus" / "public_effective" / "chunks.jsonl",
        )

    def test_complete_evidence_matches_known_applicable_rules(self) -> None:
        result = self.evaluate(self.complete_facts())
        by_id = {item.rule.rule_id: item for item in result.evaluations}
        self.assertEqual(result.overall_status, OverallStatus.MATCHED_ON_KNOWN_RULES)
        self.assertEqual(by_id["DC_PUE_LARGE_001"].status, EvaluationStatus.MET)
        self.assertEqual(by_id["DC_ENERGY_REVIEW_001"].status, EvaluationStatus.MET)
        self.assertEqual(by_id["DC_SERVER_EFFICIENCY_001"].status, EvaluationStatus.MET)
        self.assertEqual(by_id["DC_RENEWABLE_PLAN_001"].status, EvaluationStatus.MET)
        self.assertEqual(by_id["DC_HUB_GREEN_POWER_001"].status, EvaluationStatus.NOT_APPLICABLE)

    def test_baiwangxin_disclosed_pue_alone_is_insufficient_for_policy_qualification(self) -> None:
        result = self.evaluate({
            "pue": fact(Decimal("1.228"), "RATIO", "SQL:compute_facility_metric_v1:SZCF016:PUE:PHASE_III_EXCHANGE_DISCLOSURE"),
        })
        self.assertEqual(result.overall_status, OverallStatus.INSUFFICIENT_EVIDENCE)
        self.assertTrue(all(item.status == EvaluationStatus.UNKNOWN for item in result.evaluations))

    def test_missing_data_is_unknown_not_unmet_and_drives_insufficient_evidence(self) -> None:
        facts = self.complete_facts()
        del facts["renewable_energy_plan"]
        result = self.evaluate(facts)
        evaluation = next(item for item in result.evaluations if item.rule.rule_id == "DC_RENEWABLE_PLAN_001")
        self.assertEqual(evaluation.status, EvaluationStatus.UNKNOWN)
        self.assertEqual(result.overall_status, OverallStatus.INSUFFICIENT_EVIDENCE)

    def test_explicit_mandatory_rule_failure_is_not_eligible_label(self) -> None:
        facts = self.complete_facts()
        facts["pue"] = fact(Decimal("1.30"), "RATIO")
        result = self.evaluate(facts)
        self.assertEqual(result.overall_status, OverallStatus.EXPLICIT_RULE_NOT_MET)
        self.assertEqual(result.public_dict()["overall_status"], "EXPLICIT_RULE_NOT_MET")

    def test_unknown_overrides_another_explicit_failure_for_evidence_boundary(self) -> None:
        facts = self.complete_facts()
        facts["pue"] = fact(Decimal("1.30"), "RATIO")
        del facts["renewable_energy_plan"]
        self.assertEqual(self.evaluate(facts).overall_status, OverallStatus.INSUFFICIENT_EVIDENCE)

    def test_numeric_unit_mismatch_is_unknown(self) -> None:
        facts = self.complete_facts()
        facts["pue"] = fact("1.228", "PERCENT")
        evaluation = next(item for item in self.evaluate(facts).evaluations if item.rule.rule_id == "DC_PUE_LARGE_001")
        self.assertEqual(evaluation.status, EvaluationStatus.UNKNOWN)

    def test_non_applicable_scope_is_not_unmet(self) -> None:
        facts = self.complete_facts()
        facts["project_stage"] = fact("EXISTING", "ENUM")
        result = self.evaluate(facts)
        self.assertTrue(all(item.status == EvaluationStatus.NOT_APPLICABLE for item in result.evaluations))
        self.assertEqual(result.overall_status, OverallStatus.INSUFFICIENT_EVIDENCE)

    def test_hub_green_power_rule_is_evaluated_when_scope_is_proven(self) -> None:
        facts = self.complete_facts()
        facts["is_national_hub"] = fact(True, "BOOLEAN")
        facts["green_power_ratio"] = fact(Decimal("0.75"), "RATIO")
        result = self.evaluate(facts)
        evaluation = next(item for item in result.evaluations if item.rule.rule_id == "DC_HUB_GREEN_POWER_001")
        self.assertEqual(evaluation.status, EvaluationStatus.UNMET)
        self.assertEqual(result.overall_status, OverallStatus.PARTIAL_MATCH)

    def test_boolean_enum_and_document_rules_use_typed_operators(self) -> None:
        facts = self.complete_facts()
        facts["energy_review_completed"] = fact(False, "BOOLEAN")
        facts["server_energy_efficiency_level"] = fact("UNVERIFIED", "ENUM")
        facts["renewable_energy_plan"] = fact(False, "DOCUMENT")
        result = self.evaluate(facts)
        self.assertEqual(
            [item.status for item in result.evaluations[:4]],
            [EvaluationStatus.MET, EvaluationStatus.UNMET, EvaluationStatus.UNMET, EvaluationStatus.UNMET],
        )
        self.assertEqual(result.overall_status, OverallStatus.EXPLICIT_RULE_NOT_MET)

    def test_assumption_source_is_preserved_in_output_not_promoted_to_fact(self) -> None:
        facts = self.complete_facts()
        facts["pue"] = ProjectFact(Decimal("1.228"), "RATIO", SourceType.ASSUMPTION, "USER:PUE")
        result = self.evaluate(facts).public_dict()
        pue = next(item for item in result["evaluations"] if item["rule_id"] == "DC_PUE_LARGE_001")
        self.assertEqual(pue["project_fact"]["source_type"], "ASSUMPTION")
        self.assertEqual(pue["condition"]["operator"], "<=")
        self.assertEqual(pue["condition"]["threshold_value"], "1.25")

    def test_bad_rule_catalog_is_rejected_before_evaluation(self) -> None:
        with self.assertRaises(EligibilityRuleError):
            rule_from_dict({
                "rule_id": "BAD", "policy_id": "POL-X", "evidence_chunk_id": "C-1", "source_excerpt": "x",
                "rule_type": "NUMERIC_THRESHOLD", "target_field": "pue", "operator": "IN",
                "threshold_value": "1.2", "unit": "RATIO", "region": "全国", "entity_type": "DATA_CENTER",
                "description": "bad",
            })


if __name__ == "__main__":
    unittest.main()
