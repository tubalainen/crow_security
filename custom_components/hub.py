"""Hub for Crow Shepherd integration using crow_security library."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Callable

import crow_security_ng as crow
from crow_security_ng import Panel
from crow_security_ng import ResponseError

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.util import Throttle

from .const import CONF_PANEL_MAC, DOMAIN, SET_STATE_MAP, STATE_MAP

_LOGGER = logging.getLogger(__name__)


class CrowHub:
    """Hub for managing connection to Crow Cloud."""

    def __init__(self, config: dict[str, Any], hass: HomeAssistant) -> None:
        """Initialize the hub."""
        self._hass = hass
        self._mac = config[CONF_PANEL_MAC]
        self._panel: Panel | None = None
        self._devices: list[dict[str, Any]] | None = None
        self._outputs: list[dict[str, Any]] | None = None
        self._measurements: list[dict[str, Any]] | None = None
        self._areas: list[dict[str, Any]] | None = None
        self._subscriptions: dict[str, Callable] = {}
        
        _LOGGER.info("Initializing Crow Hub with MAC: %s", self._mac)
        
        self.session = crow.Session(
            config[CONF_EMAIL],
            config[CONF_PASSWORD]
        )

    @property
    def mac(self) -> str:
        """Return the panel MAC address."""
        return self._mac

    @property
    def panel(self) -> Panel | None:
        """Return the panel object."""
        return self._panel

    async def init_panel(self) -> None:
        """Initialize the panel connection."""
        self._panel = await self.session.get_panel(self._mac)
        _LOGGER.info("Panel initialized: %s", self._panel.name if self._panel else "Unknown")

    async def async_test_connection(self) -> bool:
        """Test if we can connect to the Crow Cloud."""
        try:
            panel = await self.session.get_panel(self._mac)
            return panel is not None
        except Exception as err:
            _LOGGER.error("Connection test failed: %s", err)
            return False

    @Throttle(timedelta(seconds=60))
    async def _get_devices(self) -> list[dict[str, Any]] | None:
        """Get devices (zones) from the panel."""
        try:
            zones = await self.panel.get_zones()
            return zones
        except ResponseError as ex:
            _LOGGER.error("Failed to get zones: %s", ex)
            return None
        except Exception as ex:
            _LOGGER.error("Unexpected error getting zones: %s", ex)
            return None

    async def get_devices(self) -> list[dict[str, Any]]:
        """Get devices with caching."""
        devices = await self._get_devices()
        if devices:
            self._devices = devices
        return self._devices or []

    @Throttle(timedelta(seconds=30))
    async def _get_measurements(self) -> list[dict[str, Any]] | None:
        """Get measurements from the panel."""
        try:
            return await self.panel.get_measurements()
        except ResponseError as ex:
            _LOGGER.error("Failed to get measurements: %s", ex)
            return None
        except Exception as ex:
            _LOGGER.error("Unexpected error getting measurements: %s", ex)
            return None

    async def get_measurements(self) -> list[dict[str, Any]]:
        """Get measurements with caching."""
        measurements = await self._get_measurements()
        if measurements:
            self._measurements = measurements
        return self._measurements or []

    @Throttle(timedelta(seconds=30))
    async def _get_outputs(self) -> list[dict[str, Any]] | None:
        """Get outputs from the panel."""
        try:
            return await self.panel.get_outputs()
        except ResponseError as ex:
            _LOGGER.error("Failed to get outputs: %s", ex)
            return None
        except Exception as ex:
            _LOGGER.error("Unexpected error getting outputs: %s", ex)
            return None

    async def get_outputs(self) -> list[dict[str, Any]]:
        """Get outputs with caching."""
        outputs = await self._get_outputs()
        if outputs:
            self._outputs = outputs
        return self._outputs or []

    async def get_areas(self) -> list[dict[str, Any]]:
        """Get alarm areas/partitions."""
        try:
            areas = await self.panel.get_areas()
            self._areas = areas
            return areas
        except ResponseError as ex:
            _LOGGER.error("Failed to get areas: %s", ex)
            return self._areas or []
        except Exception as ex:
            _LOGGER.error("Unexpected error getting areas: %s", ex)
            return self._areas or []

    async def get_area(self, area_id: str) -> dict[str, Any] | None:
        """Get a specific area."""
        try:
            return await self.panel.get_area(area_id)
        except ResponseError as ex:
            _LOGGER.error("Failed to get area %s: %s", area_id, ex)
            return None
        except Exception as ex:
            _LOGGER.error("Unexpected error getting area %s: %s", area_id, ex)
            return None

    async def set_area_state(self, area_id: str, state: str) -> dict[str, Any] | None:
        """Set the state of an area (arm/disarm)."""
        api_state = SET_STATE_MAP.get(state, "disarm")
        _LOGGER.info("Setting area %s to state %s (API: %s)", area_id, state, api_state)
        try:
            return await self.panel.set_area_state(area_id, api_state)
        except ResponseError as err:
            if err.status_code == 408:
                _LOGGER.debug("Received expected 408 response when setting arm state")
                return None
            _LOGGER.error("Failed to set area state: %s", err)
            raise
        except Exception as err:
            _LOGGER.error("Unexpected error setting area state: %s", err)
            raise

    async def set_output_state(self, output_id: str, state: bool) -> bool:
        """Set the state of an output."""
        try:
            await self.panel.set_output_state(output_id, state)
            return True
        except ResponseError as ex:
            _LOGGER.error("Failed to set output state: %s", ex)
            return False
        except Exception as ex:
            _LOGGER.error("Unexpected error setting output state: %s", ex)
            return False

    async def capture_cam_image(self, zone_id: str) -> bytes | None:
        """Capture an image from a camera zone."""
        try:
            return await self.panel.capture_cam_image(zone_id)
        except ResponseError as ex:
            _LOGGER.error("Failed to capture camera image: %s", ex)
            return None
        except Exception as ex:
            _LOGGER.error("Unexpected error capturing camera image: %s", ex)
            return None

    def subscribe(self, device_id: str, callback: Callable) -> None:
        """Subscribe to updates for a device."""
        self._subscriptions[device_id] = callback

    def unsubscribe(self, device_id: str) -> None:
        """Unsubscribe from updates for a device."""
        self._subscriptions.pop(device_id, None)

    async def ws_connect(self) -> None:
        """Connect to WebSocket for real-time updates."""
        async def ws_callback(msg: dict[str, Any]) -> None:
            """Handle WebSocket messages."""
            # Skip certain info messages
            if (msg.get("type") == "info" and 
                msg.get("data", {}).get("_id", {}).get("dect_interface") == 32768):
                _LOGGER.debug("Skipping DECT info message")
                return
            
            _LOGGER.debug("Received WebSocket message: %s", msg)
            
            # Find and call the appropriate callback
            device_id = msg.get("data", {}).get("_id", {}).get("device_id")
            if device_id and device_id in self._subscriptions:
                callback = self._subscriptions[device_id]
                try:
                    callback(msg)
                except Exception as err:
                    _LOGGER.error("Error in subscription callback: %s", err)

        try:
            await self.session.ws_connect(self._mac, ws_callback)
        except Exception as err:
            _LOGGER.error("WebSocket connection failed: %s", err)

    @staticmethod
    def map_alarm_state(api_state: str) -> str:
        """Map API alarm state to Home Assistant state."""
        return STATE_MAP.get(api_state, "disarmed")
