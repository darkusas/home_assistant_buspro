import asyncio

import pytest
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.buspro.diagnostics import async_get_config_entry_diagnostics

from fakebus import FakeBus, SimDevice

SCAN = {"rounds": 1, "interval": 0.2}


@pytest.fixture
async def bus(hass):
    entry = MockConfigEntry(domain="buspro", data={"host": "127.0.0.1", "port": 6000})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    module = hass.data["buspro"]
    devices = [SimDevice((1, 89), 0x01AC, "Rėlės", functions=[(1, 1, 2)], levels=[0, 100],
                         channel_names={1: "Virtuvė", 2: None})]
    module.hdl.network_interface = FakeBus(module.hdl, devices)
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
