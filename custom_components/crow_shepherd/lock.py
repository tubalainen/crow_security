"""Lock platform for Crow Shepherd outputs configured as door locks."""
from __future__ import annotations

import logging
from typing import Any

from crow_security_ng.exceptions import ResponseError
from crow_security_ng.models import Output

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN, OUTPUT_TYPES_LOCK
from .coordinator import CrowShepherdCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up lock entities from a config entry."""
    coordinator: CrowShepherdCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    async_add_entities(
        CrowShepherdLock(coordinator, output)
        for output in coordinator.data.outputs
        if output.output_type in OUTPUT_TYPES_LOCK
    )


class CrowShepherdLock(
    CoordinatorEntity[CrowShepherdCoordinator],
    LockEntity,
):
    """Lock entity representing a Crow output wired to a door lock."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CrowShepherdCoordinator,
        output: Output,
    ) -> None:
        super().__init__(coordinator)
        self._output_id = output.id
        self._attr_unique_id = f"{coordinator.hub.mac}_output_{output.id}"
        self._attr_name = output.name

    @property
    def device_info(self) -> DeviceInfo:
        panel = self.coordinator.hub.panel
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.hub.mac)},
            name=panel.name,
            manufacturer="Crow",
            model=panel.firmware_version or "Alarm Panel",
        )

    def _get_output(self) -> Output | None:
        return next(
            (o for o in self.coordinator.data.outputs if o.id == self._output_id),
            None,
        )

    @property
    def is_locked(self) -> bool | None:
        """Return True when the output is on (lock engaged)."""
        output = self._get_output()
        return output.state if output is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        output = self._get_output()
        if output is None:
            return {}
        return {
            "output_id": output.id,
            "output_type": output.output_type,
            "tamper": output.tamper_alarm,
            "battery_low": output.battery_low,
            "battery_voltage": output.battery_voltage,
            "rssi": output.rssi,
        }

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the door (turn the output on)."""
        await self._set_state(True)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the door (turn the output off)."""
        await self._set_state(False)

    async def _set_state(self, state: bool) -> None:
        try:
            await self.coordinator.hub.panel.set_output_state(self._output_id, state)
        except ResponseError as err:
            raise HomeAssistantError(
                f"Output {self._output_id}: "
                f"{'lock' if state else 'unlock'} failed "
                f"(HTTP {err.status_code}): {err}"
            ) from err
        except Exception as err:
            raise HomeAssistantError(
                f"Output {self._output_id}: "
                f"{'lock' if state else 'unlock'} failed: {err}"
            ) from err
        await self.coordinator.async_request_refresh()
