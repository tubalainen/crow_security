"""Image platform for Crow Shepherd PIR camera zones."""
from __future__ import annotations

import asyncio
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

from .const import CONF_CAMERA_ZONE_IDS, DATA_COORDINATOR, DOMAIN
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
    camera_zone_ids: set[int] = set(entry.options.get(CONF_CAMERA_ZONE_IDS, []))
    entities = [
        CrowShepherdCameraImage(hass, coordinator, zone)
        for zone in coordinator.data.zones
        if zone.is_camera or zone.id in camera_zone_ids
    ]
    async_add_entities(entities)

    if not entities:
        _LOGGER.warning(
            "No PIR camera image entities created. "
            "If your panel has PIR cameras, go to Settings \u2192 Devices & Services "
            "\u2192 Crow Shepherd \u2192 Configure and select the camera zones under "
            "'PIR Camera Zones', then reload the integration."
        )

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
        hass: HomeAssistant,
        coordinator: CrowShepherdCoordinator,
        zone: Zone,
    ) -> None:
        """Initialise entity."""
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)
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

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass.

        Calls super() first so CoordinatorEntity and ImageEntity both initialize
        (including access_tokens), then silently fetches the latest stored picture.
        """
        await super().async_added_to_hass()
        await self.async_fetch_snapshot(silent=True)

    @property
    def image_last_updated(self) -> datetime | None:
        """Return when the stored image was last fetched."""
        return self._image_last_updated

    async def async_image(self) -> bytes | None:
        """Return the stored JPEG bytes."""
        return self._image_bytes

    async def async_fetch_snapshot(self, *, silent: bool = False) -> None:
        """Fetch a snapshot from the panel and update the entity.

        silent=True (startup): retrieve the latest stored picture — no new capture.
        silent=False (user action): trigger a new capture, then poll until it appears.
        """
        panel = self.coordinator.hub.panel
        session = self.coordinator.hub.session

        if not silent:
            # ── Explicit user action: trigger a new capture ───────────────
            # Record the current newest picture ID so we know when a new one arrives.
            try:
                existing = await panel.get_zone_pictures(self._zone_id, page_size=1)
                prev_id = existing[0].id if existing else None
            except Exception as err:  # noqa: BLE001
                _LOGGER.error(
                    "Zone %s: could not check existing pictures: %s",
                    self._zone_id, err,
                )
                return

            try:
                await panel.capture_picture(self._zone_id)
            except Exception as err:  # noqa: BLE001
                _LOGGER.error(
                    "Zone %s: could not trigger capture: %s",
                    self._zone_id, err,
                )
                return

            # Poll up to ~30 s (10 × 3 s) for the new picture to appear
            pic = None
            for _ in range(10):
                await asyncio.sleep(3)
                try:
                    pics = await panel.get_zone_pictures(self._zone_id, page_size=1)
                except Exception as err:  # noqa: BLE001
                    _LOGGER.error("Zone %s: poll error: %s", self._zone_id, err)
                    return
                if pics and pics[0].id != prev_id:
                    pic = pics[0]
                    break

            if pic is None:
                _LOGGER.warning(
                    "Zone %s: timed out waiting for new picture after capture",
                    self._zone_id,
                )
                return

        else:
            # ── Silent startup fetch: retrieve the latest stored picture ──
            try:
                pics = await panel.get_zone_pictures(self._zone_id, page_size=1)
            except Exception as err:  # noqa: BLE001
                _LOGGER.error(
                    "Zone %s: could not list pictures: %s",
                    self._zone_id, err,
                )
                return
            if not pics:
                return  # no pictures stored yet — silent, no warning
            pic = pics[0]

        # ── Download and store the picture ────────────────────────────────
        try:
            self._image_bytes = await session.get_picture_bytes(pic)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Zone %s: could not download picture %s: %s",
                self._zone_id, pic.id, err,
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
