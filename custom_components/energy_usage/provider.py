"""Provider-neutral adapter protocol, registry, and request budget."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

import voluptuous as vol
from aiohttp import ClientSession

from .errors import PolicyError, UnknownProviderError
from .models import EnergyInterval, ProviderCapabilities, ProviderDescriptor, ProviderLocation


@dataclass(slots=True)
class RequestBudget:
    """Bound all nested calls in one provider request chain."""

    limit: int = 12
    used: int = 0

    def __post_init__(self) -> None:
        if (
            type(self.limit) is not int
            or self.limit < 0
            or type(self.used) is not int
            or not 0 <= self.used <= min(self.limit, 12)
        ):
            raise PolicyError from None

    def consume(self) -> None:
        """Reserve one network attempt before touching a provider session."""
        if self.used >= min(self.limit, 12):
            raise PolicyError from None
        self.used += 1


@dataclass(frozen=True, slots=True, repr=False)
class IntervalRequest:
    """A bounded private-location interval request."""

    private_location_id: str
    start: datetime
    end: datetime
    cursor: str | None = None

    def __post_init__(self) -> None:
        if (
            not self.private_location_id
            or self.start.tzinfo is None
            or self.end.tzinfo is None
            or self.start >= self.end
            or self.cursor is not None
            and (not self.cursor or len(self.cursor) > 256)
        ):
            raise ValueError("invalid interval request")


@dataclass(frozen=True, slots=True, repr=False)
class IntervalPage:
    """One normalized provider response page."""

    intervals: tuple[EnergyInterval, ...]
    next_cursor: str | None = None
    complete: bool = True

    def __post_init__(self) -> None:
        if (
            tuple(sorted(self.intervals, key=lambda interval: interval.start)) != self.intervals
            or type(self.complete) is not bool
            or self.next_cursor is not None
            and (not self.next_cursor or len(self.next_cursor) > 256)
            or self.complete
            and self.next_cursor is not None
        ):
            raise ValueError("invalid interval page")


class EnergyProvider(Protocol):
    """Runtime contract implemented by every reviewed provider adapter."""

    descriptor: ProviderDescriptor
    capabilities: ProviderCapabilities

    async def authenticate(self, budget: RequestBudget) -> None: ...

    async def async_list_locations(self, budget: RequestBudget) -> tuple[ProviderLocation, ...]: ...

    async def async_confirm_location(
        self, private_location_id: str, budget: RequestBudget
    ) -> ProviderLocation: ...

    async def async_fetch_intervals(
        self, request: IntervalRequest, budget: RequestBudget
    ) -> IntervalPage: ...

    async def async_logout(self, budget: RequestBudget) -> None: ...


@dataclass(frozen=True, slots=True)
class ProviderFactory:
    """Safe public metadata plus private runtime construction hooks."""

    descriptor: ProviderDescriptor
    auth_schema: Callable[[], vol.Schema]
    create: Callable[[ClientSession, Mapping[str, Any]], EnergyProvider]


_PROVIDERS: dict[str, ProviderFactory] = {}


def register_provider(factory: ProviderFactory) -> None:
    """Register one reviewed provider factory exactly once."""
    key = factory.descriptor.key
    if key in _PROVIDERS:
        raise ValueError("duplicate provider")
    _PROVIDERS[key] = factory


def provider_descriptors() -> tuple[ProviderDescriptor, ...]:
    """Return safe metadata in deterministic user-facing order."""
    return tuple(
        factory.descriptor
        for factory in sorted(
            _PROVIDERS.values(), key=lambda item: (item.descriptor.name, item.descriptor.key)
        )
    )


def _factory(key: str) -> ProviderFactory:
    try:
        return _PROVIDERS[key]
    except KeyError, TypeError:
        raise UnknownProviderError from None


def provider_auth_schema(key: str) -> vol.Schema:
    """Build a fresh provider-owned local credential schema."""
    return _factory(key).auth_schema()


def create_provider(key: str, session: ClientSession, auth: Mapping[str, Any]) -> EnergyProvider:
    """Create a provider client without exposing the auth mapping."""
    return _factory(key).create(session, auth)
