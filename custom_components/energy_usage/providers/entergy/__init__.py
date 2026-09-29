"""Entergy provider adapter."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import timedelta
from typing import Any

import voluptuous as vol
from aiohttp import ClientSession
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector

from ...errors import PolicyError
from ...models import (
    Account,
    Credentials,
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderLocation,
)
from ...provider import (
    IntervalPage,
    IntervalRequest,
    ProviderFactory,
    RequestBudget,
)
from .api import EntergyApiClient
from .const import DEFAULT_LANGUAGE

CONF_LANGUAGE = "language"
ENTERGY_DESCRIPTOR = ProviderDescriptor(
    key="entergy", name="Entergy", country_codes=frozenset({"US"})
)
ENTERGY_CAPABILITIES = ProviderCapabilities(
    supports_import=True,
    supports_return=True,
    supports_cost=True,
    supports_compensation=True,
    currency="USD",
    interval_duration=timedelta(hours=1),
    publication_delay=timedelta(hours=6),
    historical_range=timedelta(days=370),
    minimum_poll_interval=timedelta(hours=1),
)
_SAFE_NICKNAME = re.compile(r"[^\d\r\n\v\f\x85\u2028\u2029,@]{1,40}\Z")


def _auth_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.PASSWORD,
                    autocomplete="current-password",
                )
            ),
            vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["en", "es"], mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
        }
    )


def _location(account: Account) -> ProviderLocation:
    label = f"Account ••••{account.account_id[-4:]}"
    nickname = (account.nickname or "").strip()
    if _SAFE_NICKNAME.fullmatch(nickname):
        label += f" ({nickname})"
    return ProviderLocation(account.account_id, label, account.time_zone)


class EntergyProvider:
    """Adapt the reviewed Entergy client to the common provider contract."""

    descriptor = ENTERGY_DESCRIPTOR
    capabilities = ENTERGY_CAPABILITIES

    def __init__(self, session: ClientSession, auth: Mapping[str, Any]) -> None:
        try:
            username = auth[CONF_USERNAME]
            password = auth[CONF_PASSWORD]
            language = auth.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)
        except KeyError, TypeError:
            raise PolicyError from None
        if (
            not isinstance(username, str)
            or not username
            or not isinstance(password, str)
            or not password
            or language not in {"en", "es"}
        ):
            raise PolicyError from None
        self._client = EntergyApiClient(session, Credentials(username, password), language=language)

    async def authenticate(self, budget: RequestBudget) -> None:
        await self._client.async_initialize(budget)
        await self._client.async_login(budget)

    async def async_list_locations(self, budget: RequestBudget) -> tuple[ProviderLocation, ...]:
        return tuple(
            _location(account) for account in await self._client.async_get_accounts(budget)
        )

    async def async_confirm_location(
        self, private_location_id: str, budget: RequestBudget
    ) -> ProviderLocation:
        return _location(await self._client.async_get_account(private_location_id, budget))

    async def async_fetch_intervals(
        self, request: IntervalRequest, budget: RequestBudget
    ) -> IntervalPage:
        if request.end - request.start > timedelta(days=7) or request.cursor is not None:
            raise PolicyError from None
        intervals = await self._client.async_get_weekly_usage(
            request.private_location_id, request.start.date(), budget
        )
        return IntervalPage(intervals=intervals)

    async def async_logout(self, budget: RequestBudget) -> None:
        await self._client.async_logout(budget)

    # Temporary bridge for the existing coordinator. Task 6 replaces these
    # provider-specific calls with async_confirm_location/async_fetch_intervals.
    @property
    def authenticated(self) -> bool:
        return self._client.authenticated

    def clear_token(self) -> None:
        self._client.clear_token()

    async def async_get_account(self, private_location_id: str, budget: RequestBudget) -> Account:
        return await self._client.async_get_account(private_location_id, budget)

    async def async_get_weekly_usage(
        self,
        private_location_id: str,
        start: Any,
        budget: RequestBudget,
        *,
        fallback_time_zone: str,
    ) -> tuple[Any, ...]:
        return await self._client.async_get_weekly_usage(
            private_location_id,
            start,
            budget,
            fallback_time_zone=fallback_time_zone,
        )


def _create(session: ClientSession, auth: Mapping[str, Any]) -> EntergyProvider:
    return EntergyProvider(session, auth)


ENTERGY_FACTORY = ProviderFactory(
    descriptor=ENTERGY_DESCRIPTOR, auth_schema=_auth_schema, create=_create
)

__all__ = ["ENTERGY_DESCRIPTOR", "ENTERGY_FACTORY", "EntergyProvider"]
