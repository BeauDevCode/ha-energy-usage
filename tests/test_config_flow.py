"""One-provider, one-location setup and reauthentication contracts."""

from __future__ import annotations

import json
from collections.abc import Generator
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from aiohttp import ClientError
from custom_components.energy_usage.config_flow import EnergyUsageConfigFlow
from custom_components.energy_usage.const import (
    CONF_AUTH,
    CONF_LOCATION_PUBLIC_ID,
    CONF_PRIVATE_LOCATION_ID,
    CONF_PROVIDER_KEY,
    DOMAIN,
)
from custom_components.energy_usage.errors import AuthError, ChallengeError, PayloadError
from custom_components.energy_usage.models import (
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderLocation,
)
from custom_components.energy_usage.statistics import statistic_ids
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import InvalidData
from homeassistant.helpers import selector
from pytest_homeassistant_custom_component import common  # type: ignore[import-untyped]

AUTH = {
    "username": "synthetic-user",
    "password": "synthetic-password",
    "language": "en",
    "confirm_no_export": True,
}
PUBLIC = "a" * 32
LOCATION = ProviderLocation("987654321", "Account ••••4321 (Cabin)", "America/Chicago")
CAPABILITIES = ProviderCapabilities(
    supports_import=True,
    supports_return=True,
    supports_cost=True,
    supports_compensation=True,
    currency="USD",
    interval_duration=timedelta(hours=1),
    publication_delay=timedelta(hours=6),
    historical_range=timedelta(days=370),
    minimum_poll_interval=timedelta(hours=2),
)


@pytest.fixture
def provider_client() -> Generator[AsyncMock]:
    client = AsyncMock()
    client.descriptor = ProviderDescriptor("entergy", "Entergy", frozenset({"US"}))
    client.capabilities = CAPABILITIES
    client.async_list_locations.return_value = (LOCATION,)

    async def confirm(private_id: str, _budget: object) -> ProviderLocation:
        return next(
            location
            for location in client.async_list_locations.return_value
            if location.private_id == private_id
        )

    client.async_confirm_location.side_effect = confirm
    with (
        patch("custom_components.energy_usage.config_flow.create_provider", return_value=client),
        patch("custom_components.energy_usage.async_setup_entry", return_value=True),
    ):
        yield client


async def start(hass: HomeAssistant) -> ConfigFlowResult:
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})


async def authenticate(hass: HomeAssistant) -> ConfigFlowResult:
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PROVIDER_KEY: "entergy"}
    )
    assert result["step_id"] == "auth"
    return await hass.config_entries.flow.async_configure(result["flow_id"], AUTH)


def entry_data(**updates: object) -> dict[str, object]:
    data: dict[str, object] = {
        CONF_PROVIDER_KEY: "entergy",
        CONF_AUTH: dict(AUTH),
        CONF_PRIVATE_LOCATION_ID: LOCATION.private_id,
        CONF_LOCATION_PUBLIC_ID: PUBLIC,
        "time_zone": "America/Chicago",
        "provider_schema_version": 1,
        "ledger_initialized": True,
    }
    data.update(updates)
    return data


async def test_user_step_lists_only_released_providers(hass: HomeAssistant) -> None:
    result = await start(hass)
    assert result["type"] == "form" and result["step_id"] == "user"
    schema = result["data_schema"]
    assert schema is not None
    field = next(iter(schema.schema.values()))
    assert isinstance(field, selector.SelectSelector)
    assert field.config["options"] == [{"value": "entergy", "label": "Entergy"}]


async def test_unknown_provider_aborts_without_authentication(hass: HomeAssistant) -> None:
    flow = EnergyUsageConfigFlow()
    flow.hass = hass
    result = await flow.async_step_user({CONF_PROVIDER_KEY: "private-canary"})
    assert result["type"] == "abort"
    assert result["reason"] == "unsupported_provider"
    assert "private-canary" not in repr(result)


async def test_single_entry_blocks_second_location(hass: HomeAssistant) -> None:
    common.MockConfigEntry(domain=DOMAIN, unique_id=PUBLIC, data=entry_data()).add_to_hass(hass)
    result = await start(hass)
    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"


def test_password_selector_and_disclosure() -> None:
    from custom_components.energy_usage.config_flow import _provider_auth_schema

    schema = _provider_auth_schema("entergy").schema
    password = next(value for key, value in schema.items() if key.schema == "password")
    assert isinstance(password, selector.TextSelector)
    assert password.config["type"] == selector.TextSelectorType.PASSWORD
    assert password.config["autocomplete"] == "current-password"
    confirmation = next(value for key, value in schema.items() if key.schema == "confirm_no_export")
    assert isinstance(confirmation, selector.BooleanSelector)
    strings = json.loads(Path("custom_components/energy_usage/strings.json").read_text())
    for step in ("auth", "reauth_confirm"):
        description = strings["config"]["step"][step]["description"].lower()
        assert "password" in description and "stored" in description


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (AuthError(), "invalid_auth"),
        (ChallengeError(), "unsupported_challenge"),
        (ValueError(), "invalid_location"),
        (PayloadError(), "cannot_connect"),
        (ClientError(), "cannot_connect"),
        (RuntimeError("private-canary"), "unknown"),
    ],
)
async def test_auth_errors_logout_without_leaking(
    hass: HomeAssistant,
    provider_client: AsyncMock,
    error: Exception,
    reason: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider_client.authenticate.side_effect = error
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PROVIDER_KEY: "entergy"}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], AUTH)
    assert result["step_id"] == "auth"
    assert result["errors"] == {"base": reason}
    assert "private-canary" not in caplog.text
    provider_client.async_logout.assert_awaited_once()


