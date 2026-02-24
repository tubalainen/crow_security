"""The Crow Shepherd integration."""
from __future__ import annotations

import asyncio
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_PANEL_CODE,
    CONF_SCAN_INTERVAL,
    DATA_COORDINATOR,
    DATA_HUB,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import CrowShepherdCoordinator
from .hub import CrowHub

_LOGGER = logging.getLogger(__name__)

_WS_RECONNECT_DELAY = 30  # seconds between WebSocket reconnect attempts

BYPASS_ZONE_SCHEMA = vol.Schema(
    {
        vol.Required("zone_id"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required("bypass"): cv.boolean,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Crow Shepherd from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Build and connect the hub (raises ConfigEntryAuthFailed / ConfigEntryNotReady)
    hub = CrowHub.from_config_entry(entry.data, entry.options)
    await hub.async_connect()

    # Build coordinator and do the first data fetch
    update_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = CrowShepherdCoordinator(hass, hub, update_interval)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_HUB: hub,
        DATA_COORDINATOR: coordinator,
    }

    # Forward setup to all platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload on options change
    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    # Start WebSocket reconnect loop in the background
    ws_task = hass.async_create_background_task(
        _ws_loop(hass, entry.entry_id),
        name=f"crow_shepherd_ws_{entry.entry_id}",
    )
    hass.data[DOMAIN][entry.entry_id]["ws_task"] = ws_task

    # Register bypass_zone service (idempotent — only registers once)
    if not hass.services.has_service(DOMAIN, "bypass_zone"):
        hass.services.async_register(
            DOMAIN,
            "bypass_zone",
            _handle_bypass_zone,
            schema=BYPASS_ZONE_SCHEMA,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Cancel the WebSocket loop
    entry_data = hass.data[DOMAIN].get(entry.entry_id, {})
    ws_task: asyncio.Task | None = entry_data.get("ws_task")
    if ws_task and not ws_task.done():
        ws_task.cancel()
        try:
            await ws_task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass

    # Close the session
    hub: CrowHub | None = entry_data.get(DATA_HUB)
    if hub:
        await hub.async_close()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


# ---------------------------------------------------------------------------
# WebSocket reconnect loop
# ---------------------------------------------------------------------------

async def _ws_loop(hass: HomeAssistant, entry_id: str) -> None:
    """Keep the WebSocket connected, reconnecting after any failure."""
    while True:
        entry_data = hass.data.get(DOMAIN, {}).get(entry_id)
        if entry_data is None:
            return  # Entry was unloaded

        hub: CrowHub = entry_data[DATA_HUB]
        coordinator: CrowShepherdCoordinator = entry_data[DATA_COORDINATOR]

        async def _on_ws_message(msg: dict) -> None:
            _LOGGER.debug("WebSocket message received: %s", msg)
            coordinator.async_request_refresh()

        try:
            _LOGGER.debug("Starting WebSocket connection for panel %s", hub.mac)
            await hub.session.ws_connect(hub.mac, _on_ws_message)
            _LOGGER.debug("WebSocket connection closed for panel %s", hub.mac)
        except asyncio.CancelledError:
            return  # Clean shutdown
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "WebSocket error for panel %s: %s — reconnecting in %ss",
                hub.mac,
                err,
                _WS_RECONNECT_DELAY,
            )

        try:
            await asyncio.sleep(_WS_RECONNECT_DELAY)
        except asyncio.CancelledError:
            return


# ---------------------------------------------------------------------------
# bypass_zone service
# ---------------------------------------------------------------------------

async def _handle_bypass_zone(call: ServiceCall) -> None:
    """Handle the crow_shepherd.bypass_zone service call."""
    zone_id: int = call.data["zone_id"]
    bypass: bool = call.data["bypass"]
    hass: HomeAssistant = call.hass

    entry_data_list = hass.data.get(DOMAIN, {})
    if not entry_data_list:
        _LOGGER.error("bypass_zone: no Crow Shepherd entries found")
        return

    for entry_id, entry_data in entry_data_list.items():
        coordinator: CrowShepherdCoordinator | None = entry_data.get(DATA_COORDINATOR)
        if coordinator is None:
            continue
        try:
            await coordinator.hub.panel.set_zone_bypass(zone_id, bypass)
            await coordinator.async_request_refresh()
            _LOGGER.debug(
                "Zone %s bypass set to %s on panel %s",
                zone_id,
                bypass,
                coordinator.hub.mac,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Failed to set zone %s bypass on panel %s: %s",
                zone_id,
                coordinator.hub.mac,
                err,
            )


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    from homeassistant.const import CONF_EMAIL

    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > 2:
        return False

    if config_entry.version == 1:
        new_data = {**config_entry.data}
        if "panel_id" in new_data and "panel_mac" not in new_data:
            new_data["panel_mac"] = new_data.pop("panel_id")
        if "username" in new_data and CONF_EMAIL not in new_data:
            new_data[CONF_EMAIL] = new_data.pop("username")
        hass.config_entries.async_update_entry(
            config_entry, data=new_data, version=2
        )

    _LOGGER.debug("Migration to version %s successful", config_entry.version)
    return True
