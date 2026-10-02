"""Buttons: advance mode, sync the controller clock to Home Assistant's local time."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util
from pyke2 import SETPOINTS, KE2Error

from . import KE2ConfigEntry
from .entity import KE2Entity


async def async_setup_entry(
    hass: HomeAssistant, entry: KE2ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    entities: list[ButtonEntity] = []
    for key in coordinator.data:
        entities.append(KE2NextModeButton(coordinator, key))
        if coordinator.schemas[key].get(SETPOINTS, "Time of Day"):
            entities.append(KE2SyncClockButton(coordinator, key))
    async_add_entities(entities)


class KE2NextModeButton(KE2Entity, ButtonEntity):
    """The web UI's 'Next Mode' (Refrigerate → Off → Defrost …). Disabled by default."""

    _attr_name = "Next mode"
    _attr_icon = "mdi:debug-step-over"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, ctrl_key: str) -> None:
        super().__init__(coordinator, ctrl_key, "next_mode")

    async def async_press(self) -> None:
        ctrl = self.ctrl
        if ctrl is None:
            raise HomeAssistantError("controller unavailable")
        try:
            await self.coordinator.lda.next_mode(ctrl.address, interface=ctrl.interface)
        except KE2Error as err:
            raise HomeAssistantError(f"KE2 command failed: {err}") from err
        await self.coordinator.async_request_refresh()


class KE2SyncClockButton(KE2Entity, ButtonEntity):
    """Write HA's local time to the controller's free-running clock."""

    _attr_name = "Sync controller clock"
    _attr_icon = "mdi:clock-check-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, ctrl_key: str) -> None:
        super().__init__(coordinator, ctrl_key, "sync_clock")

    async def async_press(self) -> None:
        await self._write(SETPOINTS, {"Time of Day": dt_util.now().strftime("%H:%M")})
