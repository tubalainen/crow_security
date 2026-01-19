"""Config flow for Crow Shepherd integration."""
from __future__ import annotations

import logging
import re
from typing import Any

import crow_security_ng as crow
from crow_security_ng import ResponseError
import voluptuous as vol

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
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_PANEL_MAC): str,
    }
)


def normalize_mac_address(mac: str) -> str:
    """Normalize MAC address by removing separators and converting to lowercase.
    
    Accepts formats like:
    - AA:BB:CC:DD:EE:FF
    - AA-BB-CC-DD-EE-FF
    - AABBCCDDEEFF
    - aa:bb:cc:dd:ee:ff
    - AA BB CC DD EE FF
    
    Returns: aabbccddeeff (lowercase, no separators)
    """
    # Remove all common separators and whitespace
    normalized = re.sub(r'[:\-\s.]', '', mac)
    # Convert to lowercase
    normalized = normalized.lower()
    return normalized


def format_mac_for_display(mac: str) -> str:
    """Format MAC address for display (XX:XX:XX:XX:XX:XX)."""
    normalized = normalize_mac_address(mac)
    if len(normalized) == 12:
        return ':'.join(normalized[i:i+2] for i in range(0, 12, 2)).upper()
    return mac


def is_valid_mac(mac: str) -> bool:
    """Check if the MAC address is valid (12 hex characters after normalization)."""
    normalized = normalize_mac_address(mac)
    return bool(re.match(r'^[0-9a-f]{12}$', normalized))


class CrowShepherdConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Crow Shepherd."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._email: str | None = None
        self._password: str | None = None
        self._panel_mac: str | None = None
        self._session: crow.Session | None = None

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step - user credentials and panel MAC."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._email = user_input[CONF_EMAIL]
            self._password = user_input[CONF_PASSWORD]
            raw_mac = user_input[CONF_PANEL_MAC]
            
            # Normalize the MAC address
            self._panel_mac = normalize_mac_address(raw_mac)
            
            # Validate MAC format
            if not is_valid_mac(raw_mac):
                errors["base"] = "invalid_mac"
            else:
                try:
                    # Create session and try to get the panel
                    session = crow.Session(self._email, self._password)
                    panel = await session.get_panel(self._panel_mac)
                    
                    if panel is None:
                        errors["base"] = "no_panel"
                    else:
                        # Set unique ID based on email and panel MAC
                        await self.async_set_unique_id(f"{self._email}_{self._panel_mac}")
                        self._abort_if_unique_id_configured()

                        # Get panel name for entry title
                        panel_name = panel.name if panel.name else DEFAULT_NAME

                        return self.async_create_entry(
                            title=panel_name,
                            data={
                                CONF_EMAIL: self._email,
                                CONF_PASSWORD: self._password,
                                CONF_PANEL_MAC: self._panel_mac,
                            },
                        )
                        
                except ResponseError as err:
                    _LOGGER.error("Crow API error: %s - %s", err.status_code, err)
                    if err.status_code == 401 or err.status_code == 403:
                        errors["base"] = "invalid_auth"
                    elif err.status_code == 404:
                        errors["base"] = "no_panel"
                    else:
                        errors["base"] = "cannot_connect"
                except Exception as err:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception: %s", err)
                    errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "mac_format": "AABBCCDDEEFF or AA:BB:CC:DD:EE:FF",
            },
        )

    async def async_step_reauth(
        self,
        entry_data: dict[str, Any],
    ) -> ConfigFlowResult:
        """Handle reauthorization."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle reauthorization confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Test credentials
                session = crow.Session(
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD]
                )
                
                entry = self._get_reauth_entry()
                panel = await session.get_panel(entry.data[CONF_PANEL_MAC])
                
                if panel is None:
                    errors["base"] = "no_panel"
                else:
                    # Update the config entry
                    return self.async_update_reload_and_abort(
                        entry,
                        data={
                            **entry.data,
                            CONF_EMAIL: user_input[CONF_EMAIL],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                        },
                    )
                
            except ResponseError as err:
                _LOGGER.error("Crow API error: %s", err)
                if err.status_code == 401 or err.status_code == 403:
                    errors["base"] = "invalid_auth"
                elif err.status_code == 404:
                    errors["base"] = "no_panel"
                else:
                    errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
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
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow for this handler."""
        return CrowShepherdOptionsFlowHandler(config_entry)


class CrowShepherdOptionsFlowHandler(OptionsFlow):
    """Handle options flow for Crow Shepherd."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

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
                        default=self.config_entry.data.get(CONF_PANEL_CODE, ""),
                    ): str,
                }
            ),
        )
