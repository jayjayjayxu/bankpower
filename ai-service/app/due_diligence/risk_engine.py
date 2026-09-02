"""V5-C deterministic risk flags and evidence-gap analysis."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any

from .models import FieldStatus, ProjectSnapshot


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RiskFlag:
    code: str
    domain: str
    level: RiskLevel
    trigger: str
    observed_value: str | None
    threshold: str | None
    source_id: str
    evidence_ids: tuple[str, ...]

    def public_dict(self) -> dict[str, Any]:
        return {"code": self.code, "domain": self.domain, "level": self.level.value, "trigger": self.trigger, "observed_value": self.observed_value, "threshold": self.threshold, "source_id": self.source_id, "evidence_ids": list(self.evidence_ids)}


@dataclass(frozen=True)
class EvidenceGap:
    code: str
    domain: str
    priority: RiskLevel
    required_evidence: str
    reason: str
    source_id: str

    def public_dict(self) -> dict[str, str]:
        return {"code": self.code, "domain": self.domain, "priority": self.priority.value, "required_evidence": self.required_evidence, "reason": self.reason, "source_id": self.source_id}


_REQUIREMENTS = {
    "cfads": "项目单独账套、收入/成本/税费、营运资本、维护 CAPEX 与现金流量表。",
    "financing_inputs": "贷款合同、当前余额、还款计划、利率条款和担保登记资料。",
    "energy_review_document": "项目节能审查批复及审查意见落实材料。",
    "renewable_energy_plan": "可再生能源利用目标、方案、绿电合同/绿证及结算凭证。",
    "green_power_ratio": "项目统计期内的绿电合同、绿证和结算单。",
}


class RiskEngine:
    def evaluate(self, snapshot: ProjectSnapshot, scenario_results: list[dict[str, Any]] | None = None, eligibility: dict[str, Any] | None = None) -> tuple[RiskFlag, ...]:
        flags: list[RiskFlag] = []
        for field in snapshot.fields:
            evidence_ids = tuple(item.source_id for item in field.evidence)
            if field.status == FieldStatus.CONFLICTING:
                flags.append(RiskFlag("DATA_CONFLICTING_DISCLOSURES", "DATA", RiskLevel.MEDIUM, f"{field.label} 存在多个不同披露值或口径", None, None, "DUE_DILIGENCE_PROFILE:V5.0-A.1", evidence_ids))
            elif field.status == FieldStatus.STALE:
                flags.append(RiskFlag("DATA_STALE", "DATA", RiskLevel.MEDIUM, f"{field.label} 已超过资料时效阈值", None, "730 days", "DUE_DILIGENCE_PROFILE:V5.0-A.1", evidence_ids))
            elif field.status == FieldStatus.MISSING and field.required:
                level = RiskLevel.HIGH if field.field in {"cfads", "financing_inputs"} else RiskLevel.MEDIUM
                flags.append(RiskFlag("DATA_REQUIRED_FIELD_MISSING", "DATA", level, f"缺少必需字段：{field.label}", None, None, "DUE_DILIGENCE_PROFILE:V5.0-A.1", evidence_ids))
        for result in scenario_results or []:
            min_dscr = Decimal(str((result.get("results") or {}).get("min_dscr") or "0"))
            name = str(result.get("scenario") or "UNKNOWN")
            if min_dscr < Decimal("1.0"):
                flags.append(RiskFlag("FIN_DSCR_BELOW_1", "FINANCE", RiskLevel.HIGH, f"{name} 情景最低 DSCR 低于 1.00", str(min_dscr), "1.00", "RESEARCH_ASSUMPTION:V5.0-B.1", (f"SCENARIO:{name}",)))
            elif min_dscr < Decimal("1.20"):
                flags.append(RiskFlag("FIN_DSCR_BELOW_120", "FINANCE", RiskLevel.MEDIUM, f"{name} 情景最低 DSCR 低于研究门槛", str(min_dscr), "1.20", "RESEARCH_ASSUMPTION:V5.0-B.1", (f"SCENARIO:{name}",)))
        if eligibility and eligibility.get("overall_status") == "INSUFFICIENT_EVIDENCE":
            flags.append(RiskFlag("POLICY_EVIDENCE_INSUFFICIENT", "POLICY", RiskLevel.MEDIUM, "已载入政策规则的证据不足", None, None, "POLICY_ELIGIBILITY_ENGINE", tuple(f"RULE:{item['rule_id']}" for item in eligibility.get("evaluations") or [])))
        return tuple(flags)


class EvidenceGapAnalyzer:
    def analyze(self, snapshot: ProjectSnapshot, eligibility: dict[str, Any] | None = None, risks: tuple[RiskFlag, ...] = ()) -> tuple[EvidenceGap, ...]:
        gaps: dict[str, EvidenceGap] = {}
        for field in snapshot.fields:
            if field.status in {FieldStatus.MISSING, FieldStatus.CONFLICTING, FieldStatus.STALE}:
                required = _REQUIREMENTS.get(field.field, f"{field.label} 的项目级原始资料、统计口径和最新期间证明。")
                priority = RiskLevel.HIGH if field.field in {"cfads", "financing_inputs"} else RiskLevel.MEDIUM
                gaps[f"SNAPSHOT:{field.field}"] = EvidenceGap(f"SNAPSHOT:{field.field}", field.domain, priority, required, field.reason, "DUE_DILIGENCE_PROFILE:V5.0-A.1")
        for item in (eligibility or {}).get("evaluations") or []:
            if item.get("status") == "UNKNOWN":
                target = ((item.get("condition") or {}).get("target_field"))
                required = _REQUIREMENTS.get(str(target), f"规则 {item.get('rule_id')} 所需的项目级证明材料。")
                gaps[f"RULE:{item.get('rule_id')}"] = EvidenceGap(f"RULE:{item.get('rule_id')}", "POLICY", RiskLevel.MEDIUM, required, str(item.get("reason") or "政策规则证据不足。"), "POLICY_ELIGIBILITY_ENGINE")
        for risk in risks:
            if risk.code == "FIN_DSCR_BELOW_1":
                gaps.setdefault("RISK:FIN_DSCR", EvidenceGap("RISK:FIN_DSCR", "FINANCE", RiskLevel.HIGH, _REQUIREMENTS["cfads"], "需以项目单独 CFADS 复核压力情景偿债覆盖。", risk.source_id))
        return tuple(gaps.values())
