"""A curtain that goes to a percentage itself, added from the panel with position control."""

import asyncio

import pytest
from homeassistant.helpers import entity_registry as er

from conftest import setup_integration
from fakebus import SimDevice
from test_panel_api import connect, scan

pytestmark = [
    pytest.mark.parametrize("expected_lingering_tasks", [True]),
    pytest.mark.parametrize("expected_lingering_timers", [True]),
]


async def settle(hass):
    for _ in range(3):
        await asyncio.sleep(0)
        await hass.async_block_till_done()


@pytest.fixture
async def bus(hass, hass_ws_client):
    sim = SimDevice((1, 18), 0x25E4, "Svetainės užuolaida", functions=[(2, 0, 1)], curtains={1: 0},
                    curtain_positions={1: 40})
    await setup_integration(hass, [sim])
    client = await connect(hass, hass_ws_client)
    return sim, client


async def test_scan_shows_the_position(hass, bus):
    _sim, client = bus
    await scan(client)
    [device] = (await client.result({"type": "buspro/devices"}))["scan"]["devices"]
    [curtain] = device["channels"]
    assert (curtain["kind"], curtain["level"], curtain["entity_kind"]) == ("curtain", 40, "curtain")


async def test_position_cover(hass, bus):
    sim, client = bus
    result = await client.result({"type": "buspro/entities/add", "entities": [
        {"kind": "curtain", "platform": "cover", "address": "1.18", "channel": 1, "name": "Svetainės užuolaida",
         "position": True}]})
    assert result["added"] == ["1.18.curtain.1"]
    await settle(hass)
    state = hass.states.get("cover.svetaines_uzuolaida")
    assert (state.state, state.attributes["current_position"]) == ("open", 40)
    assert er.async_get(hass).async_get("cover.svetaines_uzuolaida").unique_id == "(1, 18)-1"

    await hass.services.async_call("cover", "set_cover_position", {"entity_id": "cover.svetaines_uzuolaida",
                                                                   "position": 70}, blocking=True)
    await settle(hass)
    assert sim.curtain_positions[1] == 70
    assert hass.states.get("cover.svetaines_uzuolaida").attributes["current_position"] == 70

    await hass.services.async_call("cover", "set_cover_position", {"entity_id": "cover.svetaines_uzuolaida",
                                                                   "position": 0}, blocking=True)
    await hass.services.async_call("cover", "open_cover", {"entity_id": "cover.svetaines_uzuolaida"}, blocking=True)
    await settle(hass)
    commands = [t.payload for t in sim.received if t.operate_code_raw == b"\xE3\xE0"]
    assert commands == [[17, 70], [17, 0], [1, 1]]

    await client.result({"type": "buspro/entities/remove", "keys": ["1.18.curtain.1"]})
    await settle(hass)
    assert hass.states.get("cover.svetaines_uzuolaida") is None


async def test_position_test_from_the_panel(hass, bus):
    sim, client = bus
    result = await client.result({"type": "buspro/channel/test", "address": "1.18", "channel": 1,
                                  "target": "curtain", "action": "level", "level": 25})
    assert (result["confirmed"], result["kind"], result["value"]) == (True, "curtain_position", 25)
    assert sim.curtain_positions[1] == 25
