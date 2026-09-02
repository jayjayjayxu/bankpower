"""V4.0-B deterministic, evidence-bound policy eligibility checks."""

from .engine import EligibilityEngine
from .models import (
    EligibilityResult,
    EvaluationStatus,
    OverallStatus,
    PolicyRule,
    ProjectFact,
    RuleType,
)
from .rules import EligibilityRuleError, load_rule_catalog, validate_evidence_references

__all__ = [
    "EligibilityEngine",
    "EligibilityResult",
    "EligibilityRuleError",
    "EvaluationStatus",
    "OverallStatus",
    "PolicyRule",
    "ProjectFact",
    "RuleType",
    "load_rule_catalog",
    "validate_evidence_references",
]
