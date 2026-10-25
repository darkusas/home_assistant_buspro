import asyncio

import pytest
from homeassistant.exceptions import HomeAssistantError
from custom_components.buspro.diagnostics import async_get_config_entry_diagnostics

from conftest import setup_integration
from fakebus import SimDevice

SCAN = {"rounds": 1, "interval": 0.2}


@pytest.fixture
async def bus(hass):
    devices = [SimDevice((1, 89), 0x01AC, "Rėlės", functions=[(1, 1, 2)], levels=[0, 100],
                         channel_names={1: "Virtuvė", 2: None})]
    entry, module, _bus = await setup_integration(hass, devices)
    return entry, module


async def test_scan_service_returns_devices(hass, bus):
    entry, module = bus
    response = await hass.services.async_call("buspro", "scan", SCAN, blocking=True, return_response=True)

    assert [d["address"] for d in response["devices"]] == ["1.89"]
    device = response["devices"][0]
    assert device["remark"] == "Rėlės"
    assert device["category"] == "output_module"
    assert device["mac"] == "10:20:30:40:50:60:01:59"
    assert device["channels"] == [
        {"number": 1, "kind": "relay", "name": "Virtuvė", "level": 0},
        {"number": 2, "kind": "relay", "name": None, "level": 100},
    ]
    assert module.last_scan is not None

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["last_scan"]["devices"][0]["mac"] == "**REDACTED**"


async def test_scan_service_rejects_parallel_scan(hass, bus):
    first = hass.async_create_task(
        hass.services.async_call("buspro", "scan", {"rounds": 1, "interval": 1}, blocking=True, return_response=True))
    await asyncio.sleep(0.05)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("buspro", "scan", SCAN, blocking=True, return_response=True)
    await first
