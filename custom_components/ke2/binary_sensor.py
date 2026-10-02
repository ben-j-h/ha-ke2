"""Binary sensors: relays, one per alarm, probe fault."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pyke2 import STATUS, FieldSpec

from . import KE2ConfigEntry
from .const import slug
from .entity import KE2Entity, KE2FieldEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: KE2ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    entities: list[BinarySensorEntity] = []
    for key in coordinator.data:
        schema = coordinator.schemas[key]
        for spec in schema.fields(STATUS):
            if spec.key.lower().endswith("relay"):
                entities.append(KE2RelaySensor(coordinator, key, spec))
            elif spec.key == "Alarms":
                entities.extend(KE2AlarmSensor(coordinator, key, label) for label in spec.discrete)
        entities.append(KE2ProbeFaultSensor(coordinator, key))
    async_add_entities(entities)


class KE2RelaySensor(KE2FieldEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator, ctrl_key: str, spec: FieldSpec) -> None:
        super().__init__(coordinator, ctrl_key, spec)
        if spec.key == "Relay":
            self._attr_name = "Cooling relay"

    @property
    def is_on(self) -> bool | None:
        return self.ctrl.relay_state(self.spec.key) if self.ctrl else None


class KE2AlarmSensor(KE2Entity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, ctrl_key: str, label: str) -> None:
        super().__init__(coordinator, ctrl_key, f"alarm_{slug(str(label))}")
        self.label = str(label)
        self._attr_name = f"Alarm: {self.label}"

    @property
    def is_on(self) -> bool | None:
        return self.label in self.ctrl.alarms if self.ctrl else None


class KE2ProbeFaultSensor(KE2Entity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Room probe fault"

    def __init__(self, coordinator, ctrl_key: str) -> None:
        super().__init__(coordinator, ctrl_key, "probe_fault")

    @property
    def is_on(self) -> bool | None:
        return (self.ctrl.sensor_fault is not None) if self.ctrl else None

    @property
    def extra_state_attributes(self):
        return {"fault": self.ctrl.sensor_fault} if self.ctrl and self.ctrl.sensor_fault else None
