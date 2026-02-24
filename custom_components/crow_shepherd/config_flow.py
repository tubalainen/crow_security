"""Config flow for Crow Shepherd integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from crow_security_ng import Session
from crow_security_ng.exceptions import (
    AuthenticationError,
    ConnectionError,
    InvalidMacError,
    PanelNotFoundError,
)
from crow_security_ng.utils import normalize_mac

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback

from .const import (
    CONF_PANEL_CODE,
    CONF_PANEL_MAC,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _try_normalize_mac(raw: str) -> str | None:
    """Return 12-char lowercase hex MAC, or None if the input is invalid.

    Accepts both:
      - compact form:   0013A1250A45
      - colon-separated: 00:13:A1:25:0A:45
    (and also dash-separated or space-separated variants)
    """
    try:
        return normalize_mac(raw)
    except InvalidMacError:
        return None


_STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_PANEL_MAC): str,
        vol.Optional(CONF_PANEL_CODE, default=""): str,
    }
)


class CrowShepherdConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the onboarding wizard for Crow Shepherd."""

    VERSION = 2

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """First (and only) setup step — credentials + panel MAC."""
        errors: dict[str, str] = {}

        if user_input is not None:
            raw_mac = user_input[CONF_PANEL_MAC].strip()
            normalized_mac = _try_normalize_mac(raw_mac)

            if normalized_mac is None:
                errors[CONF_PANEL_MAC] = "invalid_mac"
            else:
                try:
                    session = Session(
                        user_input[CONF_EMAIL],
                        user_input[CONF_PASSWORD],
                    )
                    panel = await session.get_panel(normalized_mac)
                    await session.close()

                    # Use only the MAC as unique ID (not email+mac)
                    await self.async_set_unique_id(normalized_mac)
                    self._abort_if_unique_id_configured()

                    panel_name = panel.name or "Crow Shepherd"
                    panel_code = user_input.get(CONF_PANEL_CODE, "").strip() or None

                    entry_data: dict[str, Any] = {
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_PANEL_MAC: normalized_mac,
                    }
                    if panel_code:
                        entry_data[CONF_PANEL_CODE] = panel_code

                    return self.async_create_entry(title=panel_name, data=entry_data)

                except AuthenticationError:
                    errors["base"] = "invalid_auth"
                except PanelNotFoundError:
                    errors["base"] = "no_panel"
                except ConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Unexpected error during config flow")
                    errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=_STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self,
        entry_data: dict[str, Any],
    ) -> ConfigFlowResult:
        """Start reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle reauthentication with new credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            entry = self._get_reauth_entry()
            stored_mac = entry.data[CONF_PANEL_MAC]
            try:
                session = Session(
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                )
                await session.get_panel(stored_mac)
                await session.close()

                return self.async_update_reload_and_abort(
                    entry,
                    data={
                        **entry.data,
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except PanelNotFoundError:
                errors["base"] = "no_panel"
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during reauth")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return CrowShepherdOptionsFlow(config_entry)


class CrowShepherdOptionsFlow(OptionsFlow):
    """Options flow — update scan interval and panel code."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialise options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Show and handle the options form."""
        if user_input is not None:
            # Strip empty panel_code so we don't store an empty string
            if not user_input.get(CONF_PANEL_CODE, "").strip():
                user_input.pop(CONF_PANEL_CODE, None)
            return self.async_create_entry(title="", data=user_input)

        current_code = (
            self.config_entry.options.get(CONF_PANEL_CODE)
            or self.config_entry.data.get(CONF_PANEL_CODE)
            or ""
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
                    vol.Optional(
                        CONF_PANEL_CODE,
                        default=current_code,
                    ): str,
                }
            ),
        )
