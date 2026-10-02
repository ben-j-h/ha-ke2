"""Constants for the KE2 Therm integration."""

from __future__ import annotations

import re

DOMAIN = "ke2"
MANUFACTURER = "KE2 Therm Solutions"

CONF_SCAN_INTERVAL = "scan_interval"
CONF_ADVANCED = "advanced_setpoints"
DEFAULT_SCAN_INTERVAL = 30  # seconds
MIN_SCAN_INTERVAL = 10

# Setpoints that can break the controller's bus address or units if changed casually.
# Created disabled; only when the "advanced" option is on.
ADVANCED_FIELDS = frozenset({"ModbusAddress", "Temperature Units"})
# Fields the climate entity already covers.
CLIMATE_FIELDS = frozenset({"RoomTemperature"})

SERVICE_SET_VALUE = "set_value"
ATTR_CATEGORY = "category"
ATTR_FIELD = "field"
ATTR_VALUE = "value"

# Friendlier names for KE2 Temp fields; anything else is humanised generically.
FIELD_NAMES: dict[str, str] = {
    "RoomTemperature": "Room temperature",
    "CoilTemperature": "Coil temperature",
    "AirTempDiff": "Differential",
    "SystemMode": "Mode",
    "DefrostsPerDay": "Defrosts per day",
    "Defrost Time": "Defrost duration",
    "HiTempAlarmOffset": "High temperature alarm offset",
    "LowTempAlarmOffset": "Low temperature alarm offset",
    "HighAndLowAlarmDelay": "Temperature alarm delay",
    "Compressor Starts Per Hour": "Max compressor starts per hour",
    "ModbusAddress": "Modbus address",
    "Time of Day": "Controller clock",
}

# Units for unitless numeric fields we know.
FIELD_UNITS: dict[str, str] = {
    "Defrost Time": "min",
    "HighAndLowAlarmDelay": "min",
}

_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])")


def field_name(key: str) -> str:
    """Human name for a controller field."""
    if key in FIELD_NAMES:
        return FIELD_NAMES[key]
    text = _CAMEL.sub(" ", key).replace("_", " ").strip()
    return text[:1].upper() + text[1:].lower() if text else key


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
