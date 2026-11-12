"""Tests for the panel connectivity entities."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from crow_security_ng.exceptions import ResponseError
from crow_security_ng.models import ConnectionInfo, GsmInfo, RadioInfo, WifiInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

import custom_components.crow_shepherd as crow_shepherd

DOMAIN = "crow_shepherd"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


def _hub(gsm_fails: bool = False) -> MagicMock:
    panel = MagicMock()
    panel.name = "Test Panel"
    panel.firmware_version = "1.0"
    panel.is_online = True
    panel.last_report_heartbeat = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    panel.report_heartbeat_expired = False
    for name in ("get_areas", "get_zones", "get_outputs", "get_measurements"):
        setattr(panel, name, AsyncMock(return_value=[]))
    panel.refresh = AsyncMock()
    panel.get_connection = AsyncMock(
        return_value=ConnectionInfo.from_api({"interface": 1, "connected": True})
    )
    panel.get_wifi_info = AsyncMock(
        return_value=WifiInfo.from_api({"enabled": False, "rssi": 0})
    )
    if gsm_fails:
        panel.get_gsm_info = AsyncMock(side_effect=ResponseError("boom", status_code=500))
    else:
        panel.get_gsm_info = AsyncMock(
            return_value=GsmInfo.from_api(
                {"enabled": True, "status": 4, "status_desc": "Sim Not Inserted", "rssi": 0}
            )
        )
    panel.get_radio_info = AsyncMock(return_value=RadioInfo.from_api({"failure": False}))

    hub = MagicMock()
    hub.mac = "aabbccddeeff"
    hub.panel = panel
    hub.async_connect = AsyncMock()
    hub.async_close = AsyncMock()
    async def _forever(*args):
        await asyncio.Event().wait()

    hub.session.ws_connect = AsyncMock(side_effect=_forever)
    return hub


async def _setup(hass: HomeAssistant, hub: MagicMock) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id="aabbccddeeff",
        data={"email": "user@example.com", "password": "x", "panel_mac": "aabbccddeeff"},
    )
    entry.add_to_hass(hass)
    with patch.object(crow_shepherd.CrowHub, "from_config_entry", return_value=hub):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_connectivity_entities(hass: HomeAssistant) -> None:
    entry = await _setup(hass, _hub())

    assert hass.states.get("binary_sensor.test_panel_cloud_connection").state == "on"
    assert hass.states.get("binary_sensor.test_panel_radio_module").state == "off"
    conn = hass.states.get("sensor.test_panel_connection_type")
    assert conn.state == "ethernet"
    assert conn.attributes["interface_code"] == 1
    assert hass.states.get("sensor.test_panel_gsm_status").state == "Sim Not Inserted"
    assert hass.states.get("sensor.test_panel_last_heartbeat").state == (
        "2026-01-01T12:00:00+00:00"
    )

    reg = er.async_get(hass)
    wifi = reg.async_get("sensor.test_panel_wi_fi_signal")
    assert wifi is not None and wifi.disabled_by is not None
    assert wifi.entity_category == "diagnostic"
    assert hass.states.get("sensor.test_panel_wi_fi_signal") is None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_failed_module_only_affects_its_entities(hass: HomeAssistant) -> None:
    entry = await _setup(hass, _hub(gsm_fails=True))

    assert hass.states.get("sensor.test_panel_gsm_status").state == "unavailable"
    assert hass.states.get("sensor.test_panel_connection_type").state == "ethernet"
    assert hass.states.get("binary_sensor.test_panel_cloud_connection").state == "on"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
