"""Strictly allowlisted diagnostics for Energy Usage."""

from __future__ import annotations

import re

from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from . import EnergyUsageConfigEntry
from .const import DOMAIN

type _DiagnosticValue = str | int | bool | None

_APPROVED = (
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
)
_PUBLIC_ID = re.compile(r"[0-9a-f]{32}\Z", re.ASCII)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: EnergyUsageConfigEntry,
) -> dict[str, _DiagnosticValue]:
    """Build a new object from the fixed public diagnostics contract."""
    status = entry.runtime_data.coordinator.diagnostics()
    provider = entry.runtime_data.provider
    capabilities = provider.capabilities
    public_id = entry.unique_id
    provider_schema = entry.data.get("provider_schema_version")
    ledger_schema = entry.runtime_data.ledger.state.schema_version
    integration = await async_get_integration(hass, DOMAIN)
    result: dict[str, _DiagnosticValue] = {
        "integration_version": str(integration.version),
        "home_assistant_version": HA_VERSION,
        "provider_key": provider.descriptor.key,
        "location_public_id": (
            public_id
            if isinstance(public_id, str) and _PUBLIC_ID.fullmatch(public_id) is not None
            else None
        ),
        "provider_schema_version": (provider_schema if type(provider_schema) is int else None),
        "ledger_schema_version": ledger_schema if type(ledger_schema) is int else None,
        "supports_import": capabilities.supports_import,
        "supports_return": capabilities.supports_return,
        "supports_cost": capabilities.supports_cost,
        "supports_compensation": capabilities.supports_compensation,
        "provider_currency": capabilities.currency,
        "interval_seconds": int(capabilities.interval_duration.total_seconds()),
        "publication_delay_seconds": int(capabilities.publication_delay.total_seconds()),
        "historical_range_days": int(capabilities.historical_range.total_seconds() // 86400),
        "minimum_poll_seconds": int(capabilities.minimum_poll_interval.total_seconds()),
    }
    for key in _APPROVED:
        value = status.get(key)
        result[key] = value if isinstance(value, (str, int, bool)) or value is None else None
    return result
