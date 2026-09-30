"""Energy Usage integration lifecycle."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Coroutine, Mapping
from contextlib import suppress
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TIME_ZONE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .const import (
    CONF_AUTH,
    CONF_LOCATION_PUBLIC_ID,
    CONF_PRIVATE_LOCATION_ID,
    CONF_PROVIDER_KEY,
    DOMAIN,
    PROVIDER_SCHEMA_VERSION,
)
from .coordinator import EnergyUsageDataUpdateCoordinator
from .issues import RepairKind, create_issue, delete_issue
from .ledger import EnergyLedger, LedgerRepairError
from .provider import EnergyProvider, RequestBudget, create_provider, provider_descriptors
from .providers import register_all

PLATFORMS: list[Platform] = [Platform.SENSOR]
_PUBLIC_ID = re.compile(r"[0-9a-f]{32}\Z")

register_all()


@dataclass(slots=True)
class EnergyUsageRuntimeData:
    """Objects owned by one configured provider location."""

    provider: EnergyProvider
    ledger: EnergyLedger
    coordinator: EnergyUsageDataUpdateCoordinator


type EnergyUsageConfigEntry = ConfigEntry[EnergyUsageRuntimeData]

_RUNTIME_REPAIRS = {
    RepairKind.LEDGER_CORRUPT,
    RepairKind.LEDGER_FUTURE,
    RepairKind.SCHEMA_DRIFT,
    RepairKind.CURRENCY_MISMATCH,
    RepairKind.TIMEZONE_MISMATCH,
    RepairKind.DATA_RETRACTION,
    RepairKind.BACKFILL_STALLED,
}
_CONDITION_TO_REPAIR = {
    "ledger_repair": RepairKind.LEDGER_CORRUPT,
    **{kind.value: kind for kind in _RUNTIME_REPAIRS},
}


def _active_runtime_repairs(
    coordinator: EnergyUsageDataUpdateCoordinator,
) -> tuple[set[RepairKind], bool]:
    """Read the coordinator's closed, value-free repair condition set."""
    diagnostics = coordinator.diagnostics()
    conditions = diagnostics.get("repair_conditions")
    active: set[RepairKind] = set()
    if isinstance(conditions, list):
        for token in conditions:
            if isinstance(token, str) and (kind := _CONDITION_TO_REPAIR.get(token)) is not None:
                active.add(kind)
    return active, isinstance(diagnostics.get("last_successful_fetch"), str)


def _create_active_runtime_issues(
    hass: HomeAssistant,
    public_id: str,
    coordinator: EnergyUsageDataUpdateCoordinator,
) -> tuple[set[RepairKind], bool]:
    active, has_verified_fetch = _active_runtime_repairs(coordinator)
    for kind in active:
        create_issue(hass, public_id, kind)
    return active, has_verified_fetch


def _reconcile_runtime_issues(
    hass: HomeAssistant,
    public_id: str,
    coordinator: EnergyUsageDataUpdateCoordinator,
) -> None:
    active, has_verified_fetch = _create_active_runtime_issues(hass, public_id, coordinator)
    if not has_verified_fetch:
        return
    for kind in _RUNTIME_REPAIRS:
        if kind not in active:
            delete_issue(hass, public_id, kind)


def _resolve_verified_ledger_issues(
    hass: HomeAssistant,
    public_id: str,
    ledger: EnergyLedger,
) -> None:
    if ledger.state.revision <= 0:
        return
    delete_issue(hass, public_id, RepairKind.LEDGER_CORRUPT)
    delete_issue(hass, public_id, RepairKind.LEDGER_FUTURE)


async def _async_complete_cleanup(
    cleanup: Coroutine[Any, Any, None],
    *,
    name: str,
) -> None:
    """Complete ordered cleanup before re-propagating caller cancellation."""
    cleanup_task = asyncio.create_task(cleanup, name=name)
    cancellation: asyncio.CancelledError | None = None
    while not cleanup_task.done():
        try:
            await asyncio.shield(cleanup_task)
        except asyncio.CancelledError as error:
            if cleanup_task.cancelled():
                raise
            cancellation = error
    cleanup_task.result()
    if cancellation is not None:
        raise cancellation


async def _async_logout_provider(provider: EnergyProvider) -> None:
    """Best-effort provider-owned credential cleanup."""
    with suppress(Exception):
        await provider.async_logout(RequestBudget())


async def _async_cleanup_failed_setup(
    hass: HomeAssistant,
    entry: EnergyUsageConfigEntry,
    provider: EnergyProvider,
    coordinator: EnergyUsageDataUpdateCoordinator | None,
) -> None:
    async def cleanup() -> None:
        try:
            if hasattr(entry, "runtime_data"):
                with suppress(Exception):
                    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
            if coordinator is not None:
                with suppress(Exception):
                    await coordinator.async_shutdown()
        finally:
            await _async_logout_provider(provider)
            if hasattr(entry, "runtime_data"):
                with suppress(Exception):
                    object.__delattr__(entry, "runtime_data")

    await _async_complete_cleanup(cleanup(), name=f"{DOMAIN} failed setup cleanup")


