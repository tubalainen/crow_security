"""DataUpdateCoordinator for the Crow Shepherd integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING

from crow_security_ng.exceptions import AuthenticationError, ConnectionError, ResponseError
from crow_security_ng.models import Area, Measurement, Output, Zone

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from .hub import CrowHub

_LOGGER = logging.getLogger(__name__)


@dataclass
class CrowData:
    """All data fetched from the Crow panel in one coordinator refresh."""

    areas: list[Area] = field(default_factory=list)
    zones: list[Zone] = field(default_factory=list)
    outputs: list[Output] = field(default_factory=list)
    measurements: list[Measurement] = field(default_factory=list)


class CrowShepherdCoordinator(DataUpdateCoordinator[CrowData]):
    """Coordinator that polls the Crow panel for all entity data."""

    def __init__(
        self,
        hass: HomeAssistant,
        hub: "CrowHub",
        update_interval: int,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Crow Shepherd",
            update_interval=timedelta(seconds=update_interval),
        )
        self.hub = hub

    async def _async_update_data(self) -> CrowData:
        """Fetch all data from the panel.  Raises UpdateFailed on transient errors."""
        panel = self.hub.panel
        try:
            areas = await panel.get_areas()
            zones = await panel.get_zones()
            outputs = await panel.get_outputs()
            try:
                measurements = await panel.get_measurements()
            except Exception as err:  # noqa: BLE001
                # Measurements are optional — don't fail the whole refresh
                _LOGGER.warning("Could not fetch measurements (non-fatal): %s", err)
                measurements = []

            return CrowData(
                areas=areas,
                zones=zones,
                outputs=outputs,
                measurements=measurements,
            )

        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                "Crow Cloud rejected the credentials during refresh"
            ) from err
        except (ConnectionError, ResponseError) as err:
            raise UpdateFailed(f"Error communicating with Crow Cloud: {err}") from err
