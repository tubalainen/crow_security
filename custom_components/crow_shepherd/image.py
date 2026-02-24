"""Image platform for Crow Shepherd PIR camera zones."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from crow_security_ng.models import Zone

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import CrowShepherdCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up image entities from a config entry."""
    coordinator: CrowShepherdCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    entities = [
        CrowShepherdCameraImage(coordinator, zone)
        for zone in coordinator.data.zones
        if zone.is_camera
    ]
    async_add_entities(entities)

    platform = async_get_current_platform()
    platform.async_register_entity_service(
        "fetch_camera_snapshot",
        {},
        "async_fetch_snapshot",
    )


class CrowShepherdCameraImage(
    CoordinatorEntity[CrowShepherdCoordinator],
    ImageEntity,
):
    """Image entity showing the latest on-demand snapshot from a PIR camera zone."""

    _attr_has_entity_name = True
    _attr_content_type = "image/jpeg"

    def __init__(
        self,
        coordinator: CrowShepherdCoordinator,
        zone: Zone,
    ) -> None:
        """Initialise entity."""
        super().__init__(coordinator)
        self._zone_id = zone.id
        self._attr_unique_id = f"{coordinator.hub.mac}_zone_{zone.id}_image"
        self._attr_name = f"{zone.name} Snapshot"
        self._image_bytes: bytes | None = None
        self._image_last_updated: datetime | None = None
        self._last_picture_id: int | None = None
        self._last_picture_type: str | None = None
        self._last_panel_time: str | None = None

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
    def image_last_updated(self) -> datetime | None:
        """Return when the stored image was last fetched."""
        return self._image_last_updated

    async def async_image(self) -> bytes | None:
        """Return the stored JPEG bytes."""
        return self._image_bytes

    async def async_fetch_snapshot(self) -> None:
        """Fetch the latest snapshot from the panel and store it.

        Called by the crow_shepherd.fetch_camera_snapshot action.
        """
        try:
            pics = await self.coordinator.hub.panel.get_zone_pictures(self._zone_id)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Zone %s: could not list pictures: %s", self._zone_id, err)
            return

        if not pics:
            _LOGGER.warning("Zone %s: no pictures available yet", self._zone_id)
            return

        pic = pics[-1]

        try:
            self._image_bytes = await self.coordinator.hub.session.get_picture_bytes(pic)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Zone %s: could not download picture %s: %s",
                self._zone_id,
                pic.id,
                err,
            )
            return

        self._image_last_updated = pic.created or dt_util.utcnow()
        self._last_picture_id = pic.id
        self._last_picture_type = "alarm" if pic.picture_type == 1 else "manual"
        self._last_panel_time = pic.panel_time.isoformat() if pic.panel_time else None
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if self._last_picture_id is None:
            return {}
        return {
            "picture_id": self._last_picture_id,
            "picture_type": self._last_picture_type,
            "panel_time": self._last_panel_time,
        }
