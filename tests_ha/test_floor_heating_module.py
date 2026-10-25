"""Floor heating module (0x00CF) zones and floor sensors added from the panel."""

import asyncio

import pytest
from homeassistant.helpers import entity_registry as er

from conftest import setup_integration
from fakebus import SimDevice, zone_status
from test_panel_api import connect, scan

pytestmark = [
    pytest.mark.parametrize("expected_lingering_tasks", [True]),
    pytest.mark.parametrize("expected_lingering_timers", [True]),
]

MODULE = "1.204"


def heating_module():
    return SimDevice((1, 204), 0x00CF, "Šildymas", functions=[(8, 0, 6)], heating_zones={
        1: ("Sandėlis", zone_status(1, room=21)),
        3: ("Svetainė", zone_status(3, mode=5, setpoints=(23, 22, 20, 16), timer=1, room=22, valve=True)),
    }, floor_sensors={1: ("Svetainės grindys", 3, 24)})


async def settle(hass):
    for _ in range(3):
        await asyncio.sleep(0)
        await hass.async_block_till_done()


@pytest.fixture
async def bus(hass, hass_ws_client):
    sim = heating_module()
    await setup_integration(hass, [sim])
    client = await connect(hass, hass_ws_client)
    return sim, client


async def add(client, *entities):
    return await client.result({"type": "buspro/entities/add", "entities": list(entities)})


async def test_scan_offers_zones_and_floor_sensors(hass, bus):
    _sim, client = bus
    await scan(client)
    [device] = (await client.result({"type": "buspro/devices"}))["scan"]["devices"]
    assert device["category"] == "floor_heating"
    assert [(c["kind"], c["number"], c["name"], c["entity_kind"], c["entity_number"]) for c in device["channels"]][:3] == [
        ("heating_zone", 1, "Sandėlis", "heating_zone", 1), ("heating_zone", 2, None, "heating_zone", 2),
        ("heating_zone", 3, "Svetainė", "heating_zone", 3)]
    sensor = device["channels"][-1]
    assert (sensor["kind"], sensor["name"], sensor["zone"], sensor["entity_kind"]) == (
        "floor_sensor", "Svetainės grindys", 3, "floor_sensor")

    # Refresh asks every zone and floor sensor; the answers come as live state.
    await client.result({"type": "buspro/state/subscribe", "address": MODULE})
    await client.result({"type": "buspro/device/refresh", "address": MODULE})
    updates = []
    while len(updates) < 3:  # zones 1 and 3 answer, zone 2..6 do not exist in the simulation
        updates += (await client.event())["updates"]
    by_kind = {(u["kind"], u["number"]): u["value"] for u in updates}
    assert by_kind[("heating_zone", 3)]["target"] == 20 and by_kind[("heating_zone", 3)]["valve"] is True
    assert by_kind[("floor_sensor", 1)] == 24


async def test_zone_as_climate(hass, bus):
    sim, client = bus
    result = await add(client,
                       {"kind": "heating_zone", "platform": "climate", "address": MODULE, "channel": 3,
                        "name": "Svetainė", "device_name": "Šildymas"},
                       {"kind": "heating_zone", "platform": "climate", "address": MODULE, "channel": 1,
                        "name": "Sandėlis", "device_name": "Šildymas"})
    assert result["added"] == ["1.204.heating_zone.3", "1.204.heating_zone.1"]
    await settle(hass)

    state = hass.states.get("climate.svetaine")
    assert (state.state, state.attributes["current_temperature"], state.attributes["temperature"],
            state.attributes["preset_mode"], state.attributes["hvac_action"]) == ("heat", 22, 20, "timer", "heating")
    assert hass.states.get("climate.sandelis").attributes["hvac_action"] == "idle"
    entities = er.async_get(hass)
    assert entities.async_get("climate.svetaine").unique_id == "(1, 204)-heating_zone-3"
    assert entities.async_get("climate.sandelis").unique_id == "(1, 204)-heating_zone-1"

    await hass.services.async_call("climate", "set_temperature", {"entity_id": "climate.svetaine",
                                                                  "temperature": 21}, blocking=True)
    await hass.services.async_call("climate", "set_preset_mode", {"entity_id": "climate.svetaine",
                                                                  "preset_mode": "day"}, blocking=True)
    await hass.services.async_call("climate", "set_hvac_mode", {"entity_id": "climate.svetaine",
                                                                "hvac_mode": "off"}, blocking=True)
    await settle(hass)
    # [zone, work, temperature type, mode, normal, day, night, away, valve, watering time]
    assert sim.zone_commands == [[3, 1, 0, 5, 23, 22, 21, 16, 1, 0], [3, 1, 0, 2, 23, 22, 21, 16, 1, 0],
                                 [3, 0, 0, 2, 23, 22, 21, 16, 1, 0]]
    state = hass.states.get("climate.svetaine")
    assert (state.state, state.attributes["temperature"], state.attributes["preset_mode"],
            state.attributes["hvac_action"]) == ("off", 22, "day", "off")


async def test_floor_sensor_as_sensor(hass, bus):
    _sim, client = bus
    await add(client, {"kind": "floor_sensor", "platform": "sensor", "address": MODULE, "channel": 1,
                       "name": "Svetainės grindys"})
    await settle(hass)
    state = hass.states.get("sensor.svetaines_grindys")
    assert (state.state, state.attributes["unit_of_measurement"], state.attributes["device_class"]) == (
        "24", "°C", "temperature")
    assert er.async_get(hass).async_get("sensor.svetaines_grindys").unique_id == "(1, 204)-floor_sensor-1"


async def test_test_zone_from_the_panel(hass, bus):
    sim, client = bus
    off = await client.result({"type": "buspro/channel/test", "address": MODULE, "channel": 1,
                               "target": "heating_zone", "action": "off"})
    setpoint = await client.result({"type": "buspro/channel/test", "address": MODULE, "channel": 3,
                                    "target": "heating_zone", "action": "level", "level": 21})
    assert (off["confirmed"], off["value"], off["confirmed_by"]) == (True, 0, "0x1C5D")
    assert (setpoint["confirmed"], setpoint["value"]) == (True, 21)
    assert sim.heating_zones[1][1][1] == 0  # off
    assert sim.heating_zones[3][1][4:8] == [23, 22, 21, 16]  # timer mode at night: the night setpoint

    response = await client.call({"type": "buspro/channel/test", "address": MODULE, "channel": 1,
                                  "target": "heating_zone", "action": "pulse"})
    assert response["error"]["code"] == "test_failed"
    response = await client.call({"type": "buspro/channel/test", "address": MODULE, "channel": 1,
                                  "target": "heating_zone", "action": "level", "level": 60})
    assert response["error"]["message"] == "A floor heating setpoint must be 5-35 °C"
