"""Entities added from the bus scan: created live, persisted, removed cleanly."""

import asyncio

import pytest
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from conftest import setup_integration
from fakebus import SimDevice

# pybuspro devices schedule a delayed first status read and lights poll hourly.
pytestmark = [
    pytest.mark.parametrize("expected_lingering_tasks", [True]),
    pytest.mark.parametrize("expected_lingering_timers", [True]),
]

SWITCH = {"platform": "switch", "address": "1.89", "channel": 1, "name": "Virtuvė",
          "device_name": "Rėlės 1 aukštas", "device_model": "0x01AC", "mac": "10:20:30:40:50:60:01:59"}
LIGHT = {"platform": "light", "address": "1.89", "channel": 2, "name": "Koridorius", "dimmable": True,
         "device_name": "Rėlės 1 aukštas"}


@pytest.fixture
async def relay(hass):
    device = SimDevice((1, 89), 0x01AC, "Rėlės 1 aukštas", functions=[(1, 1, 4)], levels=[0, 0, 0, 0])
    entry, module, bus = await setup_integration(hass, [device])
    return device, entry, module


async def settle(hass):
    """Let pybuspro's own callbacks (asyncio.ensure_future) run, which block_till_done does not track."""
    for _ in range(3):
        await asyncio.sleep(0)
        await hass.async_block_till_done()


async def ws(client, message):
    await client.send_json_auto_id(message)
    response = await client.receive_json()
    assert response["success"], response
    return response["result"]


async def test_add_entities_live_and_control_them(hass, hass_ws_client, relay):
    device, _entry, _module = relay
    client = await hass_ws_client(hass)
    result = await ws(client, {"type": "buspro/entities/add", "entities": [SWITCH, LIGHT]})
    await hass.async_block_till_done()

    assert result == {"added": ["1.89.1", "1.89.2"], "rejected": []}
    assert hass.states.get("switch.virtuve").state == "off"
    assert hass.states.get("light.koridorius") is not None

    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.virtuve"}, blocking=True)
    await hass.services.async_call("light", "turn_on", {"entity_id": "light.koridorius", "brightness": 128},
                                   blocking=True)
    await settle(hass)
    assert device.levels[:2] == [100, 50]
    assert hass.states.get("switch.virtuve").state == "on"

    devices = dr.async_get(hass)
    hdl_device = devices.async_get_device(identifiers={("buspro", "1.89")})
    assert (hdl_device.name, hdl_device.manufacturer, hdl_device.model, hdl_device.serial_number) == (
        "Rėlės 1 aukštas", "HDL", "0x01AC", "10:20:30:40:50:60:01:59")
    entities = er.async_get(hass)
    assert entities.async_get("switch.virtuve").device_id == hdl_device.id
    assert entities.async_get("switch.virtuve").unique_id == "(1, 89)-1"

    listed = await ws(client, {"type": "buspro/entities/list"})
    assert {e["key"]: e["entity_id"] for e in listed["entities"]} == {
        "1.89.1": "switch.virtuve", "1.89.2": "light.koridorius"}


async def test_entities_persist_and_survive_reload(hass, hass_ws_client, hass_storage, relay):
    _device, entry, module = relay
    client = await hass_ws_client(hass)
    await ws(client, {"type": "buspro/entities/add", "entities": [SWITCH]})
    await hass.async_block_till_done()
    callbacks = len(module.hdl._telegram_received_cbs)

    stored = hass_storage["buspro.entities"]["data"]["entities"]
    assert [(e["platform"], e["subnet_id"], e["device_id"], e["channel"], e["name"]) for e in stored] == [
        ("switch", 1, 89, 1, "Virtuvė")]

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("switch.virtuve") is not None
    assert hass.data["buspro"] is module  # the bus connection is reused
    assert len(module.hdl._telegram_received_cbs) == callbacks  # old entity's callbacks are gone


