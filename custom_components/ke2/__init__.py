"""KE2 Therm refrigeration controllers via the KE2 LDA (local polling)."""

from __future__ import annotations

from dataclasses import dataclass

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from pyke2 import KE2LDA, SETPOINTS, KE2Error

from .const import ATTR_CATEGORY, ATTR_FIELD, ATTR_VALUE, DOMAIN, MANUFACTURER, SERVICE_SET_VALUE
from .coordinator import KE2Coordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass(slots=True)
class KE2RuntimeData:
    lda: KE2LDA
    coordinator: KE2Coordinator
    hub_device_id: str


type KE2ConfigEntry = ConfigEntry[KE2RuntimeData]

SET_VALUE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Optional(ATTR_CATEGORY, default=SETPOINTS): cv.string,
        vol.Required(ATTR_FIELD): cv.string,
        vol.Required(ATTR_VALUE): vol.Any(cv.string, vol.Coerce(float)),
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the raw ``ke2.set_value`` service (any writable field, e.g. a disabled 24:00)."""

    async def _set_value(call: ServiceCall) -> None:
        entry_reg = er.async_get(hass).async_get(call.data[ATTR_ENTITY_ID])
        entry = (
            hass.config_entries.async_get_entry(entry_reg.config_entry_id)
            if entry_reg and entry_reg.config_entry_id
            else None
        )
        if entry is None or entry.domain != DOMAIN or not hasattr(entry, "runtime_data"):
            raise ServiceValidationError("entity_id must be a loaded KE2 entity")
        ctrl_key = (entry_reg.unique_id or "").split("|")[1] if "|" in entry_reg.unique_id else ""
        value = call.data[ATTR_VALUE]
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        await entry.runtime_data.coordinator.async_write(
            ctrl_key, call.data[ATTR_CATEGORY], {call.data[ATTR_FIELD]: value}
        )

    hass.services.async_register(DOMAIN, SERVICE_SET_VALUE, _set_value, schema=SET_VALUE_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: KE2ConfigEntry) -> bool:
    lda = KE2LDA(
        entry.data[CONF_HOST],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
    )
    coordinator = KE2Coordinator(hass, entry, lda)
    await coordinator.async_config_entry_first_refresh()
    # Hub device for the LDA itself; each controller's device hangs off it (via_device).
    try:
        version = await lda.version()
    except KE2Error:
        version = {}
    hub = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id)},
        manufacturer=MANUFACTURER,
        model="LDA (Local Area Dashboard and Alarms)",
        name=f"KE2 LDA {entry.unique_id}",
        sw_version=version.get("Version"),
        configuration_url=f"http://{lda.host}/",
    )
    entry.runtime_data = KE2RuntimeData(lda=lda, coordinator=coordinator, hub_device_id=hub.id)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: KE2ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: KE2ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