async def test_zero_locations_returns_visible_error(
    hass: HomeAssistant, provider_client: AsyncMock
) -> None:
    provider_client.async_list_locations.return_value = ()
    result = await authenticate(hass)
    assert result["step_id"] == "auth"
    assert result["errors"] == {"base": "no_locations"}
    provider_client.async_logout.assert_awaited_once()


async def test_unconfirmed_no_export_shows_field_error(hass: HomeAssistant) -> None:
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PROVIDER_KEY: "entergy"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**AUTH, "confirm_no_export": False}
    )
    assert result["step_id"] == "auth"
    assert result["errors"] == {"confirm_no_export": "no_export_confirmation_required"}
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_one_location_still_requires_explicit_review(
    hass: HomeAssistant, provider_client: AsyncMock
) -> None:
    result = await authenticate(hass)
    assert result["type"] == "form" and result["step_id"] == "location"
    options = next(iter(result["data_schema"].schema.values())).config["options"]
    assert options == [{"value": "0", "label": LOCATION.display_name}]
    assert LOCATION.private_id not in str(result)
    provider_client.async_logout.assert_awaited_once()


async def test_multiple_locations_allow_exactly_one_selection(
    hass: HomeAssistant, provider_client: AsyncMock
) -> None:
    second = ProviderLocation("123450000", "Account ••••0000", "America/New_York")
    provider_client.async_list_locations.return_value = (LOCATION, second)
    result = await authenticate(hass)
    options = next(iter(result["data_schema"].schema.values())).config["options"]
    assert [item["value"] for item in options] == ["0", "1"]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"location": "1"})
    assert result["type"] == "create_entry"
    assert result["result"].data[CONF_PRIVATE_LOCATION_ID] == second.private_id


async def test_forged_location_selection_aborts(
    hass: HomeAssistant, provider_client: AsyncMock
) -> None:
    result = await authenticate(hass)
    with pytest.raises(InvalidData) as error:
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {"location": "private-canary"}
        )
    assert "private-canary" not in str(error.value)
    assert not hass.config_entries.async_entries(DOMAIN)


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (ChallengeError(), "unsupported_challenge"),
        (AuthError(), "invalid_auth"),
        (ValueError(), "invalid_location"),
        (PayloadError(), "cannot_connect"),
        (ClientError(), "cannot_connect"),
        (RuntimeError("private-canary"), "unknown"),
    ],
)
async def test_location_confirmation_errors_abort_without_leaking(
    hass: HomeAssistant,
    provider_client: AsyncMock,
    error: Exception,
    reason: str,
) -> None:
    result = await authenticate(hass)
    provider_client.async_confirm_location.side_effect = error
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"location": "0"})
    assert result["type"] == "abort" and result["reason"] == reason
    assert "private-canary" not in repr(result)


async def test_location_confirmation_must_preserve_private_identity(
    hass: HomeAssistant, provider_client: AsyncMock
) -> None:
    result = await authenticate(hass)
    provider_client.async_confirm_location.side_effect = None
    provider_client.async_confirm_location.return_value = ProviderLocation(
        "different-location", "Account ••••0000", "America/Chicago"
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"location": "0"})
    assert result["type"] == "abort" and result["reason"] == "invalid_location"


async def test_adapter_location_is_defensively_revalidated(
    hass: HomeAssistant, provider_client: AsyncMock
) -> None:
    provider_client.async_list_locations.return_value = (
        cast(
            ProviderLocation,
            SimpleNamespace(
                private_id="private-canary", display_name="Unsafe\nLocation", time_zone="UTC"
            ),
        ),
    )
    result = await authenticate(hass)
    assert result["step_id"] == "auth"
    assert result["errors"] == {"base": "invalid_location"}
    assert "private-canary" not in repr(result)


