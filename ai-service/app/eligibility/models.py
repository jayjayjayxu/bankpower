"""Schemas for rule definitions, project facts and eligibility results."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any

from app.finance.models import SourceType


class RuleType(StrEnum):
    NUMERIC_THRESHOLD = "NUMERIC_THRESHOLD"
    BOOLEAN = "BOOLEAN"
    ENUM = "ENUM"
    DOCUMENT_REQUIRED = "DOCUMENT_REQUIRED"


class RuleOperator(StrEnum):
    LTE = "<="
    GTE = ">="
    EQUALS = "EQUALS"
    IN = "IN"


class EvaluationStatus(StrEnum):
    MET = "MET"
    UNMET = "UNMET"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class OverallStatus(StrEnum):
    MATCHED_ON_KNOWN_RULES = "MATCHED_ON_KNOWN_RULES"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    EXPLICIT_RULE_NOT_MET = "EXPLICIT_RULE_NOT_MET"


@dataclass(frozen=True)
class ProjectFact:
    """A project value that can be displayed with its original evidence chain."""

    value: Any
    unit: str
    source_type: SourceType
    source_id: str

    def public_dict(self) -> dict[str, Any]:
        value = str(self.value) if isinstance(self.value, Decimal) else self.value
        return {
            "value": value,
            "unit": self.unit,
            "source_type": self.source_type.value,
            "source_id": self.source_id,
        }


@dataclass(frozen=True)
class PolicyEvidence:
    policy_id: str
    evidence_chunk_id: str
    source_excerpt: str

    def public_dict(self) -> dict[str, str]:
        return {
            "policy_id": self.policy_id,
            "evidence_chunk_id": self.evidence_chunk_id,
            "source_excerpt": self.source_excerpt,
        }


@dataclass(frozen=True)
class PolicyRule:
    rule_id: str
    evidence: PolicyEvidence
    rule_type: RuleType
    target_field: str
    operator: RuleOperator
    threshold_value: Any | None
    unit: str
    region: str
    entity_type: str
    mandatory: bool
    effective_date: date | None
    expiry_date: date | None
    description: str
    applicability: dict[str, tuple[Any, ...]]

    def public_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "policy_evidence": self.evidence.public_dict(),
            "rule_type": self.rule_type.value,
            "target_field": self.target_field,
            "operator": self.operator.value,
            "threshold_value": self.threshold_value,
            "unit": self.unit,
            "region": self.region,
            "entity_type": self.entity_type,
            "mandatory": self.mandatory,
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "description": self.description,
            "applicability": {key: list(value) for key, value in self.applicability.items()},
        }


@dataclass(frozen=True)
class RuleEvaluation:
    rule: PolicyRule
    status: EvaluationStatus
    reason: str
    project_fact: ProjectFact | None

    def public_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule.rule_id,
            "status": self.status.value,
            "reason": self.reason,
            "mandatory": self.rule.mandatory,
            "description": self.rule.description,
            "condition": {
                "rule_type": self.rule.rule_type.value,
                "target_field": self.rule.target_field,
                "operator": self.rule.operator.value,
                "threshold_value": self.rule.threshold_value,
                "unit": self.rule.unit,
                "applicability": {key: list(value) for key, value in self.rule.applicability.items()},
            },
            "policy_evidence": self.rule.evidence.public_dict(),
            "project_fact": self.project_fact.public_dict() if self.project_fact else None,
        }


@dataclass(frozen=True)
class EligibilityResult:
    project_id: str
    rule_catalog_version: str
    as_of_date: date
    overall_status: OverallStatus
    evaluations: tuple[RuleEvaluation, ...]
    warnings: tuple[str, ...]

    def public_dict(self) -> dict[str, Any]:
        counts = {status.value: 0 for status in EvaluationStatus}
        for item in self.evaluations:
            counts[item.status.value] += 1
        return {
            "project_id": self.project_id,
            "rule_catalog_version": self.rule_catalog_version,
            "as_of_date": self.as_of_date.isoformat(),
            "overall_status": self.overall_status.value,
            "summary": counts,
            "evaluations": [item.public_dict() for item in self.evaluations],
            "warnings": list(self.warnings),
        }
