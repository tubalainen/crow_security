"""Sensor platform for Crow Shepherd measurements and status."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_HUB, DOMAIN
from .hub import CrowHub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Crow Shepherd sensors from config entry."""
    hub: CrowHub = hass.data[DOMAIN][entry.entry_id][DATA_HUB]

    entities: list[SensorEntity] = []

    # Get measurements from the hub
    measurements = await hub.get_measurements()
    
    for measurement in measurements:
        measurement_id = (
            measurement.get("id") or 
            measurement.get("measurementId") or 
            measurement.get("_id")
        )
        if measurement_id:
            entities.append(CrowShepherdMeasurementSensor(hub, measurement))

    # Add zone battery sensors
    zones = await hub.get_devices()
    for zone in zones:
        zone_id = zone.get("id") or zone.get("zoneId") or zone.get("zone_id")
        battery = (
            zone.get("battery") or 
            zone.get("batteryLevel") or 
            zone.get("battery_level")
        )
        if zone_id and battery is not None:
            entities.append(CrowShepherdZoneBatterySensor(hub, zone))

    async_add_entities(entities)


class CrowShepherdMeasurementSensor(SensorEntity):
    """Sensor showing measurements from the alarm system."""

    _attr_has_entity_name = True

    def __init__(self, hub: CrowHub, measurement_data: dict[str, Any]) -> None:
        """Initialize the sensor."""
        self._hub = hub
        self._measurement_data = measurement_data
        self._measurement_id = (
            measurement_data.get("id") or 
            measurement_data.get("measurementId") or 
            measurement_data.get("_id")
        )
        self._attr_unique_id = f"{hub.mac}_measurement_{self._measurement_id}"
        
        # Set device class based on measurement type
        measurement_type = measurement_data.get("type", "").lower()
        if "temperature" in measurement_type or "temp" in measurement_type:
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = "°C"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif "humidity" in measurement_type:
            self._attr_device_class = SensorDeviceClass.HUMIDITY
            self._attr_native_unit_of_measurement = "%"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif "battery" in measurement_type:
            self._attr_device_class = SensorDeviceClass.BATTERY
            self._attr_native_unit_of_measurement = "%"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif "signal" in measurement_type or "rssi" in measurement_type:
            self._attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
            self._attr_native_unit_of_measurement = "dBm"
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return (
            self._measurement_data.get("name") or 
            self._measurement_data.get("measurementName") or 
            f"Measurement {self._measurement_id}"
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
    def native_value(self) -> float | int | str | None:
        """Return the measurement value."""
        value = self._measurement_data.get("value") or self._measurement_data.get("currentValue")
        
        if value is None:
            return None
        
        try:
            # Try to return as number
            return float(value)
        except (ValueError, TypeError):
            return str(value)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = {
            "measurement_id": self._measurement_id,
            "measurement_type": self._measurement_data.get("type"),
        }
        
        # Add zone info if available
        zone_id = self._measurement_data.get("zoneId") or self._measurement_data.get("zone_id")
        if zone_id:
            attrs["zone_id"] = zone_id
        
        return attrs

    async def async_update(self) -> None:
        """Update measurement state."""
        measurements = await self._hub.get_measurements()
        
        for measurement in measurements:
            measurement_id = (
                measurement.get("id") or 
                measurement.get("measurementId") or 
                measurement.get("_id")
            )
            if measurement_id == self._measurement_id:
                self._measurement_data = measurement
                break


class CrowShepherdZoneBatterySensor(SensorEntity):
    """Sensor showing zone battery level."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hub: CrowHub, zone_data: dict[str, Any]) -> None:
        """Initialize the sensor."""
        self._hub = hub
        self._zone_data = zone_data
        self._zone_id = (
            zone_data.get("id") or 
            zone_data.get("zoneId") or 
            zone_data.get("zone_id")
        )
        self._attr_unique_id = f"{hub.mac}_zone_{self._zone_id}_battery"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        zone_name = (
            self._zone_data.get("name") or 
            self._zone_data.get("zoneName") or 
            f"Zone {self._zone_id}"
        )
        return f"{zone_name} Battery"

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
    def native_value(self) -> int | None:
        """Return the battery level."""
        battery = (
            self._zone_data.get("battery") or 
            self._zone_data.get("batteryLevel") or 
            self._zone_data.get("battery_level")
        )
        
        if battery is None:
            return None
        
        try:
            return int(float(battery))
        except (ValueError, TypeError):
            return None

    async def async_update(self) -> None:
        """Update zone battery state."""
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
