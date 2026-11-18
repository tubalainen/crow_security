"""Constants for the Crow Shepherd integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "crow_shepherd"

# output_type integers that should become lock entities instead of switches.
# Check Settings → Developer tools → States → switch.<name> → output_type
# to find the value your panel reports, then add it here.
# Example: OUTPUT_TYPES_LOCK: frozenset[int] = frozenset({10})
OUTPUT_TYPES_LOCK: Final[frozenset[int]] = frozenset()

# output_type integers that should become siren entities instead of switches.
OUTPUT_TYPES_SIREN: Final[frozenset[int]] = frozenset({70})

# Configuration keys
CONF_PANEL_MAC: Final = "panel_mac"
CONF_PANEL_CODE: Final = "panel_code"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_CAMERA_ZONE_IDS: Final = "camera_zone_ids"

# Default values
DEFAULT_SCAN_INTERVAL: Final = 30
CONNECTIVITY_SCAN_INTERVAL: Final = 300

# Platforms
PLATFORMS: Final = [
    "alarm_control_panel",
    "binary_sensor",
    "image",
    "lock",
    "sensor",
    "siren",
    "switch",
]

# hass.data keys
DATA_HUB: Final = "hub"
DATA_COORDINATOR: Final = "coordinator"
DATA_CONNECTIVITY: Final = "connectivity"
