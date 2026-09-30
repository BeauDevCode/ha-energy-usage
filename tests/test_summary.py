"""Provider-neutral rolling summary boundary tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from custom_components.energy_usage.errors import PayloadError
from custom_components.energy_usage.models import EnergyInterval, Freshness, LedgerState
from custom_components.energy_usage.summary import summarize_usage

HOUR = datetime(2026, 9, 28, 10, tzinfo=UTC)


def interval(*, amount: Decimal | None, currency: str | None) -> EnergyInterval:
    return EnergyInterval(
        start=HOUR,
        end=HOUR + timedelta(hours=1),
        import_kwh=Decimal("2"),
        return_kwh=Decimal("0.5"),
        amount=amount,
        currency=currency,
        is_estimated=False,
        received_at=HOUR + timedelta(days=1),
    )


def test_empty_and_absent_money_remain_unknown() -> None:
    empty = summarize_usage(LedgerState(), time_zone="UTC", now=HOUR, currency="USD")
    assert empty.freshness is Freshness.UNKNOWN
    assert empty.latest_import_kwh is None
    assert empty.latest_cost is None

    no_amount = summarize_usage(
        LedgerState(intervals=(interval(amount=None, currency=None),)),
        time_zone="UTC",
        now=HOUR + timedelta(hours=2),
        currency="USD",
    )
    assert no_amount.latest_import_kwh == Decimal("2")
    assert no_amount.latest_return_kwh == Decimal("0.5")
    assert no_amount.latest_cost is None
    assert no_amount.latest_compensation is None


@pytest.mark.parametrize(
    ("time_zone", "now"),
    [("Not/AZone", HOUR), ("UTC", HOUR.replace(tzinfo=None))],
)
def test_invalid_time_boundaries_fail_closed(time_zone: str, now: datetime) -> None:
    with pytest.raises(PayloadError):
        summarize_usage(LedgerState(), time_zone=time_zone, now=now, currency=None)
