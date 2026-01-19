# Crow Shepherd Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

A comprehensive Home Assistant custom integration for the Crow Shepherd alarm system that connects to Crow Cloud using the [crow_security_ng](https://github.com/crow-security-ng/crow-security-ng) Python library.

## Features

- **Alarm Control Panel**: Full control of your alarm system
  - Arm/Disarm in multiple modes (Away, Home)
  - Real-time status updates via WebSocket
  - Support for multiple areas/partitions

- **Zone Sensors**: Binary sensors for all zones
  - Door/Window sensors
  - Motion detectors
  - Smoke/Gas detectors
  - Water leak sensors
  - Battery level monitoring
  - Signal strength indicators
  - Bypass status

- **Output Switches**: Control all outputs
  - Turn outputs on/off
  - Real-time status updates

- **Sensors**: Additional monitoring
  - Measurement sensors (temperature, humidity, etc.)
  - Zone battery sensors

## Prerequisites

This integration requires the `crow_security_ng` Python library which will be installed automatically.

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL with category "Integration"
6. Click "Install"
7. Restart Home Assistant

### Manual Installation

1. Download the latest release
2. Copy the `crow_shepherd` folder to your `custom_components` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "Crow Shepherd"
4. Enter your Crow Cloud credentials:
   - **Email**: Your Crow Cloud account email
   - **Password**: Your Crow Cloud account password
   - **Panel MAC Address**: The MAC address of your panel (found in the Crow Cloud app settings)

### Finding Your Panel MAC Address

1. Open the Crow Cloud app on your phone
2. Go to Settings/Panel Information
3. The MAC address is displayed there

**You can enter the MAC address in any format:**
- With colons: `AA:BB:CC:DD:EE:FF`
- With dashes: `AA-BB-CC-DD-EE-FF`
- Without separators: `AABBCCDDEEFF`

The integration will automatically normalize it.

## Options

After setup, you can configure:
- **Update Interval**: How often to poll for updates (10-300 seconds, default: 30)
- **Panel Code**: Your alarm panel code for arming/disarming

## Entities Created

### Alarm Control Panel
- `alarm_control_panel.{panel_name}_{area_name}` - Alarm panel entity (one per area)

### Binary Sensors (per zone)
- `binary_sensor.{zone_name}` - Zone status (open/closed)

### Switches (per output)
- `switch.{output_name}` - Output control

### Sensors
- `sensor.{measurement_name}` - Measurement sensors
- `sensor.{zone_name}_battery` - Zone battery level (where available)

## State Mappings

| API State | Home Assistant State |
|-----------|---------------------|
| `armed` | `armed_away` |
| `stay_armed` | `armed_home` |
| `disarmed` | `disarmed` |
| `arm in progress` | `arming` |
| `stay arm in progress` | `arming` |

## Services

### `crow_shepherd.bypass_zone`
Bypass or unbypass a zone.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `zone_id` | string | Yes | The zone ID to bypass |
| `bypass` | boolean | Yes | True to bypass, false to unbypass |

### `crow_shepherd.trigger_camera_snapshot`
Trigger a camera zone to take a new snapshot.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `zone_id` | string | Yes | The camera zone ID |

## Automations Examples

### Send notification when alarm is triggered
```yaml
automation:
  - alias: "Alarm Triggered Notification"
    trigger:
      - platform: state
        entity_id: alarm_control_panel.home_alarm
        to: "triggered"
    action:
      - service: notify.mobile_app
        data:
          title: "🚨 Alarm Triggered!"
          message: "Your alarm has been triggered"
```

### Arm alarm when leaving home
```yaml
automation:
  - alias: "Arm Away When Leaving"
    trigger:
      - platform: state
        entity_id: person.your_name
        to: "not_home"
    action:
      - service: alarm_control_panel.alarm_arm_away
        target:
          entity_id: alarm_control_panel.home_alarm
```

### Disarm alarm when arriving home
```yaml
automation:
  - alias: "Disarm When Arriving"
    trigger:
      - platform: state
        entity_id: person.your_name
        to: "home"
    action:
      - service: alarm_control_panel.alarm_disarm
        target:
          entity_id: alarm_control_panel.home_alarm
```

## Troubleshooting

### Authentication Issues
- Verify your Crow Cloud email and password are correct
- Try logging into the Crow Cloud app to confirm your account is active
- Check if your account has access to the panel

### Panel Not Found
- Verify the MAC address is correct (check in Crow Cloud app)
- Ensure the panel is online and connected to the internet
- Make sure your account has permissions to access the panel

### Connection Issues
- Ensure your Home Assistant has internet access
- Check if Crow Cloud services are operational
- Verify no firewall is blocking the connection

### Missing Entities
- Check the Home Assistant logs for errors
- Ensure your panel has the expected devices configured
- Try reloading the integration

### Real-time Updates Not Working
- The integration uses WebSocket for real-time updates
- Check if your Home Assistant can maintain WebSocket connections
- Some updates may be delayed due to throttling (30-60 seconds)

## Support

For issues and feature requests, please open an issue on GitHub.

## Credits

- Uses the [crow_security_ng](https://github.com/crow-security-ng/crow-security-ng) Python library, an improved fork of the original [crow_security](https://pypi.org/project/crow-security/) by Shprota
- Based on research from [ha_crow_cloud_security_component](https://github.com/tubalainen/ha_crow_cloud_security_component) by @tubalainen
- Thanks to the Crow Group for their security products

## License

This project is licensed under the MIT License - see the LICENSE file for details.
