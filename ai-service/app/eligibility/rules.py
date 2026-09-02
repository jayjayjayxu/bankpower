"""Strict loader for the manually curated, evidence-bound V4 rule catalogue."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from .models import PolicyEvidence, PolicyRule, RuleOperator, RuleType


class EligibilityRuleError(ValueError):
    pass


_OPERATORS_BY_TYPE = {
    RuleType.NUMERIC_THRESHOLD: {RuleOperator.LTE, RuleOperator.GTE},
    RuleType.BOOLEAN: {RuleOperator.EQUALS},
    RuleType.ENUM: {RuleOperator.IN},
    RuleType.DOCUMENT_REQUIRED: {RuleOperator.EQUALS},
}


def _date(value: Any, field: str, rule_id: str) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise EligibilityRuleError(f"{rule_id}: {field} 必须为 YYYY-MM-DD。") from exc


def _required(raw: dict[str, Any], field: str, rule_id: str) -> Any:
    value = raw.get(field)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise EligibilityRuleError(f"{rule_id}: 缺少 {field}。")
    return value


def rule_from_dict(raw: dict[str, Any]) -> PolicyRule:
    rule_id = str(_required(raw, "rule_id", "<unknown>"))
    try:
        rule_type = RuleType(str(_required(raw, "rule_type", rule_id)))
        operator = RuleOperator(str(_required(raw, "operator", rule_id)))
    except ValueError as exc:
        raise EligibilityRuleError(f"{rule_id}: rule_type 或 operator 不受支持。") from exc
    if operator not in _OPERATORS_BY_TYPE[rule_type]:
        raise EligibilityRuleError(f"{rule_id}: {rule_type.value} 不能使用 {operator.value}。")
    threshold = raw.get("threshold_value")
    if rule_type != RuleType.DOCUMENT_REQUIRED and threshold is None:
        raise EligibilityRuleError(f"{rule_id}: 缺少 threshold_value。")
    if rule_type == RuleType.NUMERIC_THRESHOLD:
        try:
            str(threshold)
        except (TypeError, ValueError) as exc:
            raise EligibilityRuleError(f"{rule_id}: 数值阈值非法。") from exc
    applicability_raw = raw.get("applicability") or {}
    if not isinstance(applicability_raw, dict):
        raise EligibilityRuleError(f"{rule_id}: applicability 必须是对象。")
    applicability: dict[str, tuple[Any, ...]] = {}
    for field, allowed in applicability_raw.items():
        values = allowed if isinstance(allowed, list) else [allowed]
        if not field or not values:
            raise EligibilityRuleError(f"{rule_id}: applicability 条件非法。")
        applicability[str(field)] = tuple(values)
    effective, expiry = _date(raw.get("effective_date"), "effective_date", rule_id), _date(raw.get("expiry_date"), "expiry_date", rule_id)
    if effective and expiry and effective > expiry:
        raise EligibilityRuleError(f"{rule_id}: effective_date 晚于 expiry_date。")
    return PolicyRule(
        rule_id=rule_id,
        evidence=PolicyEvidence(
            policy_id=str(_required(raw, "policy_id", rule_id)),
            evidence_chunk_id=str(_required(raw, "evidence_chunk_id", rule_id)),
            source_excerpt=str(_required(raw, "source_excerpt", rule_id)),
        ),
        rule_type=rule_type,
        target_field=str(_required(raw, "target_field", rule_id)),
        operator=operator,
        threshold_value=threshold,
        unit=str(_required(raw, "unit", rule_id)),
        region=str(_required(raw, "region", rule_id)),
        entity_type=str(_required(raw, "entity_type", rule_id)),
        mandatory=bool(raw.get("mandatory", False)),
        effective_date=effective,
        expiry_date=expiry,
        description=str(_required(raw, "description", rule_id)),
        applicability=applicability,
    )


def load_rule_catalog(path: Path) -> tuple[str, tuple[PolicyRule, ...]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EligibilityRuleError(f"无法读取规则目录：{path}") from exc
    version = str(raw.get("catalog_version") or "")
    rules_raw = raw.get("rules")
    if not version or not isinstance(rules_raw, list) or not rules_raw:
        raise EligibilityRuleError("规则目录必须包含 catalog_version 和非空 rules。")
    rules = tuple(rule_from_dict(item) for item in rules_raw if isinstance(item, dict))
    if len(rules) != len(rules_raw) or len({item.rule_id for item in rules}) != len(rules):
        raise EligibilityRuleError("规则目录含非对象规则或重复 rule_id。")
    return version, rules


def validate_evidence_references(rules: tuple[PolicyRule, ...], corpus_path: Path) -> None:
    """Ensure a rule never points to a missing or mismatched V3 policy chunk."""

    try:
        records = [json.loads(line) for line in corpus_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as exc:
        raise EligibilityRuleError(f"无法读取政策证据语料：{corpus_path}") from exc
    by_chunk = {str(item.get("chunk_id")): item for item in records}
    for rule in rules:
        record = by_chunk.get(rule.evidence.evidence_chunk_id)
        if record is None:
            raise EligibilityRuleError(f"{rule.rule_id}: evidence_chunk_id 不存在于政策语料。")
        if str(record.get("document_id")) != rule.evidence.policy_id:
            raise EligibilityRuleError(f"{rule.rule_id}: evidence_chunk_id 与 policy_id 不一致。")
        source_text = re.sub(r"\s+", "", str(record.get("text") or ""))
        excerpt = re.sub(r"\s+", "", rule.evidence.source_excerpt)
        if excerpt not in source_text:
            raise EligibilityRuleError(f"{rule.rule_id}: source_excerpt 未在 evidence_chunk 中找到。")
