"""Curtains that go to a percentage themselves: position read in the scan, live, tested and controlled."""

import asyncio

from pybuspro.buspro import Buspro
from pybuspro.devices import PositionCover
from pybuspro.scanner import BusController, decode_state

from fakebus import FakeBus, SimDevice
from fakes import GATEWAY, wire_telegram
from test_scanner import scan

MOTOR = (1, 18)


def motor(**kwargs):
    return SimDevice(MOTOR, 0x25E4, "Svetainės užuolaida", functions=[(2, 0, 1)], curtains={1: 0},
                     curtain_positions={1: 40}, **kwargs)


async def make(devices):
    buspro = Buspro((GATEWAY, ("", 6000)), asyncio.get_running_loop())
    buspro.network_interface = FakeBus(buspro, devices)
    return buspro, buspro.network_interface


async def settle():
    for _ in range(3):
        await asyncio.sleep(0)


def test_scan_reads_the_position_of_curtains_that_know_it():
    relay_curtains = SimDevice((1, 40), 0x02CF, "Užuolaidos", functions=[(2, 2, 2)], curtains={1: 0, 2: 0})
    result, bus, _buspro = scan([motor(), relay_curtains])
    devices = {d.address: d for d in result.devices}
    assert [(c.number, c.kind, c.level) for c in devices["1.18"].channels] == [(1, "curtain", 40)]
    assert [(c.number, c.level) for c in devices["1.40"].channels] == [(1, None), (2, None)]  # time-based
    assert [t.payload for t in bus.sent if t.operate_code_raw == b"\xE3\xE2"
            and tuple(t.target_address) == (1, 40)] == [[17], [18]]
    assert 0xE3E0 not in bus.sent_codes()  # the scan never moves a curtain


def test_decode_position_and_status():
    [position] = decode_state(wire_telegram(MOTOR, (255, 255), 0xE3E1, [17, 90]))
    [status] = decode_state(wire_telegram(MOTOR, (255, 255), 0xE3E3, [1, 2]))
    assert (position.kind, position.number, position.value) == ("curtain_position", 1, 90)
    assert (status.kind, status.number, status.value) == ("curtain", 1, 2)
    assert decode_state(wire_telegram(MOTOR, (255, 255), 0xE3E1, [17, 238])) == []  # not a position


def test_position_cover_reads_and_moves():
    async def go():
        sim = motor()
        buspro, bus = await make([sim])
        cover = PositionCover(buspro, MOTOR, 1, "Svetainė")
        await cover.read_position()
        await settle()
        before = cover.position
        await cover.set_position(70)
        await cover.set_open()
        await settle()
        return before, cover, [t.payload for t in bus.sent if t.operate_code_raw == b"\xE3\xE0"], sim

    before, cover, commands, sim = asyncio.run(go())
    assert before == 40
    assert commands == [[17, 70], [1, 1]]
    assert (cover.position, sim.curtain_positions[1]) == (70, 70)
    assert cover.device_identifier == "(1, 18)-1"  # the same as a time-based cover


def test_close_stops_listening():
    async def go():
        buspro, _bus = await make([motor()])
        cover = PositionCover(buspro, MOTOR, 1)
        before = len(buspro._telegram_received_cbs)
        cover.close()
        return before, len(buspro._telegram_received_cbs)

    before, after = asyncio.run(go())
    assert after == before - 1


def test_controller_confirms_a_position():
    async def go():
        buspro, _bus = await make([motor()])
        controller = BusController(buspro, confirm_timeout=0.05, min_command_interval=0)
        moved = await controller.set_curtain_position(MOTOR, 1, 25)
        missing = await controller.set_curtain_position((1, 99), 1, 25)
        return moved, missing

    moved, missing = asyncio.run(go())
    assert (moved.confirmed, moved.kind, moved.number, moved.value, moved.confirmed_by) == (
        True, "curtain_position", 1, 25, "0xE3E1")
    assert (missing.confirmed, missing.error) == (False, "No answer from the device")