def _entry_is_valid(entry: ConfigEntry) -> bool:
    """Validate the version-one provider/location envelope without network access."""
    data = entry.data
    provider_key = data.get(CONF_PROVIDER_KEY)
    auth = data.get(CONF_AUTH)
    private_id = data.get(CONF_PRIVATE_LOCATION_ID)
    public_id = data.get(CONF_LOCATION_PUBLIC_ID)
    schema = data.get("provider_schema_version")
    time_zone = data.get(CONF_TIME_ZONE)
    supported = {descriptor.key for descriptor in provider_descriptors()}
    if (
        entry.version != 1
        or not isinstance(provider_key, str)
        or provider_key not in supported
        or not isinstance(auth, Mapping)
        or not auth
        or not isinstance(private_id, str)
        or not private_id
        or not isinstance(public_id, str)
        or _PUBLIC_ID.fullmatch(public_id) is None
        or entry.unique_id != public_id
        or schema != PROVIDER_SCHEMA_VERSION
        or type(data.get("ledger_initialized", False)) is not bool
        or not isinstance(time_zone, str)
    ):
        return False
    try:
        ZoneInfo(time_zone)
    except TypeError, ValueError, ZoneInfoNotFoundError:
        return False
    return True


async def _migration_checkpoint_is_valid(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Validate an optional same-domain migration checkpoint without mutation."""
    try:
        raw = await Store[dict[str, Any]](
            hass,
            1,
            f"{DOMAIN}.migration_{entry.entry_id}",
            private=True,
            atomic_writes=True,
            read_only=True,
        ).async_load()
    except Exception:
        return False
    if raw is None:
        return True
    expected = {
        "entry_version": entry.version,
        "provider_key": entry.data.get(CONF_PROVIDER_KEY),
        "location_public_id": entry.data.get(CONF_LOCATION_PUBLIC_ID),
    }
    return raw == expected


async def async_recover_migration(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Fail closed on malformed same-domain v1 entries without legacy imports."""
    return _entry_is_valid(entry) and await _migration_checkpoint_is_valid(hass, entry)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Validate the current schema; future migrations will advance this version."""
    return _entry_is_valid(entry) and await _migration_checkpoint_is_valid(hass, entry)


async def async_setup_entry(hass: HomeAssistant, entry: EnergyUsageConfigEntry) -> bool:
    """Set up one provider and one selected service location."""
    if not await async_recover_migration(hass, entry):
        raise ConfigEntryNotReady("ledger_repair")

    provider_key = str(entry.data[CONF_PROVIDER_KEY])
    public_id = str(entry.data[CONF_LOCATION_PUBLIC_ID])
    provider_schema_version = int(entry.data["provider_schema_version"])
    auth = entry.data[CONF_AUTH]
    assert isinstance(auth, Mapping)
    provider = create_provider(
        provider_key,
        async_get_clientsession(hass),
        auth,
    )
    ledger = EnergyLedger(
        hass,
        public_id,
        provider_key=provider_key,
        provider_schema_version=provider_schema_version,
    )
    coordinator: EnergyUsageDataUpdateCoordinator | None = None
    try:
        coordinator = EnergyUsageDataUpdateCoordinator(
            hass,
            entry,
            provider,
            ledger,
            time_zone=str(entry.data[CONF_TIME_ZONE]),
        )
        try:
            await coordinator.async_initialize()
        except LedgerRepairError as error:
            kind = RepairKind(error.kind.value)
            create_issue(hass, public_id, kind)
            raise ConfigEntryNotReady(kind.value) from None
        _resolve_verified_ledger_issues(hass, public_id, ledger)

        try:
            await coordinator.async_config_entry_first_refresh()
        except BaseException:
            _create_active_runtime_issues(hass, public_id, coordinator)
            raise

        if ledger.state.revision <= 0:
            active, _ = _create_active_runtime_issues(hass, public_id, coordinator)
            for kind in (
                RepairKind.DATA_RETRACTION,
                RepairKind.SCHEMA_DRIFT,
                RepairKind.TIMEZONE_MISMATCH,
                RepairKind.LEDGER_FUTURE,
                RepairKind.LEDGER_CORRUPT,
            ):
                if kind in active:
                    raise ConfigEntryNotReady(kind.value)
            create_issue(hass, public_id, RepairKind.LEDGER_CORRUPT)
            raise ConfigEntryNotReady(RepairKind.LEDGER_CORRUPT.value)
        _resolve_verified_ledger_issues(hass, public_id, ledger)
        if not bool(entry.data.get("ledger_initialized", False)):
            hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, "ledger_initialized": True},
            )
            if entry.data.get("ledger_initialized") is not True:
                create_issue(hass, public_id, RepairKind.LEDGER_CORRUPT)
                raise ConfigEntryNotReady(RepairKind.LEDGER_CORRUPT.value)

        entry.runtime_data = EnergyUsageRuntimeData(provider, ledger, coordinator)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        _reconcile_runtime_issues(hass, public_id, coordinator)
        entry.async_on_unload(
            coordinator.async_add_listener(
                lambda: _reconcile_runtime_issues(hass, public_id, coordinator)
            )
        )
        await coordinator.async_start_backfill()
    except BaseException:
        await _async_cleanup_failed_setup(hass, entry, provider, coordinator)
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EnergyUsageConfigEntry) -> bool:
    """Unload entities before stopping owned work and provider authentication."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    runtime = entry.runtime_data

    async def cleanup() -> None:
        try:
            await runtime.coordinator.async_shutdown()
        finally:
            await _async_logout_provider(runtime.provider)

    await _async_complete_cleanup(cleanup(), name=f"{DOMAIN} unload cleanup")
    return True
