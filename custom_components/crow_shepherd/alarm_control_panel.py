"""Alarm control panel platform for Crow Shepherd."""
from __future__ import annotations

import logging
from typing import Any

from crow_security_ng.exceptions import ResponseError
from crow_security_ng.models import Area, AreaCommand, AreaState

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import CrowShepherdCoordinator

_LOGGER = logging.getLogger(__name__)

# Authoritative AreaState → AlarmControlPanelState mapping
_AREA_STATE_MAP: dict[AreaState, AlarmControlPanelState] = {
    AreaState.DISARMED: AlarmControlPanelState.DISARMED,
    AreaState.ARMED: AlarmControlPanelState.ARMED_AWAY,
    AreaState.STAY_ARMED: AlarmControlPanelState.ARMED_HOME,
    AreaState.ARM_IN_PROGRESS: AlarmControlPanelState.ARMING,
    AreaState.STAY_ARM_IN_PROGRESS: AlarmControlPanelState.ARMING,
    AreaState.TRIGGERED: AlarmControlPanelState.TRIGGERED,
    AreaState.PENDING: AlarmControlPanelState.PENDING,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up alarm control panel entities from a config entry."""
    coordinator: CrowShepherdCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    async_add_entities(
        CrowShepherdAlarmControlPanel(coordinator, area)
        for area in coordinator.data.areas
    )


class CrowShepherdAlarmControlPanel(
    CoordinatorEntity[CrowShepherdCoordinator],
    AlarmControlPanelEntity,
):
    """One alarm control panel entity per Crow area/partition."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
    )
    # The panel user_code is wired server-side via hub.py — no UI code entry needed.
    _attr_code_arm_required = False

    def __init__(
        self,
        coordinator: CrowShepherdCoordinator,
        area: Area,
    ) -> None:
        """Initialise entity."""
        super().__init__(coordinator)
        self._area_id = area.id
        self._attr_unique_id = f"{coordinator.hub.mac}_{area.id}"
        self._attr_name = area.name

    # ------------------------------------------------------------------
    # Device info (all entities share one device per panel)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def _get_area(self) -> Area | None:
        """Return the current Area object from coordinator data."""
        return next(
            (a for a in self.coordinator.data.areas if a.id == self._area_id),
            None,
        )

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the current alarm state."""
        area = self._get_area()
        if area is None:
            return None
        state = _AREA_STATE_MAP.get(area.state)
        if state is None:
            _LOGGER.warning(
                "Unknown AreaState %r for area %s — reporting DISARMED",
                area.state,
                self._area_id,
            )
            return AlarmControlPanelState.DISARMED
        return state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        area = self._get_area()
        if area is None:
            return {}
        return {
            "area_id": area.id,
            "area_name": area.name,
            "raw_state": area.state.value if area.state else None,
            "ready_to_arm": area.ready_to_arm,
            "ready_to_stay": area.ready_to_stay,
            "zone_alarm": area.zone_alarm,
        }

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        await self._send_command(AreaCommand.DISARM)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm-home (stay) command."""
        await self._send_command(AreaCommand.STAY)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm-away command."""
        await self._send_command(AreaCommand.ARM)

    async def _send_command(self, command: AreaCommand) -> None:
        """Send an arm/disarm command and request a coordinator refresh."""
        _LOGGER.debug("Area %s: sending command %s", self._area_id, command)
        try:
            await self.coordinator.hub.panel.set_area_state(self._area_id, command)
        except ResponseError as err:
            if err.status_code == 408:
                # 408 is expected on successful arm — the panel takes time to confirm.
                _LOGGER.debug(
                    "Area %s: received expected 408 after %s", self._area_id, command
                )
            else:
                _LOGGER.error(
                    "Area %s: API error %s during %s: %s",
                    self._area_id,
                    err.status_code,
                    command,
                    err,
                )
                return
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Area %s: unexpected error during %s: %s", self._area_id, command, err
            )
            return

        await self.coordinator.async_request_refresh()
