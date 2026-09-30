"""Privacy-safe rolling usage and integration-health sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import EnergyUsageConfigEntry
from .coordinator import EnergyUsageDataUpdateCoordinator
from .entity import EnergyUsageEntity
from .models import Freshness, ProviderCapabilities, UsageSnapshot

type _SnapshotValue = Decimal | datetime | str | None
type _StatusValue = str | int | bool | None | list[str]


@dataclass(frozen=True, kw_only=True)
class EnergyUsageSensorEntityDescription(SensorEntityDescription):
    """Describe one explicitly approved public sensor."""

    snapshot_value: Callable[[UsageSnapshot], _SnapshotValue] | None = None
    status_key: str | None = None
    capability: str | None = None


def _usage(
    key: str,
    field: str,
    *,
    monetary: bool = False,
    currency: str | None = None,
    capability: str = "import",
) -> EnergyUsageSensorEntityDescription:
    return EnergyUsageSensorEntityDescription(
        key=key,
        translation_key=key,
        native_unit_of_measurement=currency if monetary else UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.MONETARY if monetary else SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:cash-multiple" if monetary else "mdi:transmission-tower-import",
        suggested_display_precision=2 if monetary else 3,
        snapshot_value=lambda snapshot: getattr(snapshot, field),
        capability=capability,
    )


def all_sensor_descriptions(
    *, currency: str | None
) -> tuple[EnergyUsageSensorEntityDescription, ...]:
    """Return the complete translated inventory for repository validation."""
    return (
        EnergyUsageSensorEntityDescription(
            key="newest_interval",
            translation_key="newest_interval",
            device_class=SensorDeviceClass.TIMESTAMP,
            icon="mdi:clock-check-outline",
            snapshot_value=lambda snapshot: snapshot.newest_interval_start,
        ),
        EnergyUsageSensorEntityDescription(
            key="freshness",
            translation_key="freshness",
            device_class=SensorDeviceClass.ENUM,
            options=[value.value for value in Freshness],
            icon="mdi:database-clock-outline",
            snapshot_value=lambda snapshot: snapshot.freshness.value,
        ),
        _usage("latest_import", "latest_import_kwh"),
        _usage("today_import", "today_import_kwh"),
        _usage("seven_day_import", "seven_day_import_kwh"),
        _usage("month_import", "month_import_kwh"),
        _usage("latest_return", "latest_return_kwh", capability="return"),
        _usage("today_return", "today_return_kwh", capability="return"),
        _usage("seven_day_return", "seven_day_return_kwh", capability="return"),
        _usage("month_return", "month_return_kwh", capability="return"),
        _usage("latest_cost", "latest_cost", monetary=True, currency=currency, capability="cost"),
        _usage("today_cost", "today_cost", monetary=True, currency=currency, capability="cost"),
        _usage(
            "seven_day_cost", "seven_day_cost", monetary=True, currency=currency, capability="cost"
        ),
        _usage("month_cost", "month_cost", monetary=True, currency=currency, capability="cost"),
        _usage(
            "latest_compensation",
            "latest_compensation",
            monetary=True,
            currency=currency,
            capability="compensation",
        ),
        _usage(
            "today_compensation",
            "today_compensation",
            monetary=True,
            currency=currency,
            capability="compensation",
        ),
        _usage(
            "seven_day_compensation",
            "seven_day_compensation",
            monetary=True,
            currency=currency,
            capability="compensation",
        ),
        _usage(
            "month_compensation",
            "month_compensation",
            monetary=True,
            currency=currency,
            capability="compensation",
        ),
        EnergyUsageSensorEntityDescription(
            key="last_successful_fetch",
            translation_key="last_successful_fetch",
            device_class=SensorDeviceClass.TIMESTAMP,
            icon="mdi:cloud-check-outline",
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            status_key="last_successful_fetch",
        ),
        EnergyUsageSensorEntityDescription(
            key="retained_interval_count",
            translation_key="retained_interval_count",
            icon="mdi:counter",
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            status_key="retained_interval_count",
        ),
        EnergyUsageSensorEntityDescription(
            key="estimated_interval_count",
            translation_key="estimated_interval_count",
            icon="mdi:counter",
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            status_key="estimated_interval_count",
        ),
        EnergyUsageSensorEntityDescription(
            key="last_corrected_count",
            translation_key="last_corrected_count",
            icon="mdi:database-edit-outline",
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            status_key="last_corrected_count",
        ),
        EnergyUsageSensorEntityDescription(
            key="backfill_progress",
            translation_key="backfill_progress",
            native_unit_of_measurement=PERCENTAGE,
            icon="mdi:history",
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            status_key="backfill_progress_percent",
        ),
    )


def sensor_descriptions(
    capabilities: ProviderCapabilities,
) -> tuple[EnergyUsageSensorEntityDescription, ...]:
    """Expose only measurement families declared by the active provider."""
    supported = {
        "import": capabilities.supports_import,
        "return": capabilities.supports_return,
        "cost": capabilities.supports_cost,
        "compensation": capabilities.supports_compensation,
    }
    return tuple(
        description
        for description in all_sensor_descriptions(currency=capabilities.currency)
        if description.capability is None or supported[description.capability]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnergyUsageConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors from the typed runtime container."""
    del hass
    runtime = entry.runtime_data
    public_id = str(entry.data["location_public_id"])
    async_add_entities(
        EnergyUsageSensor(
            runtime.coordinator,
            public_id,
            runtime.provider.descriptor.name,
            description,
        )
        for description in sensor_descriptions(runtime.provider.capabilities)
    )


class EnergyUsageSensor(EnergyUsageEntity, SensorEntity):
    """One explicitly allowlisted provider-neutral sensor."""

    entity_description: EnergyUsageSensorEntityDescription

    def __init__(
        self,
        coordinator: EnergyUsageDataUpdateCoordinator,
        public_id: str,
        provider_name: str,
        description: EnergyUsageSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, public_id, provider_name)
        self.entity_description = description
        self._attr_unique_id = f"{public_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return only a reviewed snapshot or safe-status value."""
        value_fn = self.entity_description.snapshot_value
        if value_fn is not None:
            return value_fn(self.coordinator.data)
        key = self.entity_description.status_key
        assert key is not None
        status: dict[str, _StatusValue] = self.coordinator.diagnostics()
        value = status.get(key)
        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            if not isinstance(value, str):
                return None
            parsed = dt_util.parse_datetime(value)
            return parsed if parsed is not None and parsed.tzinfo is not None else None
        if key == "backfill_progress_percent":
            if status.get("backfill_complete") is True:
                return 100
            return min(99, value) if type(value) is int else None
        return value
