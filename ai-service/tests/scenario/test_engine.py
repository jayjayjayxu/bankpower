from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[2]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.finance.models import ProvenancedValue, SourceType
from app.scenario import ScenarioEngine, ScenarioInput, break_even_occupancy, standard_scenarios


def value(number: str, unit: str, source: SourceType = SourceType.FACT) -> ProvenancedValue:
    return ProvenancedValue(Decimal(number), unit, source, "TEST:SOURCE")


def inputs() -> ScenarioInput:
    return ScenarioInput(
        project_id="TEST", rack_capacity=value("100", "CABINET"), occupancy_rate=value("0.5", "RATIO"),
        rack_price_yuan_month=value("100", "CNY_PER_RACK_MONTH"), avg_it_load_kw_per_occupied_rack=value("0.01", "KW"),
        pue=value("1.2", "RATIO"), electricity_price_yuan_kwh=value("0.1", "CNY_PER_KWH"),
        other_operating_cost_ratio=value("0.1", "RATIO"), capex=value("100000", "CNY"), debt_ratio=value("0.5", "RATIO", SourceType.ASSUMPTION),
        interest_rate=value("0.1", "RATIO", SourceType.ASSUMPTION), loan_term_years=value("2", "YEAR", SourceType.ASSUMPTION),
        required_min_dscr=value("1.2", "RATIO", SourceType.ASSUMPTION),
    )


class ScenarioEngineTests(unittest.TestCase):
    def test_base_scenario_matches_manual_proxy_formula(self) -> None:
        result = ScenarioEngine().run(inputs(), standard_scenarios()[0])
        self.assertEqual(result.annual_revenue_proxy_cny, Decimal("60000"))
        self.assertEqual(result.annual_electricity_cost_proxy_cny, Decimal("525.60000"))
        self.assertEqual(result.annual_pre_tax_cashflow_proxy_cny, Decimal("53474.40000"))
        self.assertEqual(result.finance["results"]["loan_amount"], "50000.0")

    def test_downside_and_severe_apply_only_declared_research_parameters(self) -> None:
        engine = ScenarioEngine()
        base, downside, severe = (engine.run(inputs(), item) for item in standard_scenarios())
        self.assertEqual(downside.effective_occupancy_rate, Decimal("0.40"))
        self.assertEqual(downside.effective_interest_rate, Decimal("0.105"))
        self.assertEqual(severe.effective_capex, Decimal("110000.0"))
        self.assertLess(severe.annual_pre_tax_cashflow_proxy_cny, downside.annual_pre_tax_cashflow_proxy_cny)
        self.assertLess(Decimal(severe.finance["results"]["min_dscr"]), Decimal(base.finance["results"]["min_dscr"]))

    def test_break_even_occupancy_matches_dscr_threshold(self) -> None:
        rate = break_even_occupancy(inputs(), standard_scenarios()[0], Decimal("0.00000001"))
        self.assertIsNotNone(rate)
        self.assertLess(abs(rate - (Decimal("36000") / Decimal("106948.8"))), Decimal("0.00000002"))

    def test_unreachable_break_even_returns_none(self) -> None:
        impossible = ScenarioInput(**{**inputs().__dict__, "electricity_price_yuan_kwh": value("20", "CNY_PER_KWH")})
        self.assertIsNone(break_even_occupancy(impossible, standard_scenarios()[0]))

    def test_results_keep_proxy_and_research_assumption_boundaries(self) -> None:
        public = ScenarioEngine().run(inputs(), standard_scenarios()[1]).public_dict()
        self.assertEqual(public["scenario_source"], "RESEARCH_ASSUMPTION:V5.0-B.1")
        self.assertIn("代理", public["warnings"][1])


if __name__ == "__main__":
    unittest.main()
