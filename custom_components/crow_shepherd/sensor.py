"""Sensor platform for Crow Shepherd measurements."""
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
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import CrowShepherdCoordinator

_LOGGER = logging.getLogger(__name__)

# Map measurement type strings to HA SensorDeviceClass + unit
_MEASUREMENT_TYPE_MAP: dict[str, tuple[SensorDeviceClass, str]] = {
    "temperature": (SensorDeviceClass.TEMPERATURE, "°C"),
    "temp": (SensorDeviceClass.TEMPERATURE, "°C"),
    "humidity": (SensorDeviceClass.HUMIDITY, "%"),
    "battery": (SensorDeviceClass.BATTERY, "%"),
    "signal": (SensorDeviceClass.SIGNAL_STRENGTH, "dBm"),
    "rssi": (SensorDeviceClass.SIGNAL_STRENGTH, "dBm"),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities from a config entry."""
    coordinator: CrowShepherdCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    async_add_entities(
        CrowShepherdMeasurementSensor(coordinator, idx)
        for idx, _ in enumerate(coordinator.data.measurements)
    )


class CrowShepherdMeasurementSensor(
    CoordinatorEntity[CrowShepherdCoordinator],
    SensorEntity,
):
    """Sensor showing a measurement value from the Crow panel."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: CrowShepherdCoordinator,
        index: int,
    ) -> None:
        """Initialise entity using the list index to identify the measurement."""
        super().__init__(coordinator)
        # Use index + stable initial values to set the unique_id and display name
        measurement = coordinator.data.measurements[index]
        measurement_id = getattr(measurement, "id", index)
        self._measurement_id = measurement_id
        self._attr_unique_id = f"{coordinator.hub.mac}_measurement_{measurement_id}"
        self._attr_name = getattr(measurement, "name", f"Measurement {measurement_id}")

        # Set device class and unit from measurement type
        mtype = str(getattr(measurement, "type", "")).lower()
        for key, (device_class, unit) in _MEASUREMENT_TYPE_MAP.items():
            if key in mtype:
                self._attr_device_class = device_class
                self._attr_native_unit_of_measurement = unit
                break

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        panel = self.coordinator.hub.panel
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.hub.mac)},
            name=panel.name,
            manufacturer="Crow",
            model=panel.firmware_version or "Alarm Panel",
        )

    def _get_measurement(self) -> Any | None:
        """Return the current measurement object from coordinator data."""
        return next(
            (
                m
                for m in self.coordinator.data.measurements
                if getattr(m, "id", None) == self._measurement_id
            ),
            None,
        )

    @property
    def native_value(self) -> float | str | None:
        """Return the measurement value."""
        measurement = self._get_measurement()
        if measurement is None:
            return None
        value = getattr(measurement, "value", None)
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return str(value)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        measurement = self._get_measurement()
        if measurement is None:
            return {}
        return {
            "measurement_id": self._measurement_id,
            "measurement_type": getattr(measurement, "type", None),
        }
