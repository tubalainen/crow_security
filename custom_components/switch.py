"""Switch platform for Crow Shepherd outputs."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_HUB, DOMAIN, OUTPUT_STATE_ON
from .hub import CrowHub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Crow Shepherd switches from config entry."""
    hub: CrowHub = hass.data[DOMAIN][entry.entry_id][DATA_HUB]

    entities: list[CrowShepherdOutputSwitch] = []

    # Get outputs from the hub
    outputs = await hub.get_outputs()
    
    for output in outputs:
        output_id = output.get("id") or output.get("outputId") or output.get("output_id")
        if output_id:
            entities.append(CrowShepherdOutputSwitch(hub, output))

    async_add_entities(entities)


class CrowShepherdOutputSwitch(SwitchEntity):
    """Representation of a Crow Shepherd output switch."""

    _attr_has_entity_name = True

    def __init__(self, hub: CrowHub, output_data: dict[str, Any]) -> None:
        """Initialize the output switch."""
        self._hub = hub
        self._output_data = output_data
        self._output_id = (
            output_data.get("id") or 
            output_data.get("outputId") or 
            output_data.get("output_id")
        )
        self._attr_unique_id = f"{hub.mac}_output_{self._output_id}"

    @property
    def output_id(self) -> str:
        """Return the output ID."""
        return self._output_id

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return (
            self._output_data.get("name") or 
            self._output_data.get("outputName") or 
            f"Output {self._output_id}"
        )

    @property
    def is_on(self) -> bool:
        """Return true if the output is on."""
        state = self._output_data.get("state") or self._output_data.get("status")
        
        if isinstance(state, bool):
            return state
        if isinstance(state, int):
            return state == 1
        if isinstance(state, str):
            return state.lower() in (OUTPUT_STATE_ON, "1", "true", "active", "activated")
        
        return False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._hub.mac)},
            name=self._hub.panel.name if self._hub.panel else "Crow Shepherd",
            manufacturer="Crow",
            model="Shepherd",
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = {
            "output_id": self._output_id,
            "output_name": self._output_data.get("name") or self._output_data.get("outputName"),
        }
        
        # Add output type if available
        output_type = self._output_data.get("type") or self._output_data.get("outputType")
        if output_type:
            attrs["output_type"] = output_type
        
        return attrs

    async def async_update(self) -> None:
        """Update output state."""
        outputs = await self._hub.get_outputs()
        
        for output in outputs:
            output_id = (
                output.get("id") or 
                output.get("outputId") or 
                output.get("output_id")
            )
            if output_id == self._output_id:
                self._output_data = output
                break

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the output on."""
        _LOGGER.debug("Turning on output %s", self._output_id)
        success = await self._hub.set_output_state(self._output_id, True)
        if success:
            self._output_data["state"] = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the output off."""
        _LOGGER.debug("Turning off output %s", self._output_id)
        success = await self._hub.set_output_state(self._output_id, False)
        if success:
            self._output_data["state"] = False
            self.async_write_ha_state()
