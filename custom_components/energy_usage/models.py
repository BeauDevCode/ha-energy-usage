"""Immutable, privacy-safe values shared by the integration layers."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import MAX_EMAX, MIN_EMIN, Context, Decimal, localcontext
from enum import StrEnum
from hashlib import sha256
from math import isfinite
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_PROVIDER_KEY = re.compile(r"[a-z0-9_]{1,32}\Z", re.ASCII)


def validate_decimal(value: Decimal, *, derived: bool = False) -> None:
    """Bound untrusted representation size before any arithmetic allocation."""
    parts = value.as_tuple()
    if (
        not value.is_finite()
        or not isinstance(parts.exponent, int)
        or not -1024 <= parts.exponent <= 1024
        or len(parts.digits) > (4096 if derived else 1024)
    ):
        raise ValueError("unsafe decimal representation")
    if derived and not isfinite(float(value)):
        raise ValueError("unsafe Recorder total")


def exact_sum(values: Iterable[Decimal]) -> Decimal:
    """Sum bounded decimals exactly, without ambient rounding or unbounded precision."""
    items = tuple(values)
    if not items:
        return Decimal(0)
    for item in items:
        validate_decimal(item, derived=True)
    precision = max(
        1,
        max(item.adjusted() for item in items)
        - min(int(item.as_tuple().exponent) for item in items)
        + len(str(len(items)))
        + 2,
    )
    if precision > 4096:
        raise ValueError("unsafe decimal precision")
    with localcontext(Context(prec=precision, Emax=MAX_EMAX, Emin=MIN_EMIN)):
        result = sum(items, Decimal(0))
    validate_decimal(result, derived=True)
    return result


def _canonical_decimal(value: Decimal) -> str:
    """Encode a finite number by coefficient and exponent without active context."""
    if value.is_zero():
        return "0"
    parts = value.as_tuple()
    digits = list(parts.digits)
    exponent = parts.exponent
    assert isinstance(exponent, int)
    while digits[-1] == 0:
        digits.pop()
        exponent += 1
    return f"{parts.sign}:{''.join(str(digit) for digit in digits)}:{exponent}"


@dataclass(frozen=True, slots=True, repr=False)
class Credentials:
    """Login inputs, never shown by repr."""

    username: str
    password: str


@dataclass(frozen=True, slots=True, repr=False)
class ClientMetadata:
    """Utility client identifier."""

    client_id: str


@dataclass(frozen=True, slots=True, repr=False)
class LoginResult:
    """A token and optional challenge marker."""

    access_token: str
    next_action: str | None = None


@dataclass(frozen=True, slots=True, repr=False)
class Account:
    """Account identity with a masked display label."""

    account_id: str
    nickname: str | None = None
    time_zone: str | None = None

    @property
    def display_name(self) -> str:
        """Show at most the final four account characters."""
        suffix = self.account_id[-4:]
        label = f"••••{suffix}"
        return f"{label} ({self.nickname})" if self.nickname else label


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """Measurements and timing behavior explicitly supported by a provider."""

    supports_import: bool
    supports_return: bool
    supports_cost: bool
    supports_compensation: bool
    currency: str | None
    interval_duration: timedelta
    publication_delay: timedelta
    historical_range: timedelta
    minimum_poll_interval: timedelta

    def __post_init__(self) -> None:
        flags = (
            self.supports_import,
            self.supports_return,
            self.supports_cost,
            self.supports_compensation,
        )
        money = self.supports_cost or self.supports_compensation
        if (
            any(type(flag) is not bool for flag in flags)
            or not self.supports_import
            or (self.supports_compensation and not self.supports_return)
            or (money and (self.currency is None or not re.fullmatch(r"[A-Z]{3}", self.currency)))
            or (not money and self.currency is not None)
            or self.interval_duration <= timedelta(0)
            or self.interval_duration > timedelta(days=1)
            or self.publication_delay < timedelta(0)
            or self.historical_range <= timedelta(0)
            or self.minimum_poll_interval < timedelta(hours=1)
        ):
            raise ValueError("invalid provider capabilities")


@dataclass(frozen=True, slots=True, repr=False)
class ProviderLocation:
    """A private provider location with a safe masked display label."""

    private_id: str
    masked_label: str
    time_zone: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.private_id, str)
            or not 1 <= len(self.private_id) <= 128
            or _CONTROL.search(self.private_id)
            or not isinstance(self.masked_label, str)
            or not 1 <= len(self.masked_label) <= 64
            or _CONTROL.search(self.masked_label)
            or self.private_id in self.masked_label
        ):
            raise ValueError("invalid provider location")
        if self.time_zone is not None:
            try:
                ZoneInfo(self.time_zone)
            except TypeError, ValueError, ZoneInfoNotFoundError:
                raise ValueError("invalid provider location") from None

    @property
    def display_name(self) -> str:
        """Return only the already-masked provider label."""
        return self.masked_label


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    """Public, non-secret metadata for a released provider adapter."""

    key: str
    name: str
    country_codes: frozenset[str]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.key, str)
            or _PROVIDER_KEY.fullmatch(self.key) is None
            or not isinstance(self.name, str)
            or not 1 <= len(self.name) <= 40
            or _CONTROL.search(self.name)
            or not self.country_codes
            or any(re.fullmatch(r"[A-Z]{2}", code) is None for code in self.country_codes)
        ):
            raise ValueError("invalid provider descriptor")


@dataclass(frozen=True, slots=True, repr=False)
class EnergyInterval:
    """A single absolute UTC hour of normalized usage."""

    start: datetime
    end: datetime
    import_kwh: Decimal
    return_kwh: Decimal
    amount: Decimal | None
    currency: str | None
    is_estimated: bool
    received_at: datetime
    source_revision: str | None = None
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            self.start.tzinfo is None
            or self.end.tzinfo is None
            or self.received_at.tzinfo is None
            or self.start.utcoffset() != timedelta(0)
            or self.end.utcoffset() != timedelta(0)
            or self.received_at.utcoffset() != timedelta(0)
            or self.start.minute != 0
            or self.start.second != 0
            or self.start.microsecond != 0
            or self.end - self.start != timedelta(hours=1)
            or self.import_kwh < 0
            or self.return_kwh < 0
            or not self.import_kwh.is_finite()
            or not self.return_kwh.is_finite()
            or (self.amount is not None and not self.amount.is_finite())
        ):
            raise ValueError("invalid energy interval")
        parts = (
            self.start.astimezone(UTC).isoformat(),
            self.end.astimezone(UTC).isoformat(),
            _canonical_decimal(self.import_kwh),
            _canonical_decimal(self.return_kwh),
            "" if self.amount is None else _canonical_decimal(self.amount),
            self.currency or "",
            "1" if self.is_estimated else "0",
            self.source_revision or "",
        )
        object.__setattr__(self, "fingerprint", sha256("\x1f".join(parts).encode()).hexdigest())


@dataclass(frozen=True, slots=True)
class LedgerTotals:
    """Non-negative lifetime cumulative values."""

    import_kwh: Decimal = Decimal(0)
    return_kwh: Decimal = Decimal(0)
    cost: Decimal = Decimal(0)
    compensation: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        if any(
            not value.is_finite() or value < 0
            for value in (self.import_kwh, self.return_kwh, self.cost, self.compensation)
        ):
            raise ValueError("invalid ledger totals")


@dataclass(frozen=True, slots=True, repr=False)
class LedgerState:
    """A revisioned interval ledger and statistics progress markers."""

    schema_version: int = 1
    revision: int = 0
    intervals: tuple[EnergyInterval, ...] = ()
    baseline: LedgerTotals = field(default_factory=LedgerTotals)
    backfill_cursor: datetime | None = None
    backfill_complete: bool = False
    statistics_pending_from: datetime | None = None
    statistics_pending_fingerprint: str | None = None
    statistics_verified_through: datetime | None = None
    statistics_verified_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version < 1 or self.revision < 0:
            raise ValueError("invalid ledger state")
        if tuple(sorted(self.intervals, key=lambda interval: interval.start)) != self.intervals:
            raise ValueError("unsorted ledger intervals")


@dataclass(frozen=True, slots=True, repr=False)
class LedgerMutation:
    """Result of applying a new interval window."""

    state: LedgerState
    inserted: int = 0
    corrected: int = 0
    estimated: int = 0
    earliest_statistics_hour: datetime | None = None
    deferred: bool = False
    repair: str | None = None


class Freshness(StrEnum):
    """Age of the newest utility interval."""

    FRESH = "fresh"
    DELAYED = "delayed"
    STALE = "stale"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True, repr=False)
class UsageSnapshot:
    """Validated dashboard values at a chosen local time."""

    newest_interval_start: datetime | None
    freshness: Freshness
    latest_import_kwh: Decimal | None
    latest_return_kwh: Decimal | None
    today_import_kwh: Decimal | None
    today_return_kwh: Decimal | None
    seven_day_import_kwh: Decimal | None
    seven_day_return_kwh: Decimal | None
    month_import_kwh: Decimal | None
    month_return_kwh: Decimal | None
    latest_cost: Decimal | None
    today_cost: Decimal | None
    seven_day_cost: Decimal | None
    month_cost: Decimal | None
    latest_compensation: Decimal | None
    today_compensation: Decimal | None
    seven_day_compensation: Decimal | None
    month_compensation: Decimal | None
