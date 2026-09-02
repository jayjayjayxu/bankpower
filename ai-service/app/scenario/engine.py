"""Program-owned V5 scenario arithmetic and break-even occupancy search."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, localcontext

from app.finance import FinanceCalculator, FinanceInput, ProvenancedValue, RepaymentMethod, SourceType, calculate_max_debt_ratio

from .models import ScenarioDefinition, ScenarioInput, ScenarioName, ScenarioResult


_SOURCE = "RESEARCH_ASSUMPTION:V5.0-B.1"


def standard_scenarios() -> tuple[ScenarioDefinition, ...]:
    """Versioned research assumptions, not bank policy or market forecasts."""

    return (
        ScenarioDefinition(ScenarioName.BASE, Decimal("0"), Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"), Decimal("0"), _SOURCE),
        ScenarioDefinition(ScenarioName.DOWNSIDE, Decimal("-0.10"), Decimal("0.95"), Decimal("1.10"), Decimal("1"), Decimal("1"), Decimal("0.005"), _SOURCE),
        ScenarioDefinition(ScenarioName.SEVERE, Decimal("-0.20"), Decimal("0.90"), Decimal("1.20"), Decimal("1.05"), Decimal("1.10"), Decimal("0.010"), _SOURCE),
    )


class ScenarioEngine:
    def __init__(self, calculator: FinanceCalculator | None = None) -> None:
        self.calculator = calculator or FinanceCalculator()

    def run(self, inputs: ScenarioInput, scenario: ScenarioDefinition) -> ScenarioResult:
        self._validate(inputs)
        with localcontext() as context:
            context.prec = 40
            occupancy = inputs.occupancy_rate.value + scenario.occupancy_delta
            if not Decimal("0") <= occupancy <= Decimal("1"):
                raise ValueError("压力后的 occupancy_rate 必须位于 0 到 1。")
            price = inputs.rack_price_yuan_month.value * scenario.rack_price_multiplier
            electricity_price = inputs.electricity_price_yuan_kwh.value * scenario.electricity_price_multiplier
            pue = inputs.pue.value * scenario.pue_multiplier
            capex = inputs.capex.value * scenario.capex_multiplier
            interest = inputs.interest_rate.value + scenario.interest_rate_delta
            revenue = inputs.rack_capacity.value * occupancy * price * Decimal("12")
            total_energy = inputs.rack_capacity.value * occupancy * inputs.avg_it_load_kw_per_occupied_rack.value * Decimal("8760") * pue
            electricity_cost = total_energy * electricity_price
            cashflow_proxy = revenue - electricity_cost - revenue * inputs.other_operating_cost_ratio.value
            term = int(inputs.loan_term_years.value)
            finance_inputs = FinanceInput(
                project_id=inputs.project_id,
                capex=ProvenancedValue(capex, "CNY", SourceType.DERIVED, f"{scenario.source_id}:capex"),
                debt_ratio=inputs.debt_ratio,
                interest_rate=ProvenancedValue(interest, "RATIO", SourceType.DERIVED, f"{scenario.source_id}:interest_rate"),
                loan_term_years=inputs.loan_term_years,
                repayment_method=RepaymentMethod.EQUAL_PRINCIPAL,
                annual_cfads=tuple(ProvenancedValue(cashflow_proxy, "CNY", SourceType.ASSUMPTION, f"{scenario.source_id}:pre_tax_cashflow_proxy:{year}") for year in range(1, term + 1)),
                required_min_dscr=inputs.required_min_dscr,
            )
            finance = self.calculator.calculate(finance_inputs).public_dict()
            maximum = calculate_max_debt_ratio(finance_inputs).public_dict()
        warnings = (
            "压力参数来源为研究假设，不是银行规则、监管阈值或市场预测。",
            "税前经营现金流代理不等同于经核验的项目 CFADS；仅用于情景敏感性演示。",
        )
        return ScenarioResult(scenario, occupancy, price, electricity_price, pue, capex, interest, revenue, electricity_cost, cashflow_proxy, finance, maximum, warnings)

    @staticmethod
    def _validate(inputs: ScenarioInput) -> None:
        positive = (inputs.rack_capacity, inputs.rack_price_yuan_month, inputs.pue, inputs.capex, inputs.loan_term_years, inputs.required_min_dscr)
        if any(item.value <= 0 for item in positive):
            raise ValueError("情景输入中的容量、价格、PUE、CAPEX、期限和最低 DSCR 必须为正数。")
        if not Decimal("0") <= inputs.occupancy_rate.value <= Decimal("1"):
            raise ValueError("occupancy_rate 必须介于 0 和 1。")
        if inputs.electricity_price_yuan_kwh.value < 0 or inputs.interest_rate.value < 0 or inputs.other_operating_cost_ratio.value < 0:
            raise ValueError("成本、利率和比例不能为负数。")


def break_even_occupancy(
    inputs: ScenarioInput, scenario: ScenarioDefinition, resolution: Decimal = Decimal("0.000001")
) -> Decimal | None:
    """Smallest occupancy whose scenario minimum DSCR reaches its stated threshold."""

    if resolution <= 0 or resolution >= 1:
        raise ValueError("resolution 必须介于 0 和 1。")
    engine = ScenarioEngine()
    threshold = inputs.required_min_dscr.value

    def result(rate: Decimal) -> ScenarioResult:
        occupancy = ProvenancedValue(rate, "RATIO", SourceType.DERIVED, "CALC:break_even_occupancy")
        return engine.run(replace(inputs, occupancy_rate=occupancy), scenario)

    full = result(Decimal("1"))
    if Decimal(full.finance["results"]["min_dscr"] or "0") < threshold:
        return None
    low, high = Decimal("0"), Decimal("1")
    while high - low > resolution:
        mid = (low + high) / Decimal("2")
        if Decimal(result(mid).finance["results"]["min_dscr"] or "0") >= threshold:
            high = mid
        else:
            low = mid
    return high
