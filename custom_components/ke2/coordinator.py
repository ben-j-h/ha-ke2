"""Polling coordinator: one ``GET /modbus/<if>/all`` per interval for every controller."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pyke2 import KE2LDA, Controller, KE2Error, Schema

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import KE2ConfigEntry

_LOGGER = logging.getLogger(__name__)


class KE2Coordinator(DataUpdateCoordinator[dict[str, Controller]]):
    """Fetches all controllers on the LDA and performs confirmed writes."""

    config_entry: KE2ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: KE2ConfigEntry, lda: KE2LDA) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.lda = lda
        self.schemas: dict[str, Schema] = {}

    async def _async_update_data(self) -> dict[str, Controller]:
        try:
            controllers = await self.lda.get_all()
            for key, ctrl in controllers.items():
                if key not in self.schemas:
                    self.schemas[key] = await self.lda.get_schema(ctrl.interface, ctrl.address)
                ctrl.schema = self.schemas[key]
        except KE2Error as err:
            raise UpdateFailed(f"KE2 LDA {self.lda.host}: {err}") from err
        if not controllers:
            raise UpdateFailed(f"KE2 LDA {self.lda.host} reports no controllers")
        return controllers

    async def async_write(self, ctrl_key: str, category: str, values: dict[str, Any]) -> None:
        """Validate + write, re-poll, and confirm the controller reports the new values."""
        ctrl = (self.data or {}).get(ctrl_key)
        if ctrl is None:
            raise HomeAssistantError(f"KE2 controller {ctrl_key} is not available")
        try:
            sent = await self.lda.set_values(
                ctrl.interface, ctrl.address, category, values, units=ctrl.units
            )
        except KE2Error as err:
            raise HomeAssistantError(f"KE2 write failed: {err}") from err
        await self.async_refresh()
        fresh = (self.data or {}).get(ctrl_key)
        if fresh is None:
            raise HomeAssistantError("KE2 controller unavailable after write; not confirmed")
        mismatched = {
            k: (v, fresh.value(category, k))
            for k, v in sent.items()
            if str(fresh.value(category, k)) != str(v)
            and not _numeric_equal(fresh.value(category, k), v)
        }
        if mismatched:
            raise HomeAssistantError(f"KE2 write not confirmed (sent, read back): {mismatched}")


def _numeric_equal(a: Any, b: Any) -> bool:
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return False
