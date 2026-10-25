import asyncio

import pytest

from pybuspro.buspro import Buspro
from pybuspro.scanner import (
    CURTAIN_CLOSE, CURTAIN_OPEN, BusControlError, BusController, StateMonitor, decode_state,
)

from fakebus import FakeBus, SimDevice
from fakes import GATEWAY, wire_telegram

RELAY = (1, 89)


def relay(**kwargs):
    return SimDevice(RELAY, 0x01AC, "Rėlės", functions=[(1, 1, 4)], levels=[0, 100, 0, 0], **kwargs)


async def make(devices, min_command_interval=0):
    buspro = Buspro((GATEWAY, ("", 6000)), asyncio.get_running_loop())
    buspro.network_interface = FakeBus(buspro, devices)
    controller = BusController(buspro, confirm_timeout=0.05, min_command_interval=min_command_interval)
    return controller, buspro.network_interface


def run(coro):
    return asyncio.run(coro)


def test_set_channel_confirmed_by_broadcast_answer():
    async def go():
        device = relay()
        controller, _bus = await make([device])
        on = await controller.set_channel(RELAY, 1, 100)
        off = await controller.set_channel(RELAY, 2, 0)
        return on, off, device

    on, off, device = run(go())
    assert (on.confirmed, on.value, on.confirmed_by) == (True, 100, "0x0032")
    assert on.latency < 0.05 and on.error is None
    assert (off.confirmed, off.value) == (True, 0)
    assert device.levels == [100, 0, 0, 0]
    assert on.to_dict()["address"] == "1.89"


def test_set_channel_falls_back_to_status_read():
    async def go():
        controller, bus = await make([relay(confirms=False)])
        return await controller.set_channel(RELAY, 3, 100), bus

    result, bus = run(go())
    assert (result.confirmed, result.value, result.confirmed_by) == (True, 100, "0x0034")
    assert bus.sent_codes(RELAY) == [0x0031, 0x0033]


def test_set_channel_failure_and_silence():
    async def go():
        controller, _bus = await make([relay(fails=True)])
        failed = await controller.set_channel(RELAY, 1, 100)
        silent = await controller.set_channel((9, 9), 1, 100)
        return failed, silent

    failed, silent = run(go())
    assert not failed.confirmed and failed.value is None and failed.error == "The device reported a failure"
    assert not silent.confirmed and silent.value is None and silent.error == "No answer from the device"


def test_pulse_restores_previous_level():
    async def go():
        device = relay()
        controller, _bus = await make([device])
        result = await controller.pulse_channel(RELAY, 1, seconds=0.05)
        during = list(device.levels)
        await asyncio.sleep(0.15)
        return result, during, device.levels, controller.pending_pulses

    result, during, after, pending = run(go())
    assert (result.confirmed, result.value, result.previous) == (True, 100, 0)
    assert during[0] == 100 and after[0] == 0
    assert pending == []


def test_pulse_twice_keeps_original_level_and_set_cancels_pulse():
    async def go():
        device = relay()
        controller, _bus = await make([device])
        await controller.pulse_channel(RELAY, 1, seconds=0.05)
        second = await controller.pulse_channel(RELAY, 1, seconds=0.05)
        await asyncio.sleep(0.15)
        restored = device.levels[0]

        await controller.pulse_channel(RELAY, 3, seconds=0.05)
        await controller.set_channel(RELAY, 3, 100)  # the user decides: stays on
        await asyncio.sleep(0.15)
        return second, restored, device.levels[2]

    second, restored, kept = run(go())
    assert second.previous == 0 and restored == 0
    assert kept == 100


def test_pulse_restored_without_confirmation_and_on_shutdown():
    async def go():
        device = relay(confirms=False)
        controller, _bus = await make([device])
        result = await controller.pulse_channel(RELAY, 1, seconds=60)
        pending = controller.pending_pulses
        await controller.restore_pending()
        return result, pending, device.levels[0], controller.pending_pulses

    result, pending, level, after = run(go())
    assert result.confirmed_by == "0x0034"
    assert pending == [(RELAY, 1)] and level == 0 and after == []


