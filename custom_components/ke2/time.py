"""Time entities for HH:MM setpoints (controller clock, custom defrost start times).

``24:00`` (Time_Hours "Disabled") has no ``datetime.time`` form: it shows as unknown with a
``disabled`` attribute. To disable a start time again use ``ke2.set_value`` with ``24:00``.
"""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pyke2 import SETPOINTS, FieldSpec

from . import KE2ConfigEntry
from .entity import KE2FieldEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: KE2ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        KE2Time(coordinator, key, spec)
        for key in coordinator.data
        for spec in coordinator.schemas[key].fields(SETPOINTS)
        if spec.editable and spec.is_time
    )


class KE2Time(KE2FieldEntity, TimeEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, ctrl_key: str, spec: FieldSpec) -> None:
        super().__init__(coordinator, ctrl_key, spec)
        # Custom defrost start times only matter with DefrostsPerDay = 13 ("Custom").
        if spec.key.startswith("Start Time of Defrost"):
            self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> time | None:
        raw = self.raw
        if raw is None or self.spec.special_meaning(raw) is not None:
            return None
        try:
            hours, minutes = (int(p) for p in str(raw).split(":"))
            return time(hours, minutes)
        except ValueError:
            return None

    @property
    def extra_state_attributes(self):
        meaning = self.spec.special_meaning(self.raw)
        return {"disabled": True} if meaning == "Disabled" else None

    async def async_set_value(self, value: time) -> None:
        await self._write(self.spec.category, {self.spec.key: value.strftime("%H:%M")})
