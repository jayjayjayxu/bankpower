"""Typed finance inputs/results with source provenance on every input value."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any


class SourceType(StrEnum):
    FACT = "FACT"
    ASSUMPTION = "ASSUMPTION"
    DERIVED = "DERIVED"


class RepaymentMethod(StrEnum):
    EQUAL_PRINCIPAL = "EQUAL_PRINCIPAL"


@dataclass(frozen=True)
class ProvenancedValue:
    value: Decimal
    unit: str
    source_type: SourceType
    source_id: str

    @classmethod
    def of(
        cls, value: str | int | float | Decimal, unit: str, source_type: SourceType, source_id: str
    ) -> "ProvenancedValue":
        return cls(Decimal(str(value)), unit, source_type, source_id)

    def public_dict(self) -> dict[str, str]:
        return {
            "value": str(self.value), "unit": self.unit,
            "source_type": self.source_type.value, "source_id": self.source_id,
        }


@dataclass(frozen=True)
class FinanceInput:
    project_id: str
    capex: ProvenancedValue
    debt_ratio: ProvenancedValue
    interest_rate: ProvenancedValue
    loan_term_years: ProvenancedValue
    repayment_method: RepaymentMethod
    annual_cfads: tuple[ProvenancedValue, ...]
    required_min_dscr: ProvenancedValue

    def public_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "capex": self.capex.public_dict(),
            "debt_ratio": self.debt_ratio.public_dict(),
            "interest_rate": self.interest_rate.public_dict(),
            "loan_term_years": self.loan_term_years.public_dict(),
            "repayment_method": self.repayment_method.value,
            "annual_cfads": [item.public_dict() for item in self.annual_cfads],
            "required_min_dscr": self.required_min_dscr.public_dict(),
        }


@dataclass(frozen=True)
class AnnualDebtSchedule:
    year: int
    beginning_balance: Decimal
    principal: Decimal
    interest: Decimal
    debt_service: Decimal
    cfads: Decimal
    dscr: Decimal | None

    def public_dict(self) -> dict[str, str | int | None]:
        return {
            "year": self.year,
            "beginning_balance": str(self.beginning_balance),
            "principal": str(self.principal),
            "interest": str(self.interest),
            "debt_service": str(self.debt_service),
            "cfads": str(self.cfads),
            "dscr": None if self.dscr is None else str(self.dscr),
        }


@dataclass(frozen=True)
class FinanceResult:
    calculation_id: str
    inputs: FinanceInput
    loan_amount: Decimal
    annual_schedule: tuple[AnnualDebtSchedule, ...]
    min_dscr: Decimal | None
    avg_dscr: Decimal | None
    warnings: tuple[str, ...]

    def public_dict(self) -> dict[str, Any]:
        return {
            "calculation_id": self.calculation_id,
            "inputs": self.inputs.public_dict(),
            "results": {
                "loan_amount": str(self.loan_amount),
                "debt_ratio": str(self.inputs.debt_ratio.value),
                "annual_schedule": [item.public_dict() for item in self.annual_schedule],
                "min_dscr": None if self.min_dscr is None else str(self.min_dscr),
                "avg_dscr": None if self.avg_dscr is None else str(self.avg_dscr),
            },
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class MaxDebtResult:
    max_debt_ratio: Decimal
    max_loan_amount: Decimal
    required_min_dscr: Decimal
    calculation: FinanceResult | None
    warnings: tuple[str, ...]

    def public_dict(self) -> dict[str, Any]:
        return {
            "max_debt_ratio": str(self.max_debt_ratio),
            "max_loan_amount": str(self.max_loan_amount),
            "required_min_dscr": str(self.required_min_dscr),
            "calculation_id": self.calculation.calculation_id if self.calculation else None,
            "warnings": list(self.warnings),
        }
