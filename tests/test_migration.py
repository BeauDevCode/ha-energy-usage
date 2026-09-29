"""Version-one Energy Usage recovery is local, strict, and side-effect free."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from unittest.mock import patch

import pytest
from custom_components import energy_usage as integration
from custom_components.energy_usage.const import (
    CONF_AUTH,
    CONF_LOCATION_PUBLIC_ID,
    CONF_PRIVATE_LOCATION_ID,
    CONF_PROVIDER_KEY,
    DOMAIN,
    PROVIDER_SCHEMA_VERSION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component import common  # type: ignore[import-untyped]

PUBLIC_ID = "a" * 32


def entry(hass: HomeAssistant, *, version: int = 1, data: dict[str, Any] | None = None) -> Any:
    item = common.MockConfigEntry(
        domain=DOMAIN,
        unique_id=PUBLIC_ID,
        version=version,
        minor_version=0,
        data=data
        or {
            CONF_PROVIDER_KEY: "entergy",
            CONF_AUTH: {"username": "private-user", "password": "private-password"},
            CONF_PRIVATE_LOCATION_ID: "private-location",
            CONF_LOCATION_PUBLIC_ID: PUBLIC_ID,
            "provider_schema_version": PROVIDER_SCHEMA_VERSION,
            "time_zone": "America/Chicago",
            "ledger_initialized": False,
        },
    )
    item.add_to_hass(hass)
    return item


async def test_v1_entry_recovery_is_idempotent_and_does_not_touch_registries(
    hass: HomeAssistant,
) -> None:
    item = entry(hass)
    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    with (
        patch.object(devices, "async_update_device", wraps=devices.async_update_device) as device,
        patch.object(entities, "async_update_entity", wraps=entities.async_update_entity) as entity,
    ):
        assert await integration.async_migrate_entry(hass, item)
        assert await integration.async_recover_migration(hass, item)
    device.assert_not_called()
    entity.assert_not_called()
    assert item.version == 1 and item.unique_id == PUBLIC_ID


@pytest.mark.parametrize(
    ("change", "value"),
    [
        (CONF_LOCATION_PUBLIC_ID, "private-location"),
        (CONF_LOCATION_PUBLIC_ID, "b" * 32),
        (CONF_PROVIDER_KEY, "unknown-provider"),
        ("provider_schema_version", 2),
        (CONF_AUTH, "not-a-mapping"),
        (CONF_PRIVATE_LOCATION_ID, ""),
    ],
)
async def test_malformed_v1_entry_fails_closed_without_mutation(
    hass: HomeAssistant, change: str, value: object
) -> None:
    item = entry(hass)
    hass.config_entries.async_update_entry(item, data={**item.data, change: value})
    before = dict(item.data)
    assert not await integration.async_migrate_entry(hass, item)
    assert not await integration.async_recover_migration(hass, item)
    assert item.data == before and item.version == 1


async def test_future_entry_version_is_rejected(hass: HomeAssistant) -> None:
    item = entry(hass, version=2)
    assert not await integration.async_migrate_entry(hass, item)
    assert not await integration.async_recover_migration(hass, item)


@pytest.mark.parametrize(
    "checkpoint",
    [
        {"entry_version": 2, "provider_key": "entergy", "location_public_id": PUBLIC_ID},
        {"entry_version": 1, "provider_key": "other", "location_public_id": PUBLIC_ID},
        {"entry_version": 1, "provider_key": "entergy", "location_public_id": "b" * 32},
        {"entry_version": 1},
    ],
)
async def test_malformed_or_future_same_domain_checkpoint_fails_closed(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    checkpoint: dict[str, Any],
) -> None:
    item = entry(hass)
    key = f"{DOMAIN}.migration_{item.entry_id}"
    hass_storage[key] = {"version": 1, "data": checkpoint}
    before = deepcopy(hass_storage)
    assert not await integration.async_migrate_entry(hass, item)
    assert not await integration.async_recover_migration(hass, item)
    assert hass_storage == before


async def test_recovery_ignores_old_integration_store_and_registry_data(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    item = entry(hass)
    hass_storage["entergy_mobile_usage_old-entry"] = {
        "version": 1,
        "data": {"private": "legacy-canary"},
    }
    before = deepcopy(hass_storage)
    assert await integration.async_recover_migration(hass, item)
    assert hass_storage == before
