"""Strict allowlist diagnostics."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, patch

from custom_components.energy_usage import EnergyUsageRuntimeData
from custom_components.energy_usage.diagnostics import async_get_config_entry_diagnostics
from custom_components.energy_usage.models import ProviderCapabilities, ProviderDescriptor
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component import common  # type: ignore[import-untyped]

PUBLIC_ID = "a" * 32
EXPECTED = {
    "integration_version",
    "home_assistant_version",
    "provider_key",
    "location_public_id",
    "provider_schema_version",
    "ledger_schema_version",
    "supports_import",
    "supports_return",
    "supports_cost",
    "supports_compensation",
    "provider_currency",
    "interval_seconds",
    "publication_delay_seconds",
    "historical_range_days",
    "minimum_poll_seconds",
    "configured_poll_seconds",
    "next_poll_seconds",
    "last_successful_fetch",
    "newest_interval",
    "error_category",
    "retained_interval_count",
    "estimated_interval_count",
    "last_inserted_count",
    "last_corrected_count",
    "freshness",
    "backfill_pages_completed",
    "backfill_pages_total",
    "backfill_complete",
}


def provider() -> SimpleNamespace:
    return SimpleNamespace(
        descriptor=ProviderDescriptor("example", "Example Utility", frozenset({"US"})),
        capabilities=ProviderCapabilities(
            supports_import=True,
            supports_return=True,
            supports_cost=True,
            supports_compensation=True,
            currency="USD",
            interval_duration=timedelta(hours=1),
            publication_delay=timedelta(hours=6),
            historical_range=timedelta(days=370),
            minimum_poll_interval=timedelta(hours=1),
        ),
    )


async def test_diagnostics_exact_allowlist_is_fresh_json_and_excludes_canaries(
    hass: HomeAssistant,
) -> None:
    canary = "private-canary-value"
    entry = common.MockConfigEntry(
        domain="energy_usage",
        title=canary,
        unique_id=PUBLIC_ID,
        version=99,
        data={"username": canary, "password": canary, "account_id": canary},
        options={"private_option": canary},
    )
    entry.add_to_hass(hass)
    safe = {
        "configured_poll_seconds": 14_400,
        "next_poll_seconds": 3600,
        "last_successful_fetch": "2026-09-28T12:00:00+00:00",
        "newest_interval": "2026-09-28T10:00:00+00:00",
        "error_category": "transient",
        "retained_interval_count": 12,
        "estimated_interval_count": 2,
        "last_inserted_count": 1,
        "last_corrected_count": 3,
        "freshness": "delayed",
        "backfill_pages_completed": 4,
        "backfill_pages_total": 53,
        "backfill_complete": False,
        "backfill_progress_percent": 7,
        "repair_conditions": ["schema_drift"],
        "unapproved": canary,
    }
    coordinator = SimpleNamespace(
        diagnostics=lambda: dict(safe),
        data={"payload": canary},
        last_exception=RuntimeError(canary),
    )
    private_provider = provider()
    private_provider.private_location_id = canary
    private_provider.nickname = canary
    private_provider.address = canary
    private_provider.raw_payload = {canary: canary}
    entry.runtime_data = EnergyUsageRuntimeData(
        cast(Any, private_provider),
        cast(Any, SimpleNamespace(raw=canary, state=SimpleNamespace(schema_version=2))),
        cast(Any, coordinator),
    )
    integration = SimpleNamespace(version="0.1.1")
    with patch(
        "custom_components.energy_usage.diagnostics.async_get_integration",
        AsyncMock(return_value=integration),
    ):
        result = await async_get_config_entry_diagnostics(hass, entry)
    assert set(result) == EXPECTED
    assert result["integration_version"] == "0.1.1"
    assert result["home_assistant_version"] != "99"
    assert result["freshness"] == "delayed"
    encoded = json.dumps(result, sort_keys=True)
    assert canary not in encoded
    assert result["provider_key"] == "example"
    assert result["location_public_id"] == PUBLIC_ID
    assert result["supports_cost"] is True
    assert result["provider_currency"] == "USD"
    result["retained_interval_count"] = 999
    assert coordinator.diagnostics()["retained_interval_count"] == 12


async def test_diagnostics_resolves_manifest_and_home_assistant_versions(
    hass: HomeAssistant,
) -> None:
    from homeassistant.const import __version__ as home_assistant_version

    entry = common.MockConfigEntry(
        domain="energy_usage",
        version=99,
        unique_id=PUBLIC_ID,
        data={"provider_schema_version": 1},
    )
    entry.add_to_hass(hass)
    status = {
        key: None
        for key in EXPECTED
        if key not in {"integration_version", "home_assistant_version"}
    }
    coordinator = SimpleNamespace(diagnostics=lambda: status)
    entry.runtime_data = EnergyUsageRuntimeData(
        cast(Any, provider()),
        cast(Any, SimpleNamespace(state=SimpleNamespace(schema_version=2))),
        cast(Any, coordinator),
    )
    result = await async_get_config_entry_diagnostics(hass, entry)
    manifest = json.loads(Path("custom_components/energy_usage/manifest.json").read_text())
    assert result["integration_version"] == manifest["version"]
    assert result["home_assistant_version"] == home_assistant_version
    assert result["integration_version"] != str(entry.version)
