import asyncio

import pytest

from pybuspro.buspro import Buspro
from pybuspro.devices import FloorHeating, Sensor
from pybuspro.scanner import decode_state

from fakebus import FakeBus, SimDevice
from fakes import GATEWAY, wire_telegram


async def settle():
    for _ in range(3):
        await asyncio.sleep(0)


def test_floor_heating_reads_then_controls():
    async def go():
        dlp = SimDevice((1, 42), 0x238C, floor_heating=True)
        buspro = Buspro((GATEWAY, ("", 6000)), asyncio.get_running_loop())
        bus = FakeBus(buspro, [dlp])
        buspro.network_interface = bus
        heating = FloorHeating(buspro, (1, 42), "Belos")
        with pytest.raises(ValueError):
            await heating.set(on=True)  # state unknown yet

        await heating.read_status()
        await settle()
        before = (heating.current_temperature, heating.is_on, heating.mode, heating.target_temperature)
        await heating.set(on=True, temperature=23)
        await settle()
        sent = [t.payload for t in bus.sent if t.operate_code_raw == b"\x19\x46"]
        return before, sent, heating

    before, sent, heating = asyncio.run(go())
    assert before == (22, False, 1, 24)
    assert sent == [[0, 1, 1, 23, 21, 19, 18]]  # type, status, mode, normal, day, night, away
    assert heating.is_on and heating.target_temperature == 23  # from the device's 0x1947 answer
    assert heating.setpoints == {"normal": 23, "day": 21, "night": 19, "away": 18}


def test_floor_heating_setpoint_follows_mode():
    async def go():
        buspro = Buspro((GATEWAY, ("", 6000)), asyncio.get_running_loop())
        heating = FloorHeating(buspro, (5, 222))
        # A DLP panel's own broadcast, as captured: off, night mode.
        buspro._callback_all_messages(wire_telegram((5, 222), (255, 255), 0x1947, [0xF8, 0, 0, 3, 28, 21, 19, 18],
                                                    device_type=0x0095))
        return heating

    heating = asyncio.run(go())
    assert (heating.is_on, heating.mode, heating.target_temperature, heating.current_temperature) == (False, 3, 19, None)


def test_sensor_reads_signed_temperature_answers():
    async def go():
        buspro = Buspro((GATEWAY, ("", 6000)), asyncio.get_running_loop())
        sensor = Sensor(buspro, (1, 62), name="Lauke")
        buspro._callback_all_messages(wire_telegram((1, 62), (1, 204), 0xE3E8, [1, 0x95], device_type=0x0148))
        negative = sensor.temperature
        buspro._callback_all_messages(wire_telegram((1, 62), (1, 204), 0xE3E8, [1, 0x15], device_type=0x0148))
        return negative, sensor.temperature

    assert asyncio.run(go()) == (-21, 21)


def test_decode_floor_heating_motion_and_temperature_modules():
    def updates(code, payload):
        return [(u.kind, u.number, u.value) for u in decode_state(wire_telegram((1, 42), (255, 255), code, payload))]

    assert updates(0x1945, [0, 0x17, 0, 1, 0x18, 0x15, 0x13, 0x12, 0, 0]) == [("floor_heating", None, {
        "temperature": 23, "status": 0, "mode": 1, "normal": 24, "day": 21, "night": 19, "away": 18})]
    assert updates(0x1947, [0xF8, 0, 1, 2, 28, 21, 19, 18])[0][2]["mode"] == 2
    assert updates(0xDB01, [0, 0, 0, 1, 0, 0, 0, 0]) == [("sensor", None, {"motion": True})]
    # Captured from a temperature module: channel 0x17, 22.4 °C as float32.
    assert updates(0x1949, list(bytes.fromhex("17c059b341"))) == [("temperature_channel", 0x17, 22.4)]


def test_floor_heating_commands_back_to_back():
    """A second command sent before the first is answered must not undo the first."""
    async def go():
        dlp = SimDevice((1, 42), 0x238C, floor_heating=True)
        buspro = Buspro((GATEWAY, ("", 6000)), asyncio.get_running_loop())
        buspro.network_interface = FakeBus(buspro, [dlp])
        heating = FloorHeating(buspro, (1, 42))
        await heating.read_status()
        await settle()
        await heating.set(on=True)
        await heating.set(temperature=26)  # no answer processed in between
        await heating.set(mode=3)
        await settle()
        return dlp.floor_heating

    # [temperature type, current, status, mode, normal, day, night, away]
    assert asyncio.run(go()) == [0, 22, 1, 3, 26, 21, 19, 18]
