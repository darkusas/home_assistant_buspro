"""Floor heating module (0x00CF): zone status, names, floor sensors, zone control and its scan."""

import asyncio

import pytest

from pybuspro.buspro import Buspro
from pybuspro.devices import FloorHeatingZone, FloorSensor
from pybuspro.devices.floor_heating_module import (
    build_zone_control, parse_floor_sensor, parse_floor_sensor_count, parse_zone_name, parse_zone_status,
)
from pybuspro.scanner import BusController, decode_state

from fakebus import FakeBus, SimDevice, zone_status
from fakes import GATEWAY, wire_telegram
from test_scanner import scan

MODULE = (1, 204)

# Captured from a 6-zone module (zone 4 in timer mode, valve open; zone 6 without a room sensor).
ZONE_4 = bytes.fromhex("0401000518151710001801050000")
ZONE_6 = bytes.fromhex("060000010a0a0a0a008000000000")
# Layout from the HDL operation code list as given by caligo-mentis/smart-bus (no room temperature).
OLD_LAYOUT = bytes.fromhex("012100021818161400011E010A")


def floor_sensor_payload(number, name, zone, temperature):
    rom = [0x28, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0x01, number]
    text = list(name.encode("cp1257"))[:20]
    return [number] + rom + [0, 0x0A] + text + [0] * (20 - len(text)) + [zone, temperature]


def module(**kwargs):
    return SimDevice(MODULE, 0x00CF, "Šildymas", functions=[(8, 0, 6)], heating_zones={
        1: ("Sandėlis", zone_status(1, room=21)),
        2: ("Darbo kamb", zone_status(2, mode=2, setpoints=(22, 21, 19, 16), room=23)),
        3: ("Svetainė", zone_status(3, mode=5, setpoints=(23, 22, 20, 16), timer=1, room=22, valve=True)),
        4: (None, zone_status(4, on=False, setpoints=(10, 10, 10, 10), room=0x80)),
    }, floor_sensors={1: ("Svetainės grindų temp", 3, 24), 2: ("Sandėlio grindų temp", 1, 22)}, **kwargs)


async def make(devices):
    buspro = Buspro((GATEWAY, ("", 6000)), asyncio.get_running_loop())
    buspro.network_interface = FakeBus(buspro, devices)
    return buspro, buspro.network_interface


async def settle():
    for _ in range(3):
        await asyncio.sleep(0)


def test_parse_captured_zone_status():
    zone = parse_zone_status(ZONE_4)
    assert (zone.zone, zone.on, zone.work_type, zone.temperature_type, zone.mode, zone.timer) == (4, True, 0, 0, 5, 0)
    assert zone.setpoints == {"normal": 24, "day": 21, "night": 23, "away": 16}
    assert (zone.room_temperature, zone.valve, zone.active_setpoint) == (24, True, "day")
    assert zone.as_dict()["target"] == 21

    unused = parse_zone_status(ZONE_6)
    assert (unused.on, unused.room_temperature) == (False, None)  # 0x80: no room sensor

    old = parse_zone_status(OLD_LAYOUT)
    assert (old.work_type, old.on, old.mode, old.room_temperature, old.valve) == (2, True, 2, None, True)
    assert parse_zone_status([1, 2, 3]) is None


def test_zone_control_keeps_what_it_does_not_change():
    zone = parse_zone_status(ZONE_4)
    assert build_zone_control(zone) == [4, 0x01, 0, 5, 24, 21, 23, 16, 1, 0]
    assert build_zone_control(zone, on=False, mode=2, setpoints={"day": 22}) == [4, 0x00, 0, 2, 24, 22, 23, 16, 1, 0]
    # A heating/cooling type in the high nibble stays as it is.
    assert build_zone_control(parse_zone_status(OLD_LAYOUT), on=False)[:2] == [1, 0x20]


def test_parse_zone_names_and_floor_sensors():
    assert parse_zone_name(bytes.fromhex("03005300760065007400610069006e011700000000")) == (3, "Svetainė")
    assert parse_zone_name([6] + [0] * 20) == (6, None)
    assert parse_floor_sensor_count(bytes.fromhex("00050500")) == 5

    sensor = parse_floor_sensor(floor_sensor_payload(4, "Sandėlio grindų temp", 1, 22))
    assert (sensor.number, sensor.name, sensor.zone, sensor.temperature) == (4, "Sandėlio grindų temp", 1, 22)
    assert sensor.rom == "28-AA-BB-CC-DD-EE-01-04"
    assert parse_floor_sensor(floor_sensor_payload(2, "", 0, 0x85)).temperature == -5
    assert parse_floor_sensor([3] + [0xFF] * 32) is None  # empty slot


def test_decode_zone_status_and_floor_sensor():
    [zone] = decode_state(wire_telegram(MODULE, (255, 255), 0x1C5D, list(ZONE_4), device_type=0x00CF))
    assert (zone.kind, zone.number, zone.value["temperature"], zone.value["valve"]) == ("heating_zone", 4, 24, True)
    [sensor] = decode_state(wire_telegram(MODULE, (1, 2), 0x1D17, floor_sensor_payload(2, "Grindys", 3, 23)))
    assert (sensor.kind, sensor.number, sensor.value) == ("floor_sensor", 2, 23)


