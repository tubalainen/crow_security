"""Switch platform for Crow Shepherd outputs."""
from __future__ import annotations

import logging
from typing import Any

from crow_security_ng.exceptions import ResponseError
from crow_security_ng.models import Output

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import CrowShepherdCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities from a config entry."""
    coordinator: CrowShepherdCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    async_add_entities(
        CrowShepherdOutputSwitch(coordinator, output)
        for output in coordinator.data.outputs
    )


class CrowShepherdOutputSwitch(
    CoordinatorEntity[CrowShepherdCoordinator],
    SwitchEntity,
):
    """Switch representing a Crow output."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CrowShepherdCoordinator,
        output: Output,
    ) -> None:
        """Initialise entity."""
        super().__init__(coordinator)
        self._output_id = output.id
        self._attr_unique_id = f"{coordinator.hub.mac}_output_{output.id}"
        self._attr_name = output.name

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

    def _get_output(self) -> Output | None:
        """Return the current Output object from coordinator data."""
        return next(
            (o for o in self.coordinator.data.outputs if o.id == self._output_id),
            None,
        )

    @property
    def is_on(self) -> bool:
        """Return True when the output is active.

        Output.state is a bool in crow_security_ng.
        """
        output = self._get_output()
        return output.state if output is not None else False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        output = self._get_output()
        if output is None:
            return {}
        return {
            "output_id": output.id,
            "output_type": output.output_type,
            "tamper": output.tamper_alarm,
            "battery_low": output.battery_low,
            "rssi": output.rssi,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the output on."""
        await self._set_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the output off."""
        await self._set_state(False)

    async def _set_state(self, state: bool) -> None:
        """Send set-output-state command and refresh coordinator."""
        try:
            await self.coordinator.hub.panel.set_output_state(self._output_id, state)
        except ResponseError as err:
            _LOGGER.error(
                "Output %s: API error %s setting state to %s: %s",
                self._output_id,
                err.status_code,
                state,
                err,
            )
            return
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Output %s: unexpected error setting state to %s: %s",
                self._output_id,
                state,
                err,
            )
            return

        await self.coordinator.async_request_refresh()
