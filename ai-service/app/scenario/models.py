"""Explicit inputs and results for V5 stress testing."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any

from app.finance.models import ProvenancedValue


class ScenarioName(StrEnum):
    BASE = "BASE"
    DOWNSIDE = "DOWNSIDE"
    SEVERE = "SEVERE"


@dataclass(frozen=True)
class ScenarioDefinition:
    name: ScenarioName
    occupancy_delta: Decimal
    rack_price_multiplier: Decimal
    electricity_price_multiplier: Decimal
    pue_multiplier: Decimal
    capex_multiplier: Decimal
    interest_rate_delta: Decimal
    source_id: str


@dataclass(frozen=True)
class ScenarioInput:
    project_id: str
    rack_capacity: ProvenancedValue
    occupancy_rate: ProvenancedValue
    rack_price_yuan_month: ProvenancedValue
    avg_it_load_kw_per_occupied_rack: ProvenancedValue
    pue: ProvenancedValue
    electricity_price_yuan_kwh: ProvenancedValue
    other_operating_cost_ratio: ProvenancedValue
    capex: ProvenancedValue
    debt_ratio: ProvenancedValue
    interest_rate: ProvenancedValue
    loan_term_years: ProvenancedValue
    required_min_dscr: ProvenancedValue


@dataclass(frozen=True)
class ScenarioResult:
    scenario: ScenarioDefinition
    effective_occupancy_rate: Decimal
    effective_rack_price_yuan_month: Decimal
    effective_electricity_price_yuan_kwh: Decimal
    effective_pue: Decimal
    effective_capex: Decimal
    effective_interest_rate: Decimal
    annual_revenue_proxy_cny: Decimal
    annual_electricity_cost_proxy_cny: Decimal
    annual_pre_tax_cashflow_proxy_cny: Decimal
    finance: dict[str, Any]
    max_debt: dict[str, Any]
    warnings: tuple[str, ...]

    def public_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario.name.value,
            "scenario_source": self.scenario.source_id,
            "effective_inputs": {
                "occupancy_rate": str(self.effective_occupancy_rate),
                "rack_price_yuan_month": str(self.effective_rack_price_yuan_month),
                "electricity_price_yuan_kwh": str(self.effective_electricity_price_yuan_kwh),
                "pue": str(self.effective_pue), "capex": str(self.effective_capex),
                "interest_rate": str(self.effective_interest_rate),
            },
            "results": {
                "annual_revenue_proxy_cny": str(self.annual_revenue_proxy_cny),
                "annual_electricity_cost_proxy_cny": str(self.annual_electricity_cost_proxy_cny),
                "annual_pre_tax_cashflow_proxy_cny": str(self.annual_pre_tax_cashflow_proxy_cny),
                "min_dscr": self.finance["results"]["min_dscr"],
                "max_debt_ratio": self.max_debt["max_debt_ratio"],
            },
            "finance": self.finance, "max_debt": self.max_debt, "warnings": list(self.warnings),
        }
