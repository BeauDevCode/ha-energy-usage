"""Entergy adapter conformance at the provider-neutral boundary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast
from unittest.mock import AsyncMock

import aiohttp
import pytest
from custom_components.energy_usage.errors import ChallengeError, PolicyError
from custom_components.energy_usage.models import Account, EnergyInterval, ProviderLocation
from custom_components.energy_usage.provider import IntervalRequest, RequestBudget
from custom_components.energy_usage.providers.entergy import (
    ENTERGY_DESCRIPTOR,
    ENTERGY_FACTORY,
    EntergyProvider,
)


def adapter() -> EntergyProvider:
    result = EntergyProvider(
        cast(aiohttp.ClientSession, object()),
        {"username": "private-user", "password": "private-password", "language": "en"},
    )
    result._client = AsyncMock()
    return result


def test_descriptor_and_capabilities_are_explicit() -> None:
    assert ENTERGY_DESCRIPTOR.key == "entergy"
    assert ENTERGY_DESCRIPTOR.name == "Entergy"
    assert ENTERGY_DESCRIPTOR.country_codes == frozenset({"US"})
    capabilities = adapter().capabilities
    assert capabilities.supports_import
    assert capabilities.supports_return
    assert capabilities.supports_cost
    assert capabilities.supports_compensation
    assert capabilities.currency == "USD"
    assert capabilities.minimum_poll_interval == timedelta(hours=1)


async def test_authenticate_and_logout_use_one_shared_budget() -> None:
    result = adapter()
    budget = RequestBudget()
    await result.authenticate(budget)
    result._client.async_initialize.assert_awaited_once_with(budget)
    result._client.async_login.assert_awaited_once_with(budget)
    await result.async_logout(budget)
    result._client.async_logout.assert_awaited_once_with(budget)


async def test_locations_are_masked_and_confirmed() -> None:
    result = adapter()
    result._client.async_get_accounts.return_value = (
        Account("0001234567", "Home", "America/Chicago"),
        Account("0009876543", None, None),
    )
    locations = await result.async_list_locations(RequestBudget())
    assert [item.display_name for item in locations] == [
        "Account ••••4567 (Home)",
        "Account ••••6543",
    ]
    assert all(isinstance(item, ProviderLocation) for item in locations)
    result._client.async_get_account.return_value = Account("0001234567", "Home", "America/Chicago")
    confirmed = await result.async_confirm_location("0001234567", RequestBudget())
    assert confirmed.display_name == "Account ••••4567 (Home)"


async def test_fetch_maps_weekly_usage_to_complete_interval_page() -> None:
    result = adapter()
    result._client.async_get_account.return_value = Account("0001234567", "Home", "America/Chicago")
    await result.async_confirm_location("0001234567", RequestBudget())
    start = datetime(2026, 9, 1, tzinfo=UTC)
    interval = EnergyInterval(
        start=start,
        end=start + timedelta(hours=1),
        import_kwh=Decimal("1"),
        return_kwh=Decimal("0"),
        amount=None,
        currency=None,
        is_estimated=False,
        received_at=start,
    )
    result._client.async_get_weekly_usage.return_value = (interval,)
    request = IntervalRequest("0001234567", start, start + timedelta(days=7))
    page = await result.async_fetch_intervals(request, RequestBudget())
    assert page.intervals == (interval,)
    assert page.complete
    assert page.next_cursor is None


async def test_challenge_error_never_echoes_auth_values() -> None:
    result = adapter()
    result._client.async_login.side_effect = ChallengeError()
    with pytest.raises(ChallengeError) as error:
        await result.authenticate(RequestBudget())
    rendered = f"{error.value!s} {error.value!r}"
    assert "private-user" not in rendered
    assert "private-password" not in rendered


@pytest.mark.parametrize(
    "auth",
    [
        {},
        {"username": "", "password": "private-password"},
        {"username": "private-user", "password": ""},
        {"username": "private-user", "password": "private-password", "language": "fr"},
    ],
)
def test_adapter_rejects_incomplete_or_unsupported_auth(auth: dict[str, str]) -> None:
    with pytest.raises(PolicyError):
        EntergyProvider(cast(aiohttp.ClientSession, object()), auth)


async def test_adapter_rejects_unconfirmed_cursor_and_invalid_week() -> None:
    result = adapter()
    start = datetime(2026, 9, 1, tzinfo=UTC)
    with pytest.raises(PolicyError):
        await result.async_fetch_intervals(
            IntervalRequest("0001234567", start, start + timedelta(days=7)),
            RequestBudget(),
        )

    result._client.async_get_account.return_value = Account("0001234567", None, "UTC")
    await result.async_confirm_location("0001234567", RequestBudget())
    with pytest.raises(PolicyError):
        await result.async_fetch_intervals(
            IntervalRequest(
                "0001234567",
                start,
                start + timedelta(days=7),
                cursor="next",
            ),
            RequestBudget(),
        )
    with pytest.raises(PolicyError):
        await result.async_fetch_intervals(
            IntervalRequest("0001234567", start, start + timedelta(days=8)),
            RequestBudget(),
        )


def test_registered_factory_builds_the_reviewed_adapter() -> None:
    result = ENTERGY_FACTORY.create(
        cast(aiohttp.ClientSession, object()),
        {"username": "private-user", "password": "private-password"},
    )
    assert isinstance(result, EntergyProvider)
