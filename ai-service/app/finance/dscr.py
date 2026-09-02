"""DSCR calculations over program-owned debt-service schedules."""

from __future__ import annotations

from decimal import Decimal


def dscr(cfads: Decimal, debt_service: Decimal) -> Decimal | None:
    """Return ``None`` when no debt service exists; it is not an infinite DSCR."""

    if debt_service == 0:
        return None
    return cfads / debt_service


def min_and_average(values: list[Decimal | None]) -> tuple[Decimal | None, Decimal | None]:
    defined = [value for value in values if value is not None]
    if not defined:
        return None, None
    return min(defined), sum(defined, Decimal("0")) / Decimal(len(defined))