def test_rate_limit_per_channel():
    async def go():
        controller, _bus = await make([relay()], min_command_interval=0.3)
        await controller.set_channel(RELAY, 1, 100)
        await controller.set_channel(RELAY, 2, 100)  # another channel is fine
        with pytest.raises(BusControlError):
            await controller.set_channel(RELAY, 1, 0)
        with pytest.raises(BusControlError):
            await controller.set_channel(RELAY, 2, 101)

    run(go())


def test_curtain_and_universal_switch():
    async def go():
        curtains = SimDevice((1, 40), 0x02CF, curtains={1: 0, 2: 0})
        logic = SimDevice((1, 60), 0x0453, universal_switches={100: False})
        quiet_curtains = SimDevice((1, 41), 0x02CF, curtains={1: 0}, confirms=False)
        controller, _bus = await make([curtains, logic, quiet_curtains])
        return (await controller.set_curtain((1, 40), 2, CURTAIN_OPEN),
                await controller.set_universal_switch((1, 60), 100, True),
                await controller.set_curtain((1, 41), 1, CURTAIN_CLOSE),
                curtains.curtains, logic.universal_switches)

    opened, switched, quiet, curtains, switches = run(go())
    assert (opened.confirmed, opened.value, opened.confirmed_by) == (True, CURTAIN_OPEN, "0xE3E1")
    assert (switched.confirmed, switched.value, switched.confirmed_by) == (True, 1, "0xE01D")
    assert (quiet.confirmed, quiet.confirmed_by) == (True, "0xE3E3")
    assert curtains == {1: 0, 2: CURTAIN_OPEN} and switches == {100: True}


def test_decode_state():
    def updates(code, payload):
        return [(u.kind, u.number, u.value) for u in decode_state(wire_telegram(RELAY, (255, 255), code, payload))]

    # Captured 0x0032: channel 6 off, 12 channels, channels 4, 11 and 12 on.
    assert updates(0x0032, [6, 0xF8, 0, 12, 0x08, 0x0C]) == [
        ("channel", 6, 0),
        ("channels_on", None, [False, False, False, True] + [False] * 6 + [True, True])]
    assert updates(0x0034, [2, 0, 100]) == [("channel", 1, 0), ("channel", 2, 100)]
    assert updates(0xE017, [2, 1, 0]) == [("universal_switch", 1, True), ("universal_switch", 2, False)]
    assert updates(0xE3E3, [1, 2]) == [("curtain", 1, 2)]
    assert updates(0xE3E5, [1, 0x95]) == [("sensor", None, {"temperature": -21})]
    assert updates(0x1647, [42, 1, 44, 1, 0, 0, 1]) == [("sensor", None, {
        "temperature": 22, "illuminance": 300, "motion": True, "dry_contact_1": False, "dry_contact_2": True})]
    assert updates(0x000F, [65]) == []


def test_state_monitor_subscriptions():
    async def go():
        controller, bus = await make([relay(), SimDevice((1, 20), 0x026D, levels=[0, 0])])
        monitor = StateMonitor(controller._buspro)
        everything, relay_only = [], []
        stop_all = monitor.subscribe(everything.append)
        stop_relay = monitor.subscribe(relay_only.append, address=RELAY)

        await controller.set_channel(RELAY, 1, 100)
        await controller.set_channel((1, 20), 2, 40)
        await asyncio.sleep(0)
        stop_relay()
        stop_all()
        listeners = list(controller._buspro._telegram_listeners)
        return everything, relay_only, monitor, listeners

    everything, relay_only, monitor, listeners = run(go())
    assert {u.address for u in everything} == {RELAY, (1, 20)}
    assert {u.address for u in relay_only} == {RELAY}
    assert monitor.latest[((1, 20), "channel", 2)].value == 40
    assert [u.value for u in monitor.snapshot(RELAY) if u.kind == "channel"] == [100]
    assert listeners == []
