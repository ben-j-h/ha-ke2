"""Select entities for editable enum setpoints (e.g. Temperature Units, advanced only)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pyke2 import SETPOINTS, FieldSpec

from . import KE2ConfigEntry
from .const import ADVANCED_FIELDS, CONF_ADVANCED
from .entity import KE2FieldEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: KE2ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    advanced = entry.options.get(CONF_ADVANCED, False)
    async_add_entities(
        KE2Select(coordinator, key, spec)
        for key in coordinator.data
        for spec in coordinator.schemas[key].fields(SETPOINTS)
        if spec.editable and spec.is_enum and (advanced or spec.key not in ADVANCED_FIELDS)
    )


class KE2Select(KE2FieldEntity, SelectEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, ctrl_key: str, spec: FieldSpec) -> None:
        super().__init__(coordinator, ctrl_key, spec)
        self._attr_options = spec.options
        if spec.key in ADVANCED_FIELDS:
            self._attr_entity_registry_enabled_default = False

    @property
    def current_option(self) -> str | None:
        raw = self.raw
        return str(raw) if raw is not None and str(raw) in self._attr_options else None

    async def async_select_option(self, option: str) -> None:
        await self._write(self.spec.category, {self.spec.key: option})
