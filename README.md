# Crow Shepherd Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

A Home Assistant custom integration for Crow alarm panels that connects to Crow Cloud using the [crow_security_ng](https://github.com/tubalainen/crow_security_ng) Python library.

## Features

- **Alarm Control Panel** — arm/disarm in Away and Home modes; real-time state via WebSocket; one entity per area/partition
- **Zone Binary Sensors** — open/close state for every zone with motion, tamper, bypass, battery, RSSI and battery voltage as attributes
- **Output Switches** — turn outputs on/off with tamper, battery, RSSI and battery voltage as attributes
- **DECT Measurement Sensors** — temperature, humidity, air pressure and gas level sensors for smart devices
- **PIR Camera Image Entities** — on-demand JPEG snapshots from smart-cam zones (zone type 55), fetched via the `fetch_camera_snapshot` action

## Requirements

- Home Assistant 2024.11 or newer
- `crow_security_ng >= 0.2.1` (installed automatically)

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click **Integrations** → three-dot menu → **Custom repositories**
3. Add this repository URL with category **Integration**
4. Install and restart Home Assistant

### Manual

1. Copy the `custom_components/crow_shepherd` folder to your `custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **Crow Shepherd**
3. Enter your credentials:
   - **Email** — your Crow Cloud account email
   - **Password** — your Crow Cloud account password
   - **Panel MAC Address** — the MAC address of your panel (found in the Crow Cloud app)
   - **Panel User Code** *(optional)* — required only if your panel needs a code to arm/disarm

### MAC address formats

All of the following are accepted — the integration normalises them automatically:

```
AABBCCDDEEFF
AA:BB:CC:DD:EE:FF
AA-BB-CC-DD-EE-FF
```

## Options

After setup, you can adjust:

- **Update interval** — how often to poll Crow Cloud (10–300 s, default 30 s)
- **Panel User Code** — update the arm/disarm code without reconfiguring

## Entities

### Alarm Control Panel

One entity per area/partition:

| Entity | Description |
|--------|-------------|
| `alarm_control_panel.<area_name>` | Arm Away / Arm Home / Disarm |

**Attributes:** `area_id`, `raw_state`, `ready_to_arm`, `ready_to_stay`, `zone_alarm`

### Binary Sensors (zones)

One entity per zone:

| Entity | Description |
|--------|-------------|
| `binary_sensor.<zone_name>` | `on` = open / triggered |

**Attributes:** `zone_id`, `zone_type`, `bypassed`, `tamper`, `battery_low`, `battery_voltage`, `active`, `rssi`

### Switches (outputs)

One entity per output:

| Entity | Description |
|--------|-------------|
| `switch.<output_name>` | Turn output on/off |

**Attributes:** `output_id`, `output_type`, `tamper`, `battery_low`, `battery_voltage`, `rssi`

### Sensors (DECT measurements)

One entity per measurement type per smart device:

| Entity | Description |
|--------|-------------|
| `sensor.<device_name>_temperature` | Temperature (°C) |
| `sensor.<device_name>_humidity` | Relative humidity (%) |
| `sensor.<device_name>_air_pressure` | Atmospheric pressure (hPa) |
| `sensor.<device_name>_gas_level` | Gas level (0–4 scale) |

### Image Entities (PIR cameras)

One entity per camera zone (`zone_type == 55`):

| Entity | Description |
|--------|-------------|
| `image.<zone_name>_snapshot` | Latest on-demand JPEG snapshot |

The entity starts empty. Call `crow_shepherd.fetch_camera_snapshot` targeting it to populate the image.

**Attributes:** `picture_id`, `picture_type` (`alarm` / `manual`), `panel_time`

## Actions

### `crow_shepherd.fetch_camera_snapshot`

Fetches the latest snapshot from a PIR camera zone and updates the image entity.

**Target:** one or more `image.*` entities from this integration.

```yaml
action: crow_shepherd.fetch_camera_snapshot
target:
  entity_id: image.hall_cam_snapshot
```

### `crow_shepherd.bypass_zone`

Bypass or unbypass a zone on the alarm panel.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `zone_id` | number | Yes | Numeric zone ID |
| `bypass` | boolean | Yes | `true` to bypass, `false` to unbypass |

```yaml
action: crow_shepherd.bypass_zone
data:
  zone_id: 3
  bypass: true
```

## State Mappings

| Panel state | Home Assistant state |
|-------------|----------------------|
| `disarmed` | `disarmed` |
| `armed` | `armed_away` |
| `stay_armed` | `armed_home` |
| `arm in progress` | `arming` |
| `stay arm in progress` | `arming` |
| `triggered` | `triggered` |
| `pending` | `pending` |

## Automation Examples

### Notify when alarm is triggered

```yaml
automation:
  - alias: "Alarm Triggered Notification"
    trigger:
      - platform: state
        entity_id: alarm_control_panel.home_alarm
        to: triggered
    action:
      - action: notify.mobile_app
        data:
          title: "Alarm Triggered"
          message: "Your alarm has been triggered"
```

### Arm away when leaving home

```yaml
automation:
  - alias: "Arm Away When Leaving"
    trigger:
      - platform: state
        entity_id: person.your_name
        to: not_home
    action:
      - action: alarm_control_panel.alarm_arm_away
        target:
          entity_id: alarm_control_panel.home_alarm
```

### Disarm when arriving home

```yaml
automation:
  - alias: "Disarm When Arriving"
    trigger:
      - platform: state
        entity_id: person.your_name
        to: home
    action:
      - action: alarm_control_panel.alarm_disarm
        target:
          entity_id: alarm_control_panel.home_alarm
```

### Fetch camera snapshot when motion is detected

```yaml
automation:
  - alias: "Fetch snapshot on motion"
    trigger:
      - platform: state
        entity_id: binary_sensor.hall_cam
        to: "on"
    action:
      - action: crow_shepherd.fetch_camera_snapshot
        target:
          entity_id: image.hall_cam_snapshot
```

## Troubleshooting

### Authentication issues
- Verify your Crow Cloud email and password
- Try logging in via the Crow Cloud app to confirm your account is active

### Panel not found
- Double-check the MAC address in the Crow Cloud app settings
- Ensure the panel is online and connected to the internet

### Entities missing
- Check Home Assistant logs for errors
- Try reloading the integration from **Settings → Devices & Services**
- DECT sensors only appear if your panel has wireless smart devices

### Camera image not updating
- The image entity is **on-demand only** — it does not update automatically
- Call `crow_shepherd.fetch_camera_snapshot` to retrieve the latest picture

### Real-time updates not working
- The integration uses WebSocket for live updates; it reconnects automatically after disruptions
- If updates are delayed, check your Home Assistant's internet connection

## Support

For issues and feature requests, open an issue on [GitHub](https://github.com/tubalainen/crow_security/issues).

## Credits

- Uses the [crow_security_ng](https://github.com/tubalainen/crow_security_ng) Python library by @tubalainen
- Based on research from [ha_crow_cloud_security_component](https://github.com/tubalainen/ha_crow_cloud_security_component) by @tubalainen

## License

MIT License — see the LICENSE file for details.
