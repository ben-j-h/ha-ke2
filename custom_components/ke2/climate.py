"""Climate entity: cooling thermostat (room probe, setpoint, relay/mode)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pyke2 import SETPOINTS, KE2Error

from . import KE2ConfigEntry
from .entity import KE2Entity, temperature_unit


async def async_setup_entry(
    hass: HomeAssistant, entry: KE2ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        KE2Climate(coordinator, key)
        for key, ctrl in coordinator.data.items()
        if ctrl.has(SETPOINTS, "RoomTemperature")
    )


class KE2Climate(KE2Entity, ClimateEntity):
    _attr_name = None  # the device name
    _attr_target_temperature_step = 1
    _attr_precision = PRECISION_TENTHS  # probe reads in 0.1°
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator, ctrl_key: str) -> None:
        super().__init__(coordinator, ctrl_key, "climate")
        ctrl = coordinator.data[ctrl_key]
        self._manual = ctrl.supports_manual_control
        self._attr_hvac_modes = [HVACMode.COOL, HVACMode.OFF] if self._manual else [HVACMode.COOL]
        features = ClimateEntityFeature.TARGET_TEMPERATURE
        if self._manual:
            features |= ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        self._attr_supported_features = features
        spec = coordinator.schemas[ctrl_key].get(SETPOINTS, "RoomTemperature")
        if spec is not None:
            lo, hi = spec.bounds(ctrl.units)
            self._attr_min_temp, self._attr_max_temp = float(lo), float(hi)

    @property
    def temperature_unit(self) -> str:
        return temperature_unit(self.ctrl) if self.ctrl else super().temperature_unit

    @property
    def current_temperature(self) -> float | None:
        return self.ctrl.room_temperature if self.ctrl else None

    @property
    def target_temperature(self) -> float | None:
        return self.ctrl.setpoint if self.ctrl else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        ctrl = self.ctrl
        if ctrl is None:
            return {}
        cut_in = (
            ctrl.setpoint + ctrl.differential
            if ctrl.setpoint is not None and ctrl.differential is not None
            else None
        )
        return {
            "cut_in_temperature": cut_in,
            "mode": ctrl.mode,
            "alarms": ctrl.alarms,
            "sensor_fault": ctrl.sensor_fault,
        }

    @property
    def hvac_mode(self) -> HVACMode | None:
        ctrl = self.ctrl
        if ctrl is None:
            return None
        if self._manual and ctrl.system_on is False:
            return HVACMode.OFF
        return HVACMode.COOL

    @property
    def hvac_action(self) -> HVACAction | None:
        ctrl = self.ctrl
        if ctrl is None:
            return None
        if self._manual and ctrl.system_on is False:
            return HVACAction.OFF
        if ctrl.defrosting:
            return HVACAction.DEFROSTING
        if ctrl.relay_on:
            return HVACAction.COOLING
        return HVACAction.IDLE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self._write(SETPOINTS, {"RoomTemperature": round(float(temp))})

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if not self._manual:
            if hvac_mode == HVACMode.COOL:
                return
            raise HomeAssistantError("this KE2 model has no manual on/off")
        ctrl = self.ctrl
        if ctrl is None:
            raise HomeAssistantError("controller unavailable")
        try:
            await self.coordinator.lda.set_system_on(
                ctrl.address, hvac_mode == HVACMode.COOL, interface=ctrl.interface
            )
        except KE2Error as err:
            raise HomeAssistantError(f"KE2 write failed: {err}") from err
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.COOL)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)
