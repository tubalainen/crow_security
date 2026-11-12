"""Panel connectivity polling for Crow Shepherd."""
from __future__ import annotations

import logging
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, TypeVar

from crow_security_ng.exceptions import AuthenticationError, CrowError
from crow_security_ng.models import ConnectionInfo, GsmInfo, RadioInfo, WifiInfo

from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import CONNECTIVITY_SCAN_INTERVAL, DOMAIN

if TYPE_CHECKING:
    from .hub import CrowHub

_LOGGER = logging.getLogger(__name__)

_T = TypeVar("_T")


@dataclass
class ConnectivityData:
    """Connectivity snapshot. Module fields are None when that endpoint failed."""

    online: bool | None
    last_heartbeat: datetime | None
    heartbeat_expired: bool | None
    connection: ConnectionInfo | None
    wifi: WifiInfo | None
    gsm: GsmInfo | None
    radio: RadioInfo | None


class CrowShepherdConnectivityCoordinator(DataUpdateCoordinator[ConnectivityData]):
    """Polls panel connectivity on a slower interval than the main coordinator."""

    def __init__(self, hass: HomeAssistant, hub: "CrowHub") -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Crow Shepherd connectivity",
            update_interval=timedelta(seconds=CONNECTIVITY_SCAN_INTERVAL),
        )
        self.hub = hub

    async def _optional(self, label: str, call: Awaitable[_T]) -> _T | None:
        try:
            return await call
        except AuthenticationError:
            raise
        except CrowError as err:
            _LOGGER.debug("Could not fetch %s info: %s", label, err)
            return None

    async def _async_update_data(self) -> ConnectivityData:
        panel = self.hub.panel
        try:
            await panel.refresh()
            connection = await self._optional("connection", panel.get_connection())
            wifi = await self._optional("Wi-Fi", panel.get_wifi_info())
            gsm = await self._optional("GSM", panel.get_gsm_info())
            radio = await self._optional("radio", panel.get_radio_info())
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                "Crow Cloud rejected the credentials during refresh"
            ) from err
        except CrowError as err:
            raise UpdateFailed(f"Error fetching panel connectivity: {err}") from err

        return ConnectivityData(
            online=panel.is_online,
            last_heartbeat=panel.last_report_heartbeat,
            heartbeat_expired=panel.report_heartbeat_expired,
            connection=connection,
            wifi=wifi,
            gsm=gsm,
            radio=radio,
        )


class CrowShepherdConnectivityEntity(
    CoordinatorEntity[CrowShepherdConnectivityCoordinator]
):
    """Base for diagnostic connectivity entities on the panel device."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: CrowShepherdConnectivityCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.hub.mac}_{key}"
        self._attr_translation_key = key

    @property
    def device_info(self) -> DeviceInfo:
        panel = self.coordinator.hub.panel
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.hub.mac)},
            name=panel.name,
            manufacturer="Crow",
            model=panel.firmware_version or "Alarm Panel",
        )
