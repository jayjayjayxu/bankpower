"""Auditable V5 project-snapshot data model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any


class FieldStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"
    CONFLICTING = "CONFLICTING"
    STALE = "STALE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class SnapshotEvidence:
    value: Any
    unit: str | None
    source_id: str
    source_locator: str | None
    scope: str | None
    as_of_date: str | None
    data_quality: str | None

    def public_dict(self) -> dict[str, Any]:
        return {
            "value": str(self.value) if self.value is not None else None,
            "unit": self.unit,
            "source_id": self.source_id,
            "source_locator": self.source_locator,
            "scope": self.scope,
            "as_of_date": self.as_of_date,
            "data_quality": self.data_quality,
        }


@dataclass(frozen=True)
class SnapshotField:
    field: str
    domain: str
    label: str
    status: FieldStatus
    required: bool
    weight: int
    evidence: tuple[SnapshotEvidence, ...]
    reason: str

    def public_dict(self) -> dict[str, Any]:
        return {
            "field": self.field, "domain": self.domain, "label": self.label,
            "status": self.status.value, "required": self.required, "weight": self.weight,
            "evidence": [item.public_dict() for item in self.evidence], "reason": self.reason,
        }


@dataclass(frozen=True)
class ProjectSnapshot:
    project_id: str
    project_name: str | None
    profile_version: str
    generated_at: str
    fields: tuple[SnapshotField, ...]

    def public_dict(self) -> dict[str, Any]:
        total_weight = sum(item.weight for item in self.fields if item.required)
        earned_weight = sum(
            item.weight
            for item in self.fields
            if item.required and item.status == FieldStatus.AVAILABLE
        )
        counts = {status.value: 0 for status in FieldStatus}
        domains: dict[str, list[dict[str, Any]]] = {}
        for item in self.fields:
            counts[item.status.value] += 1
            domains.setdefault(item.domain, []).append(item.public_dict())
        return {
            "project_id": self.project_id, "project_name": self.project_name,
            "profile_version": self.profile_version, "generated_at": self.generated_at,
            "data_completeness": {
                "score": str((earned_weight / total_weight * 100) if total_weight else 0),
                "required_weight": total_weight, "available_weight": earned_weight, "status_counts": counts,
                "definition": "仅表示尽调资料完整度；CONFLICTING、MISSING 和 STALE 不计为完整，不表示项目质量或授信评级。",
            },
            "domains": domains,
        }
