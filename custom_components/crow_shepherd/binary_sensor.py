"""Binary sensor platform for Crow Shepherd zones."""
from __future__ import annotations

import logging
from typing import Any

from crow_security_ng.models import Zone

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import CrowShepherdCoordinator

_LOGGER = logging.getLogger(__name__)

# Mapping of Crow zone_type integers to HA BinarySensorDeviceClass.
# Add entries as additional types are confirmed from Crow documentation.
_ZONE_TYPE_TO_DEVICE_CLASS: dict[int, BinarySensorDeviceClass] = {
    55: BinarySensorDeviceClass.MOTION,  # Smart cam / PIR camera
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities from a config entry."""
    coordinator: CrowShepherdCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    async_add_entities(
        CrowShepherdZoneSensor(coordinator, zone)
        for zone in coordinator.data.zones
    )


class CrowShepherdZoneSensor(
    CoordinatorEntity[CrowShepherdCoordinator],
    BinarySensorEntity,
):
    """Binary sensor representing a Crow zone."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CrowShepherdCoordinator,
        zone: Zone,
    ) -> None:
        """Initialise entity."""
        super().__init__(coordinator)
        self._zone_id = zone.id
        self._attr_unique_id = f"{coordinator.hub.mac}_zone_{zone.id}"
        self._attr_name = zone.name
        self._attr_device_class = _ZONE_TYPE_TO_DEVICE_CLASS.get(
            zone.zone_type, BinarySensorDeviceClass.OPENING
        )

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

    def _get_zone(self) -> Zone | None:
        """Return the current Zone object from coordinator data."""
        return next(
            (z for z in self.coordinator.data.zones if z.id == self._zone_id),
            None,
        )

    @property
    def is_on(self) -> bool:
        """Return True when the zone is open/triggered.

        Zone.state is a bool in crow_security_ng: True = open/triggered.
        """
        zone = self._get_zone()
        return zone.state if zone is not None else False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        zone = self._get_zone()
        if zone is None:
            return {}
        return {
            "zone_id": zone.id,
            "zone_type": zone.zone_type,
            "bypassed": zone.bypass,
            "tamper": zone.tamper_alarm,
            "battery_low": zone.battery_low,
            "battery_voltage": zone.battery_voltage,
            "active": zone.active,
            "rssi": zone.rssi,
        }
