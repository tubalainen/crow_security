"""Sensor platform for Crow Shepherd measurements."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from crow_security_ng.models import Measurement

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


@dataclass(frozen=True)
class _DectConfig:
    """Configuration for one DECT interface type."""

    field: str                          # Attribute name on Measurement
    device_class: SensorDeviceClass | None
    unit: str | None
    label: str                          # Appended to zone/output name


# Maps dect_interface int → sensor configuration.
# Only well-documented interface types are listed; anything else is skipped.
_DECT_MAP: dict[int, _DectConfig] = {
    32533: _DectConfig("temperature",  SensorDeviceClass.TEMPERATURE,          "°C",  "Temperature"),
    32532: _DectConfig("humidity",     SensorDeviceClass.HUMIDITY,             "%",   "Humidity"),
    32535: _DectConfig("air_pressure", SensorDeviceClass.ATMOSPHERIC_PRESSURE, "hPa", "Air Pressure"),
    61:    _DectConfig("gas_level",    None,                                   None,  "Gas Level"),
}


def _device_name(coordinator: CrowShepherdCoordinator, device_id: int, device_type: str) -> str:
    """Look up the human-readable name of a zone or output by its device_id."""
    if device_type == "zone":
        zone = next(
            (z for z in coordinator.data.zones if z.id == device_id), None
        )
        if zone:
            return zone.name
    elif device_type == "output":
        output = next(
            (o for o in coordinator.data.outputs if o.id == device_id), None
        )
        if output:
            return output.name
    return f"{device_type.capitalize()} {device_id}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities from a config entry."""
    coordinator: CrowShepherdCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    entities: list[CrowShepherdMeasurementSensor | CrowShepherdBatteryVoltageSensor] = []
    for measurement in coordinator.data.measurements:
        dect_interface = measurement.dect_interface
        if dect_interface not in _DECT_MAP:
            _LOGGER.debug(
                "Skipping unknown dect_interface %s for device %s/%s",
                dect_interface,
                measurement.device_type,
                measurement.device_id,
            )
            continue
        entities.append(CrowShepherdMeasurementSensor(coordinator, measurement))

    # Battery voltage sensors — zones
    for zone in coordinator.data.zones:
        if zone.battery_voltage is not None:
            entities.append(
                CrowShepherdBatteryVoltageSensor(coordinator, zone.id, "zone")
            )

    # Battery voltage sensors — outputs
    for output in coordinator.data.outputs:
        if output.battery_voltage is not None:
            entities.append(
                CrowShepherdBatteryVoltageSensor(coordinator, output.id, "output")
            )

    async_add_entities(entities)


class CrowShepherdBatteryVoltageSensor(
    CoordinatorEntity[CrowShepherdCoordinator],
    SensorEntity,
):
    """Sensor showing the battery voltage of a Crow zone or output device."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_native_unit_of_measurement = "V"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 3

    def __init__(
        self,
        coordinator: CrowShepherdCoordinator,
        device_id: int,
        device_type: str,
    ) -> None:
        """Initialise entity."""
        super().__init__(coordinator)

        self._device_id = device_id
        self._device_type = device_type

        self._attr_unique_id = (
            f"{coordinator.hub.mac}"
            f"_{self._device_type}"
            f"_{self._device_id}"
            f"_battery_voltage"
        )

        device_name = _device_name(coordinator, self._device_id, self._device_type)
        self._attr_name = f"{device_name} Battery Voltage"

    @property
    def device_info(self) -> DeviceInfo:
        """Group under the panel device."""
        panel = self.coordinator.hub.panel
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.hub.mac)},
            name=panel.name,
            manufacturer="Crow",
            model=panel.firmware_version or "Alarm Panel",
        )

    @property
    def native_value(self) -> float | None:
        """Return the current battery voltage."""
        if self._device_type == "zone":
            obj = next(
                (z for z in self.coordinator.data.zones if z.id == self._device_id),
                None,
            )
        else:
            obj = next(
                (o for o in self.coordinator.data.outputs if o.id == self._device_id),
                None,
            )
        return obj.battery_voltage if obj is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "device_id": self._device_id,
            "device_type": self._device_type,
        }


class CrowShepherdMeasurementSensor(
    CoordinatorEntity[CrowShepherdCoordinator],
    SensorEntity,
):
    """Sensor showing one DECT measurement value from a Crow zone or output."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: CrowShepherdCoordinator,
        measurement: Measurement,
    ) -> None:
        """Initialise entity.

        The triple (device_id, device_type, dect_interface) uniquely identifies
        one sensor reading within a panel.
        """
        super().__init__(coordinator)

        self._device_id: int = measurement.device_id
        self._device_type: str = measurement.device_type
        self._dect_interface: int = measurement.dect_interface

        cfg = _DECT_MAP[self._dect_interface]

        # Stable unique_id: mac + device type + device id + interface type
        self._attr_unique_id = (
            f"{coordinator.hub.mac}"
            f"_{self._device_type}"
            f"_{self._device_id}"
            f"_{self._dect_interface}"
        )

        # Human-readable name: "Garage Temperature", "Cam Hall OV Humidity", etc.
        device_name = _device_name(coordinator, self._device_id, self._device_type)
        self._attr_name = f"{device_name} {cfg.label}"

        if cfg.device_class is not None:
            self._attr_device_class = cfg.device_class
        if cfg.unit is not None:
            self._attr_native_unit_of_measurement = cfg.unit

    @property
    def device_info(self) -> DeviceInfo:
        """Group under the panel device."""
        panel = self.coordinator.hub.panel
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.hub.mac)},
            name=panel.name,
            manufacturer="Crow",
            model=panel.firmware_version or "Alarm Panel",
        )

    def _get_measurement(self) -> Measurement | None:
        """Return the current Measurement from coordinator data.

        Matches on all three identifying fields: device_id, device_type,
        and dect_interface.
        """
        return next(
            (
                m
                for m in self.coordinator.data.measurements
                if (
                    m.device_id == self._device_id
                    and m.device_type == self._device_type
                    and m.dect_interface == self._dect_interface
                )
            ),
            None,
        )

    @property
    def native_value(self) -> float | int | None:
        """Return the sensor value by reading the correct field for this interface type."""
        measurement = self._get_measurement()
        if measurement is None:
            return None
        cfg = _DECT_MAP[self._dect_interface]
        return getattr(measurement, cfg.field, None)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        measurement = self._get_measurement()
        if measurement is None:
            return {}
        return {
            "device_id": self._device_id,
            "device_type": self._device_type,
            "dect_interface": self._dect_interface,
            "panel_time": measurement.panel_time.isoformat()
            if measurement.panel_time
            else None,
        }
