"""Program-owned equal-principal debt repayment schedule."""

from __future__ import annotations

from decimal import Decimal


def equal_principal_schedule(loan_amount: Decimal, annual_interest_rate: Decimal, term_years: int) -> list[tuple[Decimal, Decimal, Decimal]]:
    """Return ``(beginning_balance, principal, interest)`` for each annual period."""

    if loan_amount < 0 or annual_interest_rate < 0 or term_years <= 0:
        raise ValueError("贷款本金、利率和期限不合法。")
    if loan_amount == 0:
        return [(Decimal("0"), Decimal("0"), Decimal("0")) for _ in range(term_years)]
    standard_principal = loan_amount / Decimal(term_years)
    balance = loan_amount
    schedule: list[tuple[Decimal, Decimal, Decimal]] = []
    for year in range(1, term_years + 1):
        principal = balance if year == term_years else standard_principal
        interest = balance * annual_interest_rate
        schedule.append((balance, principal, interest))
        balance -= principal
    return schedule