async def test_create_stable_private_identity(
    hass: HomeAssistant, provider_client: AsyncMock
) -> None:
    result = await authenticate(hass)
    with patch(
        "custom_components.energy_usage.config_flow.uuid4", wraps=__import__("uuid").uuid4
    ) as uuid:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"location": "0"}
        )
        uuid.assert_called_once()
    assert result["type"] == "create_entry"
    entry = result["result"]
    public_id = entry.data[CONF_LOCATION_PUBLIC_ID]
    assert UUID(entry.unique_id).hex == public_id
    statistic_ids(public_id)
    assert entry.title == "Energy Usage · Entergy · Account ••••4321 (Cabin)"
    assert entry.data == {
        CONF_PROVIDER_KEY: "entergy",
        CONF_AUTH: AUTH,
        CONF_PRIVATE_LOCATION_ID: LOCATION.private_id,
        CONF_LOCATION_PUBLIC_ID: public_id,
        "time_zone": "America/Chicago",
        "provider_schema_version": 1,
        "ledger_initialized": False,
    }
    assert entry.version == 1
    assert entry.options["scan_interval_seconds"] == 14400


async def test_missing_timezone_requires_visible_valid_selection(
    hass: HomeAssistant, provider_client: AsyncMock
) -> None:
    missing = ProviderLocation("987654321", "Account ••••4321", None)
    provider_client.async_list_locations.return_value = (missing,)
    provider_client.async_confirm_location.return_value = missing
    hass.config.time_zone = "America/New_York"
    result = await authenticate(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"location": "0"})
    assert result["step_id"] == "time_zone"
    assert result["data_schema"]({}) == {"time_zone": "America/New_York"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"time_zone": "America/Denver"}
    )
    assert result["type"] == "create_entry"
    assert result["result"].data["time_zone"] == "America/Denver"


async def test_invalid_timezone_is_value_free(
    hass: HomeAssistant, provider_client: AsyncMock
) -> None:
    missing = ProviderLocation("987654321", "Account ••••4321", None)
    provider_client.async_list_locations.return_value = (missing,)
    provider_client.async_confirm_location.return_value = missing
    result = await authenticate(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"location": "0"})
    with pytest.raises(InvalidData) as error:
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {"time_zone": "private-canary/NotAZone"}
        )
    assert "private-canary" not in str(error.value)


@pytest.mark.parametrize("location_available", [True, False])
async def test_reauth_preserves_identity_and_requires_same_location(
    hass: HomeAssistant,
    provider_client: AsyncMock,
    location_available: bool,
) -> None:
    entry = common.MockConfigEntry(domain=DOMAIN, unique_id=PUBLIC, version=1, data=entry_data())
    entry.add_to_hass(hass)
    before = dict(entry.data)
    provider_client.async_list_locations.return_value = (LOCATION,) if location_available else ()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id}, data=before
    )
    with patch.object(hass.config_entries, "async_reload", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**AUTH, "username": "new-user", "password": "new-password"},
        )
        await hass.async_block_till_done()
    assert result["reason"] == ("reauth_successful" if location_available else "location_mismatch")
    if location_available:
        assert entry.data == {
            **before,
            CONF_AUTH: {**AUTH, "username": "new-user", "password": "new-password"},
        }
    else:
        assert entry.data == before
    assert entry.unique_id == PUBLIC
    assert entry.title == "Mock Title"
    provider_client.async_logout.assert_awaited_once()


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (ChallengeError(), "unsupported_challenge"),
        (AuthError(), "invalid_auth"),
        (ValueError(), "invalid_location"),
        (PayloadError(), "cannot_connect"),
        (ClientError(), "cannot_connect"),
        (RuntimeError("private-canary"), "unknown"),
    ],
)
async def test_reauth_errors_preserve_existing_credentials(
    hass: HomeAssistant,
    provider_client: AsyncMock,
    error: Exception,
    reason: str,
) -> None:
    entry = common.MockConfigEntry(domain=DOMAIN, unique_id=PUBLIC, version=1, data=entry_data())
    entry.add_to_hass(hass)
    before = dict(entry.data)
    provider_client.authenticate.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=before,
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], AUTH)
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": reason}
    assert entry.data == before
    assert "private-canary" not in repr(result)


async def test_reauth_unconfirmed_no_export_preserves_credentials(hass: HomeAssistant) -> None:
    entry = common.MockConfigEntry(domain=DOMAIN, unique_id=PUBLIC, version=1, data=entry_data())
    entry.add_to_hass(hass)
    before = dict(entry.data)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=before,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**AUTH, "confirm_no_export": False}
    )
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"confirm_no_export": "no_export_confirmation_required"}
    assert entry.data == before


@pytest.mark.parametrize(("old", "expected"), [(None, 14400), (60, 7200), (10800, 10800)])
async def test_options_clamp_to_provider_minimum_and_reload_once(
    hass: HomeAssistant,
    provider_client: AsyncMock,
    old: int | None,
    expected: int,
) -> None:
    entry = common.MockConfigEntry(
        domain=DOMAIN,
        data=entry_data(),
        options={} if old is None else {"scan_interval_seconds": old},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["data_schema"]({})["scan_interval_seconds"] == expected
    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"scan_interval_seconds": 7200}
        )
        await hass.async_block_till_done()
    assert entry.options["scan_interval_seconds"] == 7200
    reload.assert_awaited_once()
