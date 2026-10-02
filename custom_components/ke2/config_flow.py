"""Config + options flow for KE2 Therm."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pyke2 import (
    DEFAULT_PASSWORD,
    DEFAULT_USERNAME,
    KE2LDA,
    KE2AuthError,
    KE2Error,
)

from .const import (
    CONF_ADVANCED,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def _user_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Required(CONF_USERNAME, default=defaults.get(CONF_USERNAME, DEFAULT_USERNAME)): str,
            vol.Required(CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, DEFAULT_PASSWORD)): str,
        }
    )


class KE2ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up a KE2 LDA by IP address."""

    VERSION = 1

    async def _validate(self, data: dict[str, Any]) -> tuple[str, str]:
        """Return (unique_id, title); raises KE2Error / KE2AuthError."""
        lda = KE2LDA(
            data[CONF_HOST],
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            session=async_get_clientsession(self.hass),
        )
        controllers = await lda.get_all()
        if not controllers:
            raise KE2Error("no controllers found on the LDA")
        await lda.login()  # check write credentials now, not at the first write
        await lda.logout()
        try:
            fqdn = str((await lda.network_info()).get("wan-fqdn") or "")
        except KE2Error:
            fqdn = ""
        hostname = fqdn.split(".")[0] or data[CONF_HOST]
        models = ", ".join(sorted({c.model for c in controllers.values()}))
        return hostname.upper(), f"{models} ({hostname})"

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                unique_id, title = await self._validate(user_input)
            except KE2AuthError:
                errors["base"] = "invalid_auth"
            except KE2Error as err:
                _LOGGER.debug("KE2 LDA validation failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured(updates={CONF_HOST: user_input[CONF_HOST]})
                return self.async_create_entry(title=title, data=user_input)
        return self.async_show_form(
            step_id="user", data_schema=_user_schema(user_input or {}), errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                unique_id, _ = await self._validate(user_input)
            except KE2AuthError:
                errors["base"] = "invalid_auth"
            except KE2Error:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_user_schema(user_input or dict(entry.data)),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> KE2OptionsFlow:
        return KE2OptionsFlow()


class KE2OptionsFlow(OptionsFlow):
    """Poll interval and whether to expose advanced setpoints."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        opts = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=600)),
                    vol.Required(CONF_ADVANCED, default=opts.get(CONF_ADVANCED, False)): bool,
                }
            ),
        )
