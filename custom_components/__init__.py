"""The Crow Shepherd integration."""
from __future__ import annotations

import logging

import crow_security_ng as crow
from crow_security_ng import ResponseError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import CONF_PANEL_MAC, DATA_HUB, DOMAIN
from .hub import CrowHub

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Crow Shepherd from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create the hub
    hub = CrowHub(entry.data, hass)

    try:
        # Initialize the panel connection
        await hub.init_panel()
    except ResponseError as err:
        _LOGGER.error("Crow API error: %s - %s", err.status_code, err)
        if err.status_code == 401 or err.status_code == 403:
            raise ConfigEntryAuthFailed(
                "Authentication failed. Please reconfigure the integration."
            ) from err
        raise ConfigEntryNotReady(f"Failed to connect: {err}") from err
    except Exception as err:
        _LOGGER.error("Unexpected error connecting to Crow Cloud: %s", err)
        raise ConfigEntryNotReady(f"Failed to connect: {err}") from err

    if hub.panel is None:
        raise ConfigEntryNotReady("Could not find panel with specified MAC address")

    # Store the hub
    hass.data[DOMAIN][entry.entry_id] = {DATA_HUB: hub}

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start WebSocket connection for real-time updates
    hass.loop.create_task(hub.ws_connect())

    # Register update listener for options
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > 2:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1:
        new_data = {**config_entry.data}
        
        # Migrate panel_id to panel_mac if necessary
        if "panel_id" in new_data and CONF_PANEL_MAC not in new_data:
            new_data[CONF_PANEL_MAC] = new_data.pop("panel_id")
        
        # Migrate username to email if necessary
        if "username" in new_data and CONF_EMAIL not in new_data:
            new_data[CONF_EMAIL] = new_data.pop("username")

        hass.config_entries.async_update_entry(
            config_entry,
            data=new_data,
            version=2,
        )

    _LOGGER.debug(
        "Migration to configuration version %s successful",
        config_entry.version,
    )

    return True
