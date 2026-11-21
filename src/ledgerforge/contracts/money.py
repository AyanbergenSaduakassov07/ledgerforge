"""Published money, FX and time semantics (policy.json describes the same rules in words).

- Amounts are integers in minor units; exponent per currency from CURRENCY_EXPONENTS.
- A rate is a decimal string: target-currency units per ONE source-currency unit.
- Conversion: round_half_even(amount_minor * rate * 10**(exp_target - exp_source)).
- FX date for a document = its recognition date (local date of issued_at / timestamp in the
  episode timezone). If fx.csv has no row that day, use the most recent earlier row.
- Reporting period membership uses that same local date; bounds are inclusive.
"""

from __future__ import annotations

import bisect
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_EVEN, Decimal

from ledgerforge.contracts.schemas import CURRENCY_EXPONENTS, fx_id

ROUNDING = "ROUND_HALF_EVEN"


def parse_offset(offset: str) -> timezone:
    """'+05:00' -> timezone(timedelta(hours=5))."""
    sign = -1 if offset[0] == "-" else 1
    hours, minutes = offset[1:].split(":")
    return timezone(sign * timedelta(hours=int(hours), minutes=int(minutes)))


def parse_ts(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError(f"timestamp without offset: {value}")
    return dt


def fmt_ts(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def local_date(value: str, offset: str) -> str:
    """Recognition date: calendar date of `value` in the episode timezone offset."""
    return parse_ts(value).astimezone(parse_offset(offset)).date().isoformat()


def in_period(day: str, start: str, end: str) -> bool:
    return start <= day <= end  # ISO dates compare lexicographically


def convert(amount_minor: int, source: str, target: str, rate: str) -> int:
    scale = Decimal(10) ** (CURRENCY_EXPONENTS[target] - CURRENCY_EXPONENTS[source])
    value = Decimal(amount_minor) * Decimal(rate) * scale
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


class FxTable:
    """Index over fx.csv rows for policy-correct rate lookup."""

    def __init__(self, rows: list[dict]) -> None:
        series: dict[tuple[str, str], list[tuple[str, str]]] = {}
        for r in rows:
            series.setdefault((r["source_currency"], r["target_currency"]), []).append(
                (r["date"], r["rate"])
            )
        self._series = {k: sorted(v) for k, v in series.items()}

    def effective(self, source: str, target: str, day: str) -> tuple[str, str] | None:
        """(fx_id, rate) of the most recent row on or before `day`, or None."""
        rows = self._series.get((source, target), [])
        idx = bisect.bisect_right(rows, (day, "￿")) - 1
        if idx < 0:
            return None
        row_date, rate = rows[idx]
        return fx_id(row_date, source, target), rate


def add_days(day: str, n: int) -> str:
    return (date.fromisoformat(day) + timedelta(days=n)).isoformat()
