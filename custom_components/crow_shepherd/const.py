"""Constants for the Crow Shepherd integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "crow_shepherd"

# Configuration keys
CONF_PANEL_MAC: Final = "panel_mac"
CONF_PANEL_CODE: Final = "panel_code"
CONF_SCAN_INTERVAL: Final = "scan_interval"

# Default values
DEFAULT_SCAN_INTERVAL: Final = 30

# Platforms
PLATFORMS: Final = [
    "alarm_control_panel",
    "binary_sensor",
    "switch",
    "sensor",
]

# hass.data keys
DATA_HUB: Final = "hub"
DATA_COORDINATOR: Final = "coordinator"
