"""Provider-neutral rolling energy usage summaries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import PayloadError
from .models import EnergyInterval, Freshness, LedgerState, UsageSnapshot, exact_sum


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        raise PayloadError from None


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PayloadError
    return value.astimezone(UTC)


def summarize_usage(
    state: LedgerState,
    *,
    time_zone: str,
    now: datetime,
    currency: str | None,
) -> UsageSnapshot:
    """Summarize intervals in the configured local calendar and age window."""
    zone = _zone(time_zone)
    current = _aware_utc(now)
    intervals = state.intervals
    monetary_allowed = currency is not None and all(
        item.amount is None or item.currency == currency for item in intervals
    )
    newest = intervals[-1] if intervals else None
    if newest is None:
        freshness = Freshness.UNKNOWN
    else:
        age = current - newest.end
        if age <= timedelta(hours=36):
            freshness = Freshness.FRESH
        elif age <= timedelta(hours=72):
            freshness = Freshness.DELAYED
        else:
            freshness = Freshness.STALE

    local_today = current.astimezone(zone).date()
    buckets: dict[str, list[EnergyInterval]] = {"today": [], "seven_day": [], "month": []}
    for interval in intervals:
        local_date = interval.start.astimezone(zone).date()
        if local_date == local_today:
            buckets["today"].append(interval)
        if local_today - timedelta(days=6) <= local_date <= local_today:
            buckets["seven_day"].append(interval)
        if local_date.year == local_today.year and local_date.month == local_today.month:
            buckets["month"].append(interval)

    def total(items: list[EnergyInterval], kind: str) -> Decimal | None:
        if not items:
            return None
        if kind == "import":
            return exact_sum(item.import_kwh for item in items)
        if kind == "return":
            return exact_sum(item.return_kwh for item in items)
        if not monetary_allowed:
            return None
        amounts = [item.amount for item in items if item.amount is not None]
        if not amounts:
            return None
        if kind == "cost":
            return exact_sum(max(amount, Decimal(0)) for amount in amounts)
        return exact_sum(max(amount.copy_negate(), Decimal(0)) for amount in amounts)

    latest = [newest] if newest is not None else []
    return UsageSnapshot(
        newest_interval_start=newest.start if newest is not None else None,
        freshness=freshness,
        latest_import_kwh=total(latest, "import"),
        latest_return_kwh=total(latest, "return"),
        today_import_kwh=total(buckets["today"], "import"),
        today_return_kwh=total(buckets["today"], "return"),
        seven_day_import_kwh=total(buckets["seven_day"], "import"),
        seven_day_return_kwh=total(buckets["seven_day"], "return"),
        month_import_kwh=total(buckets["month"], "import"),
        month_return_kwh=total(buckets["month"], "return"),
        latest_cost=total(latest, "cost"),
        today_cost=total(buckets["today"], "cost"),
        seven_day_cost=total(buckets["seven_day"], "cost"),
        month_cost=total(buckets["month"], "cost"),
        latest_compensation=total(latest, "compensation"),
        today_compensation=total(buckets["today"], "compensation"),
        seven_day_compensation=total(buckets["seven_day"], "compensation"),
        month_compensation=total(buckets["month"], "compensation"),
    )
