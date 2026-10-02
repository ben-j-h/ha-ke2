"""Sensors: temperatures and other numeric Status fields, mode, alarms, diagnostics."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pyke2 import STATUS, FieldSpec

from . import KE2ConfigEntry
from .const import FIELD_UNITS
from .entity import KE2Entity, KE2FieldEntity, temperature_unit


async def async_setup_entry(
    hass: HomeAssistant, entry: KE2ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    entities: list[SensorEntity] = []
    for key in coordinator.data:
        schema = coordinator.schemas[key]
        for spec in schema.fields(STATUS):
            if spec.is_numeric:
                entities.append(KE2NumericSensor(coordinator, key, spec))
            elif spec.is_enum and not spec.key.lower().endswith("relay"):
                entities.append(KE2EnumSensor(coordinator, key, spec))
            elif spec.key == "Alarms":
                entities.append(KE2AlarmCountSensor(coordinator, key, spec))
        entities.append(KE2CommTimeoutsSensor(coordinator, key))
    async_add_entities(entities)


class KE2NumericSensor(KE2FieldEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, ctrl_key: str, spec: FieldSpec) -> None:
        super().__init__(coordinator, ctrl_key, spec)
        if spec.is_temperature:
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_suggested_display_precision = 1
        self._unit: str | None = FIELD_UNITS.get(spec.key)

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.spec.is_temperature and self.ctrl:
            return temperature_unit(self.ctrl)
        return self._unit

    @property
    def native_value(self) -> float | None:
        raw = self.raw
        if raw is None or self.spec.special_meaning(raw) is not None:
            return None  # e.g. 999.9 shorted / 888.8 open probe
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        fault = self.spec.special_meaning(self.raw)
        return {"sensor_fault": fault} if fault else None


class KE2EnumSensor(KE2FieldEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(self, coordinator, ctrl_key: str, spec: FieldSpec) -> None:
        super().__init__(coordinator, ctrl_key, spec)
        self._attr_options = spec.options or None

    @property
    def native_value(self) -> str | None:
        raw = self.raw
        if raw is None:
            return None
        return str(raw) if not self._attr_options or str(raw) in self._attr_options else None


class KE2AlarmCountSensor(KE2FieldEntity, SensorEntity):
    _attr_icon = "mdi:alert"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        return len(self.ctrl.alarms) if self.ctrl else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"alarms": self.ctrl.alarms if self.ctrl else []}


class KE2CommTimeoutsSensor(KE2Entity, SensorEntity):
    _attr_name = "Modbus comm timeouts"
    _attr_icon = "mdi:lan-disconnect"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator, ctrl_key: str) -> None:
        super().__init__(coordinator, ctrl_key, "comm_timeouts")

    @property
    def native_value(self) -> int | None:
        return self.ctrl.comm_timeouts if self.ctrl else None
