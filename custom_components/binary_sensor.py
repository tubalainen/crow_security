"""Binary sensor platform for Crow Shepherd zones."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_BATTERY_LEVEL,
    ATTR_SIGNAL_STRENGTH,
    ATTR_ZONE_ID,
    ATTR_ZONE_NAME,
    ATTR_ZONE_TYPE,
    DATA_HUB,
    DOMAIN,
    ZONE_STATE_ALARM,
    ZONE_STATE_OK,
    ZONE_STATE_OPEN,
    ZONE_STATE_TAMPER,
    ZONE_STATE_TROUBLE,
    ZONE_TYPE_DOOR,
    ZONE_TYPE_GAS,
    ZONE_TYPE_GLASS,
    ZONE_TYPE_MEDICAL,
    ZONE_TYPE_MOTION,
    ZONE_TYPE_PANIC,
    ZONE_TYPE_SMOKE,
    ZONE_TYPE_TEMPERATURE,
    ZONE_TYPE_WATER,
    ZONE_TYPE_WINDOW,
)
from .hub import CrowHub

_LOGGER = logging.getLogger(__name__)

# Map zone types to device classes
ZONE_TYPE_TO_DEVICE_CLASS = {
    ZONE_TYPE_DOOR: BinarySensorDeviceClass.DOOR,
    ZONE_TYPE_WINDOW: BinarySensorDeviceClass.WINDOW,
    ZONE_TYPE_MOTION: BinarySensorDeviceClass.MOTION,
    ZONE_TYPE_SMOKE: BinarySensorDeviceClass.SMOKE,
    ZONE_TYPE_WATER: BinarySensorDeviceClass.MOISTURE,
    ZONE_TYPE_GLASS: BinarySensorDeviceClass.VIBRATION,
    ZONE_TYPE_PANIC: BinarySensorDeviceClass.SAFETY,
    ZONE_TYPE_MEDICAL: BinarySensorDeviceClass.SAFETY,
    ZONE_TYPE_GAS: BinarySensorDeviceClass.GAS,
    ZONE_TYPE_TEMPERATURE: BinarySensorDeviceClass.HEAT,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Crow Shepherd binary sensors from config entry."""
    hub: CrowHub = hass.data[DOMAIN][entry.entry_id][DATA_HUB]

    entities: list[CrowShepherdZoneSensor] = []

    # Get zones from the hub
    zones = await hub.get_devices()

    for zone in zones:
        zone_id = zone.get("id") or zone.get("zoneId") or zone.get("zone_id")
        if zone_id:
            entities.append(CrowShepherdZoneSensor(hub, zone))

    async_add_entities(entities)


class CrowShepherdZoneSensor(BinarySensorEntity):
    """Representation of a Crow Shepherd zone sensor."""

    _attr_has_entity_name = True

    def __init__(self, hub: CrowHub, zone_data: dict[str, Any]) -> None:
        """Initialize the zone sensor."""
        self._hub = hub
        self._zone_data = zone_data
        self._zone_id = (
            zone_data.get("id") or 
            zone_data.get("zoneId") or 
            zone_data.get("zone_id")
        )
        self._attr_unique_id = f"{hub.mac}_zone_{self._zone_id}"
        
        # Set device class based on zone type
        zone_type = self._get_zone_type()
        self._attr_device_class = ZONE_TYPE_TO_DEVICE_CLASS.get(
            zone_type, BinarySensorDeviceClass.OPENING
        )

    @property
    def zone_id(self) -> str:
        """Return the zone ID."""
        return self._zone_id

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return (
            self._zone_data.get("name") or 
            self._zone_data.get("zoneName") or 
            f"Zone {self._zone_id}"
        )

    def _get_zone_type(self) -> str:
        """Get the zone type."""
        zone_type = (
            self._zone_data.get("type") or 
            self._zone_data.get("zoneType") or 
            self._zone_data.get("zone_type", "generic")
        )
        return zone_type.lower() if isinstance(zone_type, str) else "generic"

    @property
    def is_on(self) -> bool:
        """Return true if the zone is triggered/open."""
        state = self._zone_data.get("state") or self._zone_data.get("status", ZONE_STATE_OK)
        
        if isinstance(state, str):
            state = state.lower()
        
        # Zone is "on" (triggered) if it's open, in alarm, tampered, or has trouble
        return state in (
            ZONE_STATE_OPEN,
            ZONE_STATE_ALARM,
            ZONE_STATE_TAMPER,
            ZONE_STATE_TROUBLE,
            "1",
            "active",
            "triggered",
            "violated",
        )

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
            ATTR_ZONE_ID: self._zone_id,
            ATTR_ZONE_NAME: self._zone_data.get("name") or self._zone_data.get("zoneName"),
            ATTR_ZONE_TYPE: self._get_zone_type(),
        }
        
        # Add battery level if available
        battery = (
            self._zone_data.get("battery") or 
            self._zone_data.get("batteryLevel") or 
            self._zone_data.get("battery_level")
        )
        if battery is not None:
            attrs[ATTR_BATTERY_LEVEL] = battery
        
        # Add signal strength if available
        signal = (
            self._zone_data.get("signal") or 
            self._zone_data.get("signalStrength") or 
            self._zone_data.get("signal_strength") or 
            self._zone_data.get("rssi")
        )
        if signal is not None:
            attrs[ATTR_SIGNAL_STRENGTH] = signal
        
        # Add bypass status
        bypassed = self._zone_data.get("bypassed") or self._zone_data.get("bypass", False)
        attrs["bypassed"] = bypassed
        
        # Add tamper status
        state = self._zone_data.get("state") or self._zone_data.get("status", "")
        if isinstance(state, str):
            attrs["tamper"] = state.lower() == ZONE_STATE_TAMPER
        
        # Add low battery status
        if battery is not None:
            try:
                attrs["low_battery"] = float(battery) < 20
            except (ValueError, TypeError):
                attrs["low_battery"] = str(battery).lower() in ("low", "critical", "1")
        
        return attrs

    async def async_update(self) -> None:
        """Update zone state."""
        zones = await self._hub.get_devices()
        
        for zone in zones:
            zone_id = (
                zone.get("id") or 
                zone.get("zoneId") or 
                zone.get("zone_id")
            )
            if zone_id == self._zone_id:
                self._zone_data = zone
                break
