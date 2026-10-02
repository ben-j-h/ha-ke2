"""Diagnostics: raw controller state + schema (credentials redacted)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from pyke2 import KE2Error

from . import KE2ConfigEntry

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: KE2ConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data.coordinator
    lda = entry.runtime_data.lda
    controllers = {}
    for key, ctrl in (coordinator.data or {}).items():
        data = asdict(ctrl)
        data.pop("schema", None)
        schema = coordinator.schemas.get(key)
        data["schema"] = (
            {f"{f.category}.{f.key}": asdict(f) for f in schema.fields()} if schema else None
        )
        controllers[key] = data
    try:
        version = await lda.version()
    except KE2Error as err:
        version = {"error": str(err)}
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "lda_version": version,
        "controllers": controllers,
    }