def test_scan_finds_zones_and_floor_sensors():
    result, bus, _buspro = scan([module()])
    [device] = result.devices
    assert device.category == "floor_heating"
    zones = [(c.number, c.kind, c.name) for c in device.channels if c.kind == "heating_zone"]
    assert zones == [(1, "heating_zone", "Sandėlis"), (2, "heating_zone", "Darbo kamb"),
                     (3, "heating_zone", "Svetainė"), (4, "heating_zone", None), (5, "heating_zone", None),
                     (6, "heating_zone", None)]  # six zones from the module's self-description
    sensors = [c.to_dict() for c in device.channels if c.kind == "floor_sensor"]
    assert sensors == [
        {"number": 1, "kind": "floor_sensor", "name": "Svetainės grindų tem", "level": None, "zone": 3},  # 20 chars
        {"number": 2, "kind": "floor_sensor", "name": "Sandėlio grindų temp", "level": None, "zone": 1}]
    assert bus.sent_codes(MODULE).count(0x1D16) == 2
    assert 0x1C5C not in bus.sent_codes()  # the scan never controls anything


def test_zone_reads_then_controls():
    async def go():
        sim = module()
        buspro, bus = await make([sim])
        zone = FloorHeatingZone(buspro, MODULE, 3, "Svetainė")
        with pytest.raises(ValueError):
            await zone.set(on=False)  # state unknown yet

        await zone.read_status()
        await settle()
        before = (zone.is_on, zone.mode, zone.current_temperature, zone.target_temperature, zone.heating)
        await zone.set(temperature=21)  # timer mode at night: changes the night setpoint
        await settle()
        after_setpoint = (zone.target_temperature, zone.status.setpoints)
        await zone.set(mode=2, temperature=24)
        await zone.set(on=False)  # sent before the module's answer, builds on the previous command
        await settle()
        return before, after_setpoint, sim.zone_commands, zone

    before, after_setpoint, commands, zone = asyncio.run(go())
    assert before == (True, 5, 22, 20, True)
    assert after_setpoint == (21, {"normal": 23, "day": 22, "night": 21, "away": 16})
    assert commands == [[3, 1, 0, 5, 23, 22, 21, 16, 1, 0], [3, 1, 0, 2, 23, 24, 21, 16, 1, 0],
                        [3, 0, 0, 2, 23, 24, 21, 16, 1, 0]]
    assert (zone.is_on, zone.mode, zone.target_temperature) == (False, 2, 24)  # from the module's 0x1C5D
    assert zone.device_identifier == "(1, 204)-heating_zone-3"


def test_zone_ignores_other_zones_and_floor_sensor_reads():
    async def go():
        buspro, _bus = await make([module()])
        zone = FloorHeatingZone(buspro, MODULE, 1)
        sensor = FloorSensor(buspro, MODULE, 2, "Sandėlio grindys")
        await FloorHeatingZone(buspro, MODULE, 2).read_status()
        await settle()
        other_zone_only = zone.known
        await sensor.read_status()
        await settle()
        return other_zone_only, sensor

    other_zone_only, sensor = asyncio.run(go())
    assert not other_zone_only
    assert (sensor.temperature, sensor.info.zone, sensor.device_identifier) == (22, 1, "(1, 204)-floor_sensor-2")


def test_controller_confirms_zone_commands():
    async def go():
        sim = module()
        buspro, _bus = await make([sim])
        controller = BusController(buspro, confirm_timeout=0.05, min_command_interval=0)
        off = await controller.set_heating_zone(MODULE, 1, on=False)
        setpoint = await controller.set_heating_zone(MODULE, 2, temperature=25)  # day mode: day setpoint
        missing = await controller.set_heating_zone(MODULE, 6, on=True)
        return off, setpoint, missing, sim

    off, setpoint, missing, sim = asyncio.run(go())
    assert (off.confirmed, off.value, off.confirmed_by, off.kind) == (True, 0, "0x1C5D", "heating_zone")
    assert (setpoint.confirmed, setpoint.requested, setpoint.value) == (True, 25, 25)
    assert sim.heating_zones[2][1][4:8] == [22, 25, 19, 16]
    assert (missing.confirmed, missing.error) == (False, "No answer from the device")


def test_controller_does_not_take_a_spontaneous_report_as_confirmation():
    class IgnoresControl(SimDevice):
        def handle(self, telegram):
            if int.from_bytes(telegram.operate_code_raw, "big") == 0x1C5C:
                # Answers with the old state, like the broadcast after a room temperature change.
                return [self.reply(0x1C5D, self.heating_zones[1][1], (255, 255))]
            return super().handle(telegram)

    async def go():
        sim = IgnoresControl(MODULE, 0x00CF, heating_zones={1: ("Sandėlis", zone_status(1, setpoints=(21, 21, 20, 14)))})
        buspro, _bus = await make([sim])
        controller = BusController(buspro, confirm_timeout=0.05, min_command_interval=0)
        return await controller.set_heating_zone(MODULE, 1, temperature=23)

    result = asyncio.run(go())
    assert (result.confirmed, result.value, result.confirmed_by) == (False, 21, "0x1C5F")
