"""Program-owned evaluation of fixed policy rules; no LLM or RAG call occurs here."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from .models import (
    EligibilityResult,
    EvaluationStatus,
    OverallStatus,
    PolicyRule,
    ProjectFact,
    RuleEvaluation,
    RuleOperator,
    RuleType,
)


class EligibilityEngine:
    """Evaluate supplied facts against a versioned, manually-curated rule set."""

    def evaluate(
        self,
        *,
        project_id: str,
        rule_catalog_version: str,
        rules: tuple[PolicyRule, ...],
        facts: dict[str, ProjectFact],
        as_of_date: date | None = None,
    ) -> EligibilityResult:
        if not project_id.strip() or not rule_catalog_version.strip() or not rules:
            raise ValueError("project_id、rule_catalog_version 和 rules 不能为空。")
        as_of = as_of_date or date.today()
        evaluations = tuple(self._evaluate_rule(rule, facts, as_of) for rule in rules)
        warnings = (
            "结果仅表示已载入规则与已提供证据的逐项匹配，不构成绿色贷款认定、授信审批或融资建议。",
            "UNKNOWN 表示证据缺失或不适用范围未能核验，不等同于 UNMET。",
        )
        return EligibilityResult(
            project_id=project_id,
            rule_catalog_version=rule_catalog_version,
            as_of_date=as_of,
            overall_status=self._overall(evaluations),
            evaluations=evaluations,
            warnings=warnings,
        )

    def _evaluate_rule(
        self, rule: PolicyRule, facts: dict[str, ProjectFact], as_of: date
    ) -> RuleEvaluation:
        if rule.effective_date and as_of < rule.effective_date:
            return RuleEvaluation(rule, EvaluationStatus.NOT_APPLICABLE, "规则在该核验日尚未生效。", None)
        if rule.expiry_date and as_of > rule.expiry_date:
            return RuleEvaluation(rule, EvaluationStatus.NOT_APPLICABLE, "规则在该核验日已失效。", None)
        applicability = self._check_applicability(rule, facts)
        if applicability is not None:
            status, reason = applicability
            return RuleEvaluation(rule, status, reason, None)
        fact = facts.get(rule.target_field)
        if fact is None:
            return RuleEvaluation(rule, EvaluationStatus.UNKNOWN, f"缺少项目字段 {rule.target_field} 的可追溯证据。", None)
        if fact.unit != rule.unit:
            return RuleEvaluation(rule, EvaluationStatus.UNKNOWN, f"字段 {rule.target_field} 的单位为 {fact.unit}，与规则单位 {rule.unit} 不一致。", fact)
        try:
            met = self._matches(rule, fact.value)
        except (InvalidOperation, TypeError, ValueError):
            return RuleEvaluation(rule, EvaluationStatus.UNKNOWN, f"字段 {rule.target_field} 的值无法按 {rule.rule_type.value} 规则比较。", fact)
        return RuleEvaluation(
            rule,
            EvaluationStatus.MET if met else EvaluationStatus.UNMET,
            self._comparison_reason(rule, fact.value, met),
            fact,
        )

    @staticmethod
    def _normalise(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value).strip().casefold()

    def _check_applicability(
        self, rule: PolicyRule, facts: dict[str, ProjectFact]
    ) -> tuple[EvaluationStatus, str] | None:
        for field, allowed in rule.applicability.items():
            fact = facts.get(field)
            if fact is None:
                return EvaluationStatus.UNKNOWN, f"缺少适用范围字段 {field}，无法确认规则是否适用。"
            actual = self._normalise(fact.value)
            expected = {self._normalise(item) for item in allowed}
            if actual not in expected:
                return EvaluationStatus.NOT_APPLICABLE, f"项目 {field}={fact.value} 不在规则适用范围内。"
        return None

    def _matches(self, rule: PolicyRule, actual: Any) -> bool:
        if rule.rule_type == RuleType.NUMERIC_THRESHOLD:
            value, threshold = Decimal(str(actual)), Decimal(str(rule.threshold_value))
            return value <= threshold if rule.operator == RuleOperator.LTE else value >= threshold
        if rule.rule_type == RuleType.BOOLEAN:
            return self._normalise(actual) == self._normalise(rule.threshold_value)
        if rule.rule_type == RuleType.ENUM:
            return self._normalise(actual) in {self._normalise(item) for item in rule.threshold_value}
        if rule.rule_type == RuleType.DOCUMENT_REQUIRED:
            return self._normalise(actual) == "true"
        raise ValueError("不支持的规则类型。")

    @staticmethod
    def _comparison_reason(rule: PolicyRule, actual: Any, met: bool) -> str:
        outcome = "满足" if met else "不满足"
        if rule.rule_type == RuleType.DOCUMENT_REQUIRED:
            return f"项目材料登记值为 {actual}，{outcome}“{rule.description}”的材料要求。"
        return f"项目值 {actual} 与规则 {rule.operator.value} {rule.threshold_value} 比较，{outcome}该项规则。"

    @staticmethod
    def _overall(evaluations: tuple[RuleEvaluation, ...]) -> OverallStatus:
        applicable = [item for item in evaluations if item.status != EvaluationStatus.NOT_APPLICABLE]
        if not applicable or any(item.status == EvaluationStatus.UNKNOWN for item in applicable):
            return OverallStatus.INSUFFICIENT_EVIDENCE
        if any(item.status == EvaluationStatus.UNMET and item.rule.mandatory for item in applicable):
            return OverallStatus.EXPLICIT_RULE_NOT_MET
        if any(item.status == EvaluationStatus.UNMET for item in applicable):
            return OverallStatus.PARTIAL_MATCH
        return OverallStatus.MATCHED_ON_KNOWN_RULES
