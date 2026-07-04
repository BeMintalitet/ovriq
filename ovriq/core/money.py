"""OVRIQ pengetype: OQ som Decimal. Float eksisterer ikke i pengekode."""
from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation

QUANTUM = Decimal("0.0001")  # 4 decimaler
ZERO = Decimal("0.0000")


class MoneyError(Exception):
    pass


def oq(value) -> Decimal:
    """Konvertér til kvantiseret OQ-Decimal. Afviser float-artefakter og NaN/inf."""
    if isinstance(value, float):
        # floats accepteres kun via str-omvejen, så 0.1 bliver "0.1" og ikke 0.1000000000000000055...
        value = repr(value)
    try:
        d = Decimal(value).quantize(QUANTUM, rounding=ROUND_HALF_EVEN)
    except (InvalidOperation, ValueError, TypeError) as e:
        raise MoneyError(f"invalid OQ amount: {value!r}") from e
    if not d.is_finite():
        raise MoneyError(f"non-finite OQ amount: {value!r}")
    return d


def require_positive(amount: Decimal, what: str = "amount") -> Decimal:
    if amount <= ZERO:
        raise MoneyError(f"{what} must be positive, got {amount}")
    return amount


def s(amount: Decimal) -> str:
    """Kanonisk strengform til journal, hashes og API-svar."""
    return format(amount, "f")
