"""Deterministic V4.0-A loan, debt-service, DSCR and debt-capacity calculator."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, localcontext
from uuid import uuid4

from .dscr import dscr, min_and_average
from .models import AnnualDebtSchedule, FinanceInput, FinanceResult, MaxDebtResult, ProvenancedValue, SourceType
from .repayment import equal_principal_schedule
from .validators import validate_finance_input


class FinanceCalculator:
    def calculate(self, inputs: FinanceInput) -> FinanceResult:
        validate_finance_input(inputs)
        with localcontext() as context:
            context.prec = 40
            loan_amount = inputs.capex.value * inputs.debt_ratio.value
            repayment = equal_principal_schedule(
                loan_amount, inputs.interest_rate.value, int(inputs.loan_term_years.value)
            )
            annual_schedule = []
            for index, ((balance, principal, interest), cfads_input) in enumerate(zip(repayment, inputs.annual_cfads, strict=True), 1):
                debt_service = principal + interest
                annual_schedule.append(AnnualDebtSchedule(
                    year=index, beginning_balance=balance, principal=principal, interest=interest,
                    debt_service=debt_service, cfads=cfads_input.value,
                    dscr=dscr(cfads_input.value, debt_service),
                ))
            minimum, average = min_and_average([item.dscr for item in annual_schedule])
        warnings: list[str] = []
        if inputs.debt_ratio.value == 0:
            warnings.append("债务比例为 0，未形成债务服务，因此 DSCR 不适用。")
        if any(item.cfads <= 0 for item in annual_schedule):
            warnings.append("至少一个期间的 CFADS 为零或负数；该情景不支持正向债务承受能力。")
        if any(item.source_type == SourceType.ASSUMPTION for item in inputs.annual_cfads):
            warnings.append("CFADS 包含用户或研究假设，不代表已核验项目现金流。")
        return FinanceResult(
            calculation_id=f"CALC-{uuid4().hex[:12].upper()}", inputs=inputs, loan_amount=loan_amount,
            annual_schedule=tuple(annual_schedule), min_dscr=minimum, avg_dscr=average,
            warnings=tuple(warnings),
        )


def calculate_max_debt_ratio(inputs: FinanceInput, resolution: Decimal = Decimal("0.000001")) -> MaxDebtResult:
    """Find the largest ratio in [0, 1] whose minimum DSCR meets the requirement.

    The search is deterministic bisection.  It never treats a zero-debt schedule
    as an infinite DSCR, and returns zero capacity when no positive ratio meets
    the required DSCR.
    """

    validate_finance_input(inputs)
    if resolution <= 0 or resolution >= 1:
        raise ValueError("resolution 必须介于 0 和 1 之间。")
    calculator = FinanceCalculator()
    required = inputs.required_min_dscr.value

    def run(ratio: Decimal) -> FinanceResult:
        ratio_input = ProvenancedValue(ratio, "RATIO", SourceType.DERIVED, "CALC:max_debt_ratio_search")
        return calculator.calculate(replace(inputs, debt_ratio=ratio_input))

    full = run(Decimal("1"))
    if full.min_dscr is not None and full.min_dscr >= required:
        return MaxDebtResult(Decimal("1"), full.loan_amount, required, full, tuple())
    low, high, best = Decimal("0"), Decimal("1"), None
    while high - low > resolution:
        middle = (low + high) / Decimal("2")
        calculated = run(middle)
        if calculated.min_dscr is not None and calculated.min_dscr >= required:
            low, best = middle, calculated
        else:
            high = middle
    if best is None:
        return MaxDebtResult(
            Decimal("0"), Decimal("0"), required, None,
            ("没有正的债务比例能满足最低 DSCR 要求。",),
        )
    return MaxDebtResult(low, best.loan_amount, required, best, tuple())
