"""Curtains, sensors, universal switches and floor heating added from the panel."""

import asyncio

import pytest
from homeassistant.setup import async_setup_component

from conftest import setup_integration
from fakebus import SimDevice
from test_panel_api import connect, scan

pytestmark = [
    pytest.mark.parametrize("expected_lingering_tasks", [True]),
    pytest.mark.parametrize("expected_lingering_timers", [True]),
]


def installation():
    return {
        "curtains": SimDevice((1, 40), 0x02CF, "Užuolaidos", functions=[(2, 2, 1)], curtains={1: 0},
                              channel_names={1: "Langas", 2: "Langas"}),
        # Answers ReadSensorStatus: [ok, temperature + 20, illuminance, motion, sonic, dry contacts]
        "sensor": SimDevice((1, 30), 0x0134, "12in1 Holas", sensor_status=[0xF8, 42, 1, 44, 0, 0, 0, 0]),
        "panel": SimDevice((1, 60), 0x0852, "Panelė", functions=[(4, 1, 4), (5, 2, 1)], temperature=21),
        "dlp": SimDevice((1, 42), 0x238C, "2A Belos", functions=[(4, 1, 8), (8, 1, 1)], floor_heating=True),
        "logic": SimDevice((56, 54), 0x0453, universal_switches={100: False, 101: False}),
    }


async def settle(hass):
    for _ in range(3):
        await asyncio.sleep(0)
        await hass.async_block_till_done()


@pytest.fixture
async def bus(hass, hass_ws_client):
    devices = installation()
    _entry, module, bus = await setup_integration(hass, list(devices.values()))
    bus.start()
    client = await connect(hass, hass_ws_client)
    return devices, bus, client


async def add(client, *entities):
    return await client.result({"type": "buspro/entities/add", "entities": list(entities)})


async def test_scan_offers_sensor_and_heating_features(hass, bus):
    _devices, _bus, client = bus
    await scan(client)
    devices = {d["address"]: d for d in (await client.result({"type": "buspro/devices"}))["scan"]["devices"]}

    def kinds(address):
        return [(c["kind"], c["number"], c["entity_kind"]) for c in devices[address]["channels"]]

    assert kinds("1.40") == [("curtain", 1, "curtain")]
    assert kinds("1.30") == [("temperature", 1, "temperature"), ("illuminance", 1, "illuminance"),
                             ("motion", 1, "motion"), ("dry_contact", 1, "dry_contact_1"),
                             ("dry_contact", 2, "dry_contact_2")]
    assert kinds("1.60") == [("temperature", 1, "temperature")]
    assert kinds("1.42") == [("floor_heating", 1, "floor_heating")]
    assert devices["1.40"]["channels"][0]["name"] == "Langas"


async def test_curtain(hass, bus):
    devices, _bus, client = bus
    result = await add(client, {"kind": "curtain", "platform": "cover", "address": "1.40", "channel": 1,
                                "name": "Langas", "opening_time": 30})
    assert result["added"] == ["1.40.curtain.1"]
    await settle(hass)
    assert hass.states.get("cover.langas") is not None

    await hass.services.async_call("cover", "open_cover", {"entity_id": "cover.langas"}, blocking=True)
    await settle(hass)
    assert devices["curtains"].curtains[1] == 1


async def test_sensor_readings(hass, bus):
    devices, fake_bus, client = bus
    common = {"address": "1.30", "device_model": "0x0134"}
    await add(client,
              {**common, "kind": "temperature", "platform": "sensor", "name": "Holo temperatūra"},
              {**common, "kind": "illuminance", "platform": "sensor", "name": "Holo šviesa"},
              {**common, "kind": "motion", "platform": "binary_sensor", "name": "Holo judesys"},
              {**common, "kind": "dry_contact_2", "platform": "binary_sensor", "name": "Holo durys"},
              {"address": "1.60", "kind": "temperature", "platform": "sensor", "name": "Panelės temperatūra",
               "device_category": "panel"})
    await settle(hass)

    # 12-in-1 broadcast: temperature 42 - 20, illuminance 300 lx, motion, dry contact 2 closed.
    fake_bus.broadcast(devices["sensor"], 0x1647, [42, 1, 44, 1, 0, 0, 1])
    await settle(hass)
    assert hass.states.get("sensor.holo_temperatura").state == "22"
    assert hass.states.get("sensor.holo_sviesa").state == "300"
    assert hass.states.get("binary_sensor.holo_judesys").state == "on"
    assert hass.states.get("binary_sensor.holo_judesys").attributes["device_class"] == "motion"
    assert hass.states.get("binary_sensor.holo_durys").state == "on"
    # The panel is asked with ReadTemperature (0xE3E7) when its sensor is added.
    assert hass.states.get("sensor.paneles_temperatura").state == "21"