async def test_entities_load_from_storage(hass, hass_storage):
    hass_storage["buspro.entities"] = {"version": 1, "minor_version": 1, "key": "buspro.entities", "data": {
        "entities": [{"platform": "light", "subnet_id": 1, "device_id": 20, "channel": 3, "name": "Valgomasis",
                      "options": {"dimmable": False, "running_time": 0}, "device_name": None,
                      "device_model": None, "mac": None}]}}
    await setup_integration(hass, [SimDevice((1, 20), 0x026D, levels=[0, 0, 0])])
    await hass.async_block_till_done()

    state = hass.states.get("light.valgomasis")
    assert state is not None and state.attributes["supported_color_modes"] == ["onoff"]
    assert dr.async_get(hass).async_get_device(identifiers={("buspro", "1.20")}).name == "HDL 1.20"


async def test_remove_entities(hass, hass_ws_client, relay):
    _device, _entry, module = relay
    client = await hass_ws_client(hass)
    baseline = len(module.hdl._telegram_received_cbs)
    await ws(client, {"type": "buspro/entities/add", "entities": [SWITCH, LIGHT]})
    await hass.async_block_till_done()

    assert await ws(client, {"type": "buspro/entities/remove", "keys": ["1.89.1"]}) == {"removed": ["1.89.1"]}
    await hass.async_block_till_done()
    assert hass.states.get("switch.virtuve") is None
    assert er.async_get(hass).async_get("switch.virtuve") is None
    assert dr.async_get(hass).async_get_device(identifiers={("buspro", "1.89")}) is not None  # light remains

    await ws(client, {"type": "buspro/entities/remove", "keys": ["1.89.2", "9.9.9"]})
    await hass.async_block_till_done()
    assert dr.async_get(hass).async_get_device(identifiers={("buspro", "1.89")}) is None
    assert len(module.hdl._telegram_received_cbs) == baseline
    assert (await ws(client, {"type": "buspro/entities/list"}))["entities"] == []


async def test_duplicates_are_rejected(hass, hass_ws_client):
    # YAML is loaded at startup, before the config entry, which then reuses the YAML bus connection.
    assert await async_setup_component(hass, "buspro", {"buspro": {"host": "127.0.0.1", "port": 6000}})
    assert await async_setup_component(hass, "switch", {"switch": [
        {"platform": "buspro", "devices": {"1.89.3": {"name": "Yaml switch"}}}]})
    await hass.async_block_till_done()
    yaml_module = hass.data["buspro"]
    _entry, module, _bus = await setup_integration(hass, [SimDevice((1, 89), 0x01AC, levels=[0, 0, 0, 0])])
    assert module is yaml_module
    client = await hass_ws_client(hass)
    await ws(client, {"type": "buspro/entities/add", "entities": [SWITCH]})

    result = await ws(client, {"type": "buspro/entities/add", "entities": [
        {**SWITCH, "name": "Again"},
        {**LIGHT, "channel": 1, "name": "Same channel as light"},
        {**SWITCH, "channel": 3, "name": "Also in YAML"},
        {**LIGHT, "channel": 3, "name": "In YAML as a switch"},
        {**SWITCH, "channel": 4, "name": "Fine"},
    ]})
    assert result["added"] == ["1.89.4"]
    assert [r["reason"] for r in result["rejected"]] == [
        "1.89.1 is already added as switch",
        "1.89.1 is already added as switch",
        "already configured as switch.yaml_switch (YAML)",
        "already configured as switch.yaml_switch (YAML)",
    ]


async def test_websocket_requires_admin(hass, hass_ws_client, hass_read_only_access_token, relay):
    client = await hass_ws_client(hass, hass_read_only_access_token)
    await client.send_json_auto_id({"type": "buspro/entities/list"})
    response = await client.receive_json()
    assert not response["success"] and response["error"]["code"] == "unauthorized"


async def test_yaml_lights_and_switches_still_load(hass):
    assert await async_setup_component(hass, "buspro", {"buspro": {"host": "127.0.0.1", "port": 6000}})
    assert await async_setup_component(hass, "light", {"light": [
        {"platform": "buspro", "devices": {"1.20.1": {"name": "Yaml light", "dimmable": False}}}]})
    assert await async_setup_component(hass, "switch", {"switch": [
        {"platform": "buspro", "devices": {"1.20.2": {"name": "Yaml relay"}}}]})
    await hass.async_block_till_done()

    assert hass.states.get("light.yaml_light").attributes["supported_color_modes"] == ["onoff"]
    assert hass.states.get("switch.yaml_relay").state == "off"
