"""Provider-neutral local setup, one-location selection, and reauthentication."""

from __future__ import annotations

from contextlib import suppress
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from aiohttp import ClientError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_TIME_ZONE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_AUTH,
    CONF_LOCATION_PUBLIC_ID,
    CONF_NO_EXPORT,
    CONF_PRIVATE_LOCATION_ID,
    CONF_PROVIDER_KEY,
    CONF_SCAN_INTERVAL_SECONDS,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    MAX_SCAN_INTERVAL_SECONDS,
    MIN_SCAN_INTERVAL_SECONDS,
    PROVIDER_SCHEMA_VERSION,
)
from .errors import AuthError, ChallengeError, EnergyUsageError, NoExportConfirmationError
from .models import ProviderDescriptor, ProviderLocation
from .provider import (
    RequestBudget,
    create_provider,
    provider_auth_schema,
    provider_descriptors,
)
from .statistics import statistic_ids

CONF_LOCATION = "location"


def _provider_options() -> list[selector.SelectOptionDict]:
    return [
        {"value": descriptor.key, "label": descriptor.name}
        for descriptor in provider_descriptors()
        if "US" in descriptor.country_codes
    ]


def _provider_descriptor(key: str) -> ProviderDescriptor | None:
    return next((item for item in provider_descriptors() if item.key == key), None)


def _provider_auth_schema(key: str) -> vol.Schema:
    """Return a fresh provider-owned credential schema for the local UI."""
    return provider_auth_schema(key)


def _safe_locations(value: object) -> tuple[ProviderLocation, ...]:
    if not isinstance(value, tuple) or any(
        not isinstance(location, ProviderLocation) for location in value
    ):
        raise ValueError
    return value


async def _async_logout(provider: Any, budget: RequestBudget) -> None:
    with suppress(Exception):
        await provider.async_logout(budget)


async def _async_locations(
    hass: HomeAssistant, provider_key: str, auth: dict[str, Any]
) -> tuple[ProviderLocation, ...]:
    provider = create_provider(provider_key, async_get_clientsession(hass), auth)
    budget = RequestBudget()
    try:
        await provider.authenticate(budget)
        return _safe_locations(await provider.async_list_locations(budget))
    finally:
        await _async_logout(provider, budget)


async def _async_confirm_location(
    hass: HomeAssistant,
    provider_key: str,
    auth: dict[str, Any],
    expected: ProviderLocation,
) -> ProviderLocation:
    provider = create_provider(provider_key, async_get_clientsession(hass), auth)
    budget = RequestBudget()
    try:
        await provider.authenticate(budget)
        confirmed = await provider.async_confirm_location(expected.private_id, budget)
        if (
            not isinstance(confirmed, ProviderLocation)
            or confirmed.private_id != expected.private_id
        ):
            raise ValueError
        return confirmed
    finally:
        await _async_logout(provider, budget)


class EnergyUsageConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure one reviewed provider and one selected service location."""

    VERSION = 1
    MINOR_VERSION = 0

    def __init__(self) -> None:
        self._provider_key: str | None = None
        self._auth: dict[str, Any] = {}
        self._locations: tuple[ProviderLocation, ...] = ()
        self._selected_location: ProviderLocation | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        options = _provider_options()
        if user_input is not None:
            key = user_input.get(CONF_PROVIDER_KEY)
            if not isinstance(key, str) or key not in {item["value"] for item in options}:
                return self.async_abort(reason="unsupported_provider")
            self._provider_key = key
            return await self.async_step_auth()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PROVIDER_KEY): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options, mode=selector.SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
        )

    async def async_step_auth(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        provider_key = self._provider_key
        if provider_key is None or _provider_descriptor(provider_key) is None:
            return self.async_abort(reason="unsupported_provider")
        errors: dict[str, str] = {}
        if user_input is not None:
            auth = dict(user_input)
            try:
                locations = await _async_locations(self.hass, provider_key, auth)
                if not locations:
                    errors["base"] = "no_locations"
                else:
                    self._auth = auth
                    self._locations = locations
                    return await self.async_step_location()
            except ChallengeError:
                errors["base"] = "unsupported_challenge"
            except AuthError:
                errors["base"] = "invalid_auth"
            except ValueError:
                errors["base"] = "invalid_location"
            except NoExportConfirmationError:
                errors[CONF_NO_EXPORT] = "no_export_confirmation_required"
            except EnergyUsageError, ClientError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
        return self.async_show_form(
            step_id="auth", data_schema=_provider_auth_schema(provider_key), errors=errors
        )

    async def async_step_location(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        provider_key = self._provider_key
        if provider_key is None or not self._auth or not self._locations:
            return await self.async_step_user()
        choices: list[selector.SelectOptionDict] = [
            {"value": str(index), "label": location.display_name}
            for index, location in enumerate(self._locations)
        ]
        if user_input is not None:
            selection = user_input.get(CONF_LOCATION)
            if selection not in {choice["value"] for choice in choices}:
                return self.async_abort(reason="invalid_location")
            expected = self._locations[int(selection)]
            try:
                confirmed = await _async_confirm_location(
                    self.hass, provider_key, self._auth, expected
                )
            except ChallengeError:
                return self.async_abort(reason="unsupported_challenge")
            except AuthError:
                return self.async_abort(reason="invalid_auth")
            except ValueError:
                return self.async_abort(reason="invalid_location")
            except EnergyUsageError, ClientError:
                return self.async_abort(reason="cannot_connect")
            except Exception:
                return self.async_abort(reason="unknown")
            self._selected_location = confirmed
            if confirmed.time_zone is None:
                return await self.async_step_time_zone()
            return await self._create_location_entry(confirmed.time_zone)
        return self.async_show_form(
            step_id="location",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LOCATION): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=choices, mode=selector.SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
        )

    async def async_step_time_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._selected_location is None:
            return await self.async_step_user()
        errors: dict[str, str] = {}
        if user_input is not None:
            time_zone = user_input.get(CONF_TIME_ZONE, self.hass.config.time_zone)
            try:
                ZoneInfo(time_zone)
            except TypeError, ValueError, ZoneInfoNotFoundError:
                errors[CONF_TIME_ZONE] = "invalid_time_zone"
            else:
                return await self._create_location_entry(time_zone)
        time_zones = await self.hass.async_add_executor_job(available_timezones)
        return self.async_show_form(
            step_id="time_zone",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TIME_ZONE, default=self.hass.config.time_zone
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=sorted(time_zones),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def _create_location_entry(self, time_zone: str) -> ConfigFlowResult:
        location = self._selected_location
        provider_key = self._provider_key
        if location is None or provider_key is None:
            return await self.async_step_user()
        descriptor = _provider_descriptor(provider_key)
        if descriptor is None:
            return self.async_abort(reason="unsupported_provider")
        public_id = uuid4().hex
        statistic_ids(public_id)
        await self.async_set_unique_id(public_id)
        return self.async_create_entry(
            title=f"Energy Usage · {descriptor.name} · {location.display_name}",
            data={
                CONF_PROVIDER_KEY: provider_key,
                CONF_AUTH: dict(self._auth),
                CONF_PRIVATE_LOCATION_ID: location.private_id,
                CONF_LOCATION_PUBLIC_ID: public_id,
                CONF_TIME_ZONE: time_zone,
                "provider_schema_version": PROVIDER_SCHEMA_VERSION,
                "ledger_initialized": False,
            },
            options={CONF_SCAN_INTERVAL_SECONDS: DEFAULT_SCAN_INTERVAL_SECONDS},
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        provider_key = entry.data.get(CONF_PROVIDER_KEY)
        if not isinstance(provider_key, str) or _provider_descriptor(provider_key) is None:
            return self.async_abort(reason="unsupported_provider")
        self._provider_key = provider_key
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        provider_key = self._provider_key
        if provider_key is None:
            return self.async_abort(reason="unsupported_provider")
        errors: dict[str, str] = {}
        if user_input is not None:
            auth = dict(user_input)
            try:
                locations = await _async_locations(self.hass, provider_key, auth)
            except ChallengeError:
                errors["base"] = "unsupported_challenge"
            except AuthError:
                errors["base"] = "invalid_auth"
            except ValueError:
                errors["base"] = "invalid_location"
            except NoExportConfirmationError:
                errors[CONF_NO_EXPORT] = "no_export_confirmation_required"
            except EnergyUsageError, ClientError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                private_id = entry.data.get(CONF_PRIVATE_LOCATION_ID)
                if not any(location.private_id == private_id for location in locations):
                    return self.async_abort(reason="location_mismatch")
                public_id = entry.data.get(CONF_LOCATION_PUBLIC_ID)
                if not isinstance(public_id, str):
                    return self.async_abort(reason="location_mismatch")
                await self.async_set_unique_id(public_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(entry, data_updates={CONF_AUTH: auth})
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_provider_auth_schema(provider_key),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> EnergyUsageOptionsFlow:
        return EnergyUsageOptionsFlow()


class EnergyUsageOptionsFlow(OptionsFlowWithReload):
    """Bound polling to common and provider-specific safe minimums."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        minimum = MIN_SCAN_INTERVAL_SECONDS
        provider_key = self.config_entry.data.get(CONF_PROVIDER_KEY)
        auth = self.config_entry.data.get(CONF_AUTH)
        if isinstance(provider_key, str) and isinstance(auth, dict):
            with suppress(Exception):
                provider = create_provider(provider_key, async_get_clientsession(self.hass), auth)
                minimum = max(
                    minimum, int(provider.capabilities.minimum_poll_interval.total_seconds())
                )
        interval = max(
            minimum,
            min(
                MAX_SCAN_INTERVAL_SECONDS,
                int(
                    self.config_entry.options.get(
                        CONF_SCAN_INTERVAL_SECONDS, DEFAULT_SCAN_INTERVAL_SECONDS
                    )
                ),
            ),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SCAN_INTERVAL_SECONDS, default=interval): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=minimum, max=MAX_SCAN_INTERVAL_SECONDS),
                    )
                }
            ),
        )