async def test_universal_switches(hass, bus):
    devices, fake_bus, client = bus
    await add(client,
              {"kind": "universal_switch", "platform": "switch", "address": "56.54", "channel": 100, "name": "Režimas"},
              {"kind": "universal_switch", "platform": "binary_sensor", "address": "56.54", "channel": 101,
               "name": "Apsauga"})
    await settle(hass)

    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.rezimas"}, blocking=True)
    await settle(hass)
    assert devices["logic"].universal_switches[100] is True
    assert hass.states.get("switch.rezimas").state == "on"

    fake_bus.broadcast(devices["logic"], 0xE01D, [101, 1])
    await settle(hass)
    assert hass.states.get("binary_sensor.apsauga").state == "on"

    listed = (await client.result({"type": "buspro/entities/list"}))["entities"]
    assert {e["key"] for e in listed} == {"56.54.universal_switch.100", "56.54.universal_switch.101"}


async def test_floor_heating(hass, bus):
    devices, _bus, client = bus
    await add(client, {"kind": "floor_heating", "platform": "climate", "address": "1.42", "name": "Belos šildymas"})
    await settle(hass)
    state = hass.states.get("climate.belos_sildymas")
    assert (state.state, state.attributes["current_temperature"], state.attributes["temperature"],
            state.attributes["preset_mode"]) == ("off", 22, 24, "normal")

    await hass.services.async_call("climate", "set_temperature", {"entity_id": "climate.belos_sildymas",
                                                                  "temperature": 23}, blocking=True)
    await hass.services.async_call("climate", "set_hvac_mode", {"entity_id": "climate.belos_sildymas",
                                                                "hvac_mode": "heat"}, blocking=True)
    await hass.services.async_call("climate", "set_preset_mode", {"entity_id": "climate.belos_sildymas",
                                                                  "preset_mode": "night"}, blocking=True)
    await settle(hass)
    # [temperature type, current, status, mode, normal, day, night, away]
    assert devices["dlp"].floor_heating == [0, 22, 1, 3, 23, 21, 19, 18]
    state = hass.states.get("climate.belos_sildymas")
    assert (state.state, state.attributes["temperature"], state.attributes["preset_mode"]) == ("heat", 19, "night")


async def test_invalid_kind_platform_and_yaml_sensor(hass, hass_ws_client):
    assert await async_setup_component(hass, "buspro", {"buspro": {"host": "127.0.0.1", "port": 6000}})
    assert await async_setup_component(hass, "binary_sensor", {"binary_sensor": [
        {"platform": "buspro", "devices": [{"address": "1.30", "name": "Yaml motion", "type": "motion"}]}]})
    await hass.async_block_till_done()
    await setup_integration(hass, list(installation().values()))
    client = await connect(hass, hass_ws_client)

    result = await add(client,
                       {"kind": "curtain", "platform": "light", "address": "1.40", "name": "Wrong"},
                       {"kind": "motion", "platform": "binary_sensor", "address": "1.30", "name": "Again"},
                       {"kind": "temperature", "platform": "sensor", "address": "1.30", "name": "Fine"})
    assert result["added"] == ["1.30.temperature.1"]
    assert [r["reason"] for r in result["rejected"]] == [
        "curtain cannot be a light", "already configured as binary_sensor.yaml_motion (YAML)"]


async def test_added_sensor_shows_in_scan(hass, bus):
    _devices, _bus, client = bus
    await scan(client)
    await add(client, {"kind": "dry_contact_2", "platform": "binary_sensor", "address": "1.30", "name": "Durys"})
    await settle(hass)
    channels = {(c["kind"], c["number"]): c for c in next(
        d for d in (await client.result({"type": "buspro/devices"}))["scan"]["devices"] if d["address"] == "1.30")["channels"]}
    assert channels[("dry_contact", 2)]["entity_number"] == 1
    assert channels[("dry_contact", 2)]["entity"]["entity_id"] == "binary_sensor.durys"
    assert channels[("dry_contact", 1)]["entity"] is None
