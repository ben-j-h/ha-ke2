"""Shared base entity: one HA device per controller, behind an LDA hub device."""

from __future__ import annotations

from typing import Any

from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pyke2 import Controller, FieldSpec

from .const import DOMAIN, MANUFACTURER, field_name, slug
from .coordinator import KE2Coordinator


class KE2Entity(CoordinatorEntity[KE2Coordinator]):
    """An entity on one controller (``ctrl_key`` = '<interface>-<address>')."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: KE2Coordinator, ctrl_key: str, suffix: str) -> None:
        super().__init__(coordinator)
        self.ctrl_key = ctrl_key
        entry = coordinator.config_entry
        ctrl = coordinator.data[ctrl_key]
        # '|' separates parts so the ke2.set_value service can recover the controller key.
        self._attr_unique_id = f"{entry.unique_id}|{ctrl_key}|{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.unique_id}-{ctrl_key}")},
            manufacturer=MANUFACTURER,
            model=ctrl.model,
            sw_version=ctrl.version,
            hw_version=str(ctrl.firmware_id) if ctrl.firmware_id is not None else None,
            name=ctrl.device_name or f"{ctrl.model} ({ctrl.interface} #{ctrl.address})",
            via_device_id=entry.runtime_data.hub_device_id,
            configuration_url=(
                f"http://{coordinator.lda.host}/smartaccess/modbus/index.html"
                f"?endpoint={ctrl.interface}:{ctrl.address}"
            ),
        )

    @property
    def ctrl(self) -> Controller | None:
        return (self.coordinator.data or {}).get(self.ctrl_key)

    @property
    def available(self) -> bool:
        return super().available and self.ctrl is not None

    async def _write(self, category: str, values: dict[str, Any]) -> None:
        await self.coordinator.async_write(self.ctrl_key, category, values)


class KE2FieldEntity(KE2Entity):
    """An entity bound to one schema field."""

    def __init__(self, coordinator: KE2Coordinator, ctrl_key: str, spec: FieldSpec) -> None:
        super().__init__(coordinator, ctrl_key, f"{slug(spec.category)}_{slug(spec.key)}")
        self.spec = spec
        self._attr_name = field_name(spec.key)

    @property
    def raw(self) -> Any:
        ctrl = self.ctrl
        return None if ctrl is None else ctrl.value(self.spec.category, self.spec.key)

    @property
    def available(self) -> bool:
        ctrl = self.ctrl
        spec = self.spec
        return super().available and ctrl is not None and ctrl.has(spec.category, spec.key)


def temperature_unit(ctrl: Controller) -> str:
    return UnitOfTemperature.CELSIUS if ctrl.units == "Celsius" else UnitOfTemperature.FAHRENHEIT
