"""Sensor platform for Crow Shepherd measurements and panel connectivity."""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from crow_security_ng.models import ConnectionInterface, Measurement

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .connectivity import (
    ConnectivityData,
    CrowShepherdConnectivityCoordinator,
    CrowShepherdConnectivityEntity,
)
from .const import DATA_CONNECTIVITY, DATA_COORDINATOR, DOMAIN
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

    entities: list[CrowShepherdMeasurementSensor] = []
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

    async_add_entities(entities)

    connectivity: CrowShepherdConnectivityCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ][DATA_CONNECTIVITY]
    async_add_entities(
        CrowShepherdConnectivitySensor(connectivity, description)
        for description in CONNECTIVITY_SENSORS
    )


_INTERFACE_STATES: dict[ConnectionInterface, str] = {
    ConnectionInterface.ETHERNET: "ethernet",
}


def _connection_type(data: ConnectivityData) -> str | None:
    if data.connection is None or data.connection.interface is None:
        return None
    return _INTERFACE_STATES.get(data.connection.interface, "unknown")


@dataclass(frozen=True, kw_only=True)
class CrowConnectivitySensorDescription(SensorEntityDescription):
    """Describes a panel connectivity sensor."""

    value_fn: Callable[[ConnectivityData], str | int | datetime | None]
    available_fn: Callable[[ConnectivityData], bool] = lambda data: True
    attributes_fn: Callable[[ConnectivityData], dict[str, Any]] | None = None


CONNECTIVITY_SENSORS: tuple[CrowConnectivitySensorDescription, ...] = (
    CrowConnectivitySensorDescription(
        key="last_heartbeat",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.last_heartbeat,
    ),
    CrowConnectivitySensorDescription(
        key="connection_type",
        device_class=SensorDeviceClass.ENUM,
        options=["ethernet", "unknown"],
        value_fn=_connection_type,
        available_fn=lambda data: data.connection is not None,
        attributes_fn=lambda data: {
            "interface_code": int(data.connection.interface)
            if data.connection and data.connection.interface is not None
            else None
        },
    ),
    CrowConnectivitySensorDescription(
        key="gsm_status",
        value_fn=lambda data: data.gsm.status_desc if data.gsm else None,
        available_fn=lambda data: data.gsm is not None,
    ),
    CrowConnectivitySensorDescription(
        key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.wifi.rssi if data.wifi else None,
        available_fn=lambda data: data.wifi is not None and bool(data.wifi.enabled),
    ),
    CrowConnectivitySensorDescription(
        key="gsm_signal",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.gsm.rssi if data.gsm else None,
        available_fn=lambda data: data.gsm is not None and bool(data.gsm.enabled),
    ),
)


class CrowShepherdConnectivitySensor(CrowShepherdConnectivityEntity, SensorEntity):
    """Diagnostic sensor for panel connectivity."""

    entity_description: CrowConnectivitySensorDescription

    def __init__(
        self,
        coordinator: CrowShepherdConnectivityCoordinator,
        description: CrowConnectivitySensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data is not None
            and self.entity_description.available_fn(self.coordinator.data)
        )

    @property
    def native_value(self) -> str | int | datetime | None:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        fn = self.entity_description.attributes_fn
        if fn is None or self.coordinator.data is None:
            return None
        return fn(self.coordinator.data)


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
