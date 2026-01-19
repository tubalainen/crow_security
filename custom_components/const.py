"""Constants for the Crow Shepherd integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "crow_shepherd"

# Configuration
CONF_PANEL_MAC: Final = "panel_mac"
CONF_PANEL_CODE: Final = "panel_code"
CONF_SCAN_INTERVAL: Final = "scan_interval"

# Default values
DEFAULT_SCAN_INTERVAL: Final = 30
DEFAULT_NAME: Final = "Crow Shepherd"

# Alarm states mapping from API to Home Assistant
STATE_MAP: Final = {
    "armed": "armed_away",
    "arm in progress": "arming",
    "stay arm in progress": "arming",
    "stay_armed": "armed_home",
    "disarmed": "disarmed",
}

# Arm state commands to send to API
SET_STATE_MAP: Final = {
    "armed_home": "stay",
    "armed_away": "arm",
    "disarm": "disarm",
}

# Zone types
ZONE_TYPE_DOOR: Final = "door"
ZONE_TYPE_WINDOW: Final = "window"
ZONE_TYPE_MOTION: Final = "motion"
ZONE_TYPE_SMOKE: Final = "smoke"
ZONE_TYPE_WATER: Final = "water"
ZONE_TYPE_GLASS: Final = "glass"
ZONE_TYPE_PANIC: Final = "panic"
ZONE_TYPE_MEDICAL: Final = "medical"
ZONE_TYPE_GAS: Final = "gas"
ZONE_TYPE_TEMPERATURE: Final = "temperature"
ZONE_TYPE_GENERIC: Final = "generic"

# Zone states
ZONE_STATE_OK: Final = "ok"
ZONE_STATE_OPEN: Final = "open"
ZONE_STATE_TAMPER: Final = "tamper"
ZONE_STATE_ALARM: Final = "alarm"
ZONE_STATE_TROUBLE: Final = "trouble"
ZONE_STATE_BYPASSED: Final = "bypassed"
ZONE_STATE_LOWBATT: Final = "low_battery"

# Output states
OUTPUT_STATE_ON: Final = "on"
OUTPUT_STATE_OFF: Final = "off"

# Platforms
PLATFORMS: Final = [
    "alarm_control_panel",
    "binary_sensor",
    "switch",
    "sensor",
]

# Data keys
DATA_HUB: Final = "hub"

# Events
EVENT_ALARM_TRIGGERED: Final = f"{DOMAIN}_alarm_triggered"
EVENT_ZONE_OPENED: Final = f"{DOMAIN}_zone_opened"
EVENT_ZONE_TAMPER: Final = f"{DOMAIN}_zone_tamper"

# Attributes
ATTR_PANEL_MAC: Final = "panel_mac"
ATTR_PANEL_NAME: Final = "panel_name"
ATTR_ZONE_ID: Final = "zone_id"
ATTR_ZONE_NAME: Final = "zone_name"
ATTR_ZONE_TYPE: Final = "zone_type"
ATTR_LAST_EVENT: Final = "last_event"
ATTR_LAST_TRIGGERED: Final = "last_triggered"
ATTR_BATTERY_LEVEL: Final = "battery_level"
ATTR_SIGNAL_STRENGTH: Final = "signal_strength"
ATTR_FIRMWARE_VERSION: Final = "firmware_version"
