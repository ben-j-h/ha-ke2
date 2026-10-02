"""Switch: Manual Control system on/off (only on models that have it)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pyke2 import KE2Error

from . import KE2ConfigEntry
from .entity import KE2Entity


async def async_setup_entry(
    hass: HomeAssistant, entry: KE2ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        KE2SystemSwitch(coordinator, key)
        for key, ctrl in coordinator.data.items()
        if ctrl.supports_manual_control
    )


class KE2SystemSwitch(KE2Entity, SwitchEntity):
    _attr_name = "System"
    _attr_icon = "mdi:power"

    def __init__(self, coordinator, ctrl_key: str) -> None:
        super().__init__(coordinator, ctrl_key, "system_on")

    @property
    def is_on(self) -> bool | None:
        return self.ctrl.system_on if self.ctrl else None

    async def _set(self, on: bool) -> None:
        ctrl = self.ctrl
        if ctrl is None:
            raise HomeAssistantError("controller unavailable")
        try:
            await self.coordinator.lda.set_system_on(ctrl.address, on, interface=ctrl.interface)
        except KE2Error as err:
            raise HomeAssistantError(f"KE2 write failed: {err}") from err
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)
