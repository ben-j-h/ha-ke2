"""Number entities for every editable numeric setpoint (except the climate's setpoint)."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pyke2 import SETPOINTS, FieldSpec

from . import KE2ConfigEntry
from .const import ADVANCED_FIELDS, CLIMATE_FIELDS, CONF_ADVANCED, FIELD_UNITS
from .entity import KE2FieldEntity, temperature_unit


async def async_setup_entry(
    hass: HomeAssistant, entry: KE2ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    advanced = entry.options.get(CONF_ADVANCED, False)
    async_add_entities(
        KE2Number(coordinator, key, spec)
        for key in coordinator.data
        for spec in coordinator.schemas[key].fields(SETPOINTS)
        if spec.editable
        and spec.is_numeric
        and spec.key not in CLIMATE_FIELDS
        and (advanced or spec.key not in ADVANCED_FIELDS)
    )


class KE2Number(KE2FieldEntity, NumberEntity):
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, ctrl_key: str, spec: FieldSpec) -> None:
        super().__init__(coordinator, ctrl_key, spec)
        self._attr_native_step = 1 if spec.data_type == "Integer" else 0.1
        if spec.key in ADVANCED_FIELDS:
            self._attr_entity_registry_enabled_default = False
        if spec.is_temperature:
            self._attr_device_class = NumberDeviceClass.TEMPERATURE
        self._unit: str | None = FIELD_UNITS.get(spec.key)
        # Values outside Min/Max that are still allowed (e.g. 0 = Disabled)
        self._extra_lows = [d for d in spec.discrete if isinstance(d, int | float)]

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.spec.is_temperature and self.ctrl:
            return temperature_unit(self.ctrl)
        return self._unit

    @property
    def native_min_value(self) -> float:
        lo, _ = self.spec.bounds(self.ctrl.units if self.ctrl else "Fahrenheit")
        candidates = [v for v in (lo, *self._extra_lows) if isinstance(v, int | float)]
        return float(min(candidates)) if candidates else 0.0

    @property
    def native_max_value(self) -> float:
        _, hi = self.spec.bounds(self.ctrl.units if self.ctrl else "Fahrenheit")
        return float(hi) if isinstance(hi, int | float) else 100.0

    @property
    def native_value(self) -> float | None:
        raw = self.raw
        try:
            return None if raw is None else float(raw)
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self):
        meaning = self.spec.special_meaning(self.raw)
        return {"meaning": meaning} if meaning else None

    async def async_set_native_value(self, value: float) -> None:
        out = int(value) if self.spec.data_type == "Integer" else value
        await self._write(self.spec.category, {self.spec.key: out})
