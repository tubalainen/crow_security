"""Alarm control panel platform for Crow Shepherd."""
from __future__ import annotations

import logging
from typing import Any

from crow_security_ng import ResponseError

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_PANEL_MAC,
    ATTR_PANEL_NAME,
    DATA_HUB,
    DOMAIN,
    SET_STATE_MAP,
    STATE_MAP,
)
from .hub import CrowHub

_LOGGER = logging.getLogger(__name__)

# State mappings from API to Home Assistant
HA_STATE_MAP = {
    "armed": AlarmControlPanelState.ARMED_AWAY,
    "arm in progress": AlarmControlPanelState.ARMING,
    "stay arm in progress": AlarmControlPanelState.ARMING,
    "stay_armed": AlarmControlPanelState.ARMED_HOME,
    "disarmed": AlarmControlPanelState.DISARMED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Crow Shepherd alarm control panel from config entry."""
    hub: CrowHub = hass.data[DOMAIN][entry.entry_id][DATA_HUB]
    
    alarms = []
    areas = await hub.get_areas()
    
    for area in areas:
        alarms.append(CrowShepherdAlarmControlPanel(hub, area))
    
    async_add_entities(alarms)


class CrowShepherdAlarmControlPanel(AlarmControlPanelEntity):
    """Representation of a Crow Shepherd alarm control panel."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
    )

    def __init__(self, hub: CrowHub, area: dict[str, Any]) -> None:
        """Initialize the alarm control panel."""
        self._hub = hub
        self._panel = hub.panel
        self._area = area
        
        # Use DISARMED as fallback state
        self._state = HA_STATE_MAP.get(
            self._area.get("state"), AlarmControlPanelState.DISARMED
        )
        _LOGGER.debug("Initialized alarm state for %s: %s", self.name, self._state)

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._hub.mac}_{self._area.get('id', 'area')}"

    @property
    def name(self) -> str:
        """Return the name of the device."""
        panel_name = self._panel.name if self._panel else "Crow"
        area_name = self._area.get("name", "Alarm")
        return f"{panel_name} {area_name}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._hub.mac)},
            name=self._panel.name if self._panel else "Crow Shepherd",
            manufacturer="Crow",
            model="Shepherd",
        )

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the alarm."""
        return self._state

    @property
    def code_format(self) -> CodeFormat | None:
        """Return the format of the code."""
        return CodeFormat.NUMBER

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            ATTR_PANEL_MAC: self._hub.mac,
            ATTR_PANEL_NAME: self._panel.name if self._panel else None,
            "area_id": self._area.get("id"),
            "area_name": self._area.get("name"),
            "raw_state": self._area.get("state"),
        }

    async def async_update(self) -> None:
        """Update alarm status."""
        area = await self._hub.get_area(self._area.get("id"))
        
        _LOGGER.debug("Area type is %s", type(area))
        
        if area is not None and isinstance(area, dict):
            self._area = area
        
        _LOGGER.debug("Updating Crow area %s", self._area.get("name"))

        # Log the current state before updating
        received_state = self._area.get("state")
        _LOGGER.debug("Current state before update: %s", received_state)

        # Log unknown state for debugging
        if received_state not in HA_STATE_MAP:
            _LOGGER.warning(
                "Unknown alarm state received: %s. Mapping to DISARMED.",
                received_state
            )

        # Use DISARMED as fallback state if the state is unknown
        self._state = HA_STATE_MAP.get(received_state, AlarmControlPanelState.DISARMED)
        _LOGGER.debug("State successfully updated: %s", self._state)

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        await self._async_set_arm_state(AlarmControlPanelState.DISARMED, code)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        await self._async_set_arm_state(AlarmControlPanelState.ARMED_HOME, code)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self._async_set_arm_state(AlarmControlPanelState.ARMED_AWAY, code)

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Trigger alarm - not supported."""
        pass

    async def async_alarm_arm_custom_bypass(self, code: str | None = None) -> None:
        """Custom bypass command - not supported."""
        pass

    async def _async_set_arm_state(
        self, state: AlarmControlPanelState, code: str | None = None
    ) -> None:
        """Send set arm state command."""
        # Map HA state to API command
        api_command_map = {
            AlarmControlPanelState.ARMED_HOME: "stay",
            AlarmControlPanelState.ARMED_AWAY: "arm",
            AlarmControlPanelState.DISARMED: "disarm",
        }
        
        api_command = api_command_map.get(state, "disarm")
        _LOGGER.info("Crow set arm state %s (API: %s)", state, api_command)
        
        try:
            area = await self._panel.set_area_state(
                self._area.get("id"), api_command
            )
            if area:
                self._area = area
        except ResponseError as err:
            if err.status_code == 408:
                _LOGGER.debug("Received expected 408 error when setting arm state.")
            else:
                _LOGGER.error("Error setting arm state: %s", err)
        except Exception as err:
            _LOGGER.error("Unexpected error setting arm state: %s", err)
