"""Input validation for deterministic financing calculations."""

from __future__ import annotations

from decimal import Decimal

from .models import FinanceInput, RepaymentMethod, SourceType


class FinanceValidationError(ValueError):
    pass


def _require_provenance(source_type: SourceType, source_id: str, field: str) -> None:
    if not source_id.strip():
        raise FinanceValidationError(f"{field} 缺少 source_id，无法追溯来源。")
    if source_type not in {SourceType.FACT, SourceType.ASSUMPTION, SourceType.DERIVED}:
        raise FinanceValidationError(f"{field} 使用了不支持的 source_type。")


def validate_finance_input(value: FinanceInput) -> None:
    if not value.project_id.strip():
        raise FinanceValidationError("project_id 不能为空。")
    for field, item in (
        ("capex", value.capex), ("debt_ratio", value.debt_ratio),
        ("interest_rate", value.interest_rate), ("loan_term_years", value.loan_term_years),
        ("required_min_dscr", value.required_min_dscr),
    ):
        _require_provenance(item.source_type, item.source_id, field)
    if value.capex.unit != "CNY" or value.capex.value <= 0:
        raise FinanceValidationError("capex 必须为正数 CNY。")
    if value.debt_ratio.unit != "RATIO" or not Decimal("0") <= value.debt_ratio.value <= Decimal("1"):
        raise FinanceValidationError("debt_ratio 必须为 0 到 1 之间的 RATIO。")
    if value.interest_rate.unit != "RATIO" or value.interest_rate.value < 0:
        raise FinanceValidationError("interest_rate 必须为非负 RATIO。")
    if value.loan_term_years.unit != "YEAR" or value.loan_term_years.value != value.loan_term_years.value.to_integral_value() or value.loan_term_years.value <= 0:
        raise FinanceValidationError("loan_term_years 必须为正整数 YEAR。")
    if value.required_min_dscr.unit != "RATIO" or value.required_min_dscr.value <= 0:
        raise FinanceValidationError("required_min_dscr 必须为正 RATIO。")
    if value.repayment_method != RepaymentMethod.EQUAL_PRINCIPAL:
        raise FinanceValidationError("V4.0-A 仅支持 EQUAL_PRINCIPAL。")
    if len(value.annual_cfads) != int(value.loan_term_years.value):
        raise FinanceValidationError("annual_cfads 必须与 loan_term_years 一一对应。")
    for index, item in enumerate(value.annual_cfads, 1):
        _require_provenance(item.source_type, item.source_id, f"annual_cfads[{index}]")
        if item.unit != "CNY":
            raise FinanceValidationError(f"annual_cfads[{index}] 必须为 CNY。")
