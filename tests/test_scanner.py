import asyncio
import json

import pytest

from pybuspro.buspro import Buspro
from pybuspro.scanner import BusScanner, ScannedChannel, ScanOptions

from fakebus import FakeBus, SimDevice
from fakes import GATEWAY

FAST = ScanOptions(search_rounds=3, search_interval=0.02, settle_time=0.01, request_timeout=0.02)


def installation():
    """Device mix from the stage 2 acceptance criteria, modelled on the captures."""
    return [
        SimDevice((1, 89), 0x01AC, "Rėlės 1 aukštas", functions=[(1, 1, 8)], levels=[0, 100, 0, 0, 0, 0, 0, 0],
                  channel_names={1: "Virtuvė", 2: "Koridorius", **{n: None for n in range(3, 9)}},
                  missed_searches=1),
        SimDevice((1, 20), 0x026D, "Dimeris", functions=[(1, 0, 6)], levels=[0, 50, 0, 0, 0, 0],
                  channel_names={n: f"Šviestuvas {n}" for n in range(1, 7)}),
        # Older relay: no 0xE549, only channel 1 answers 0xF00E.
        SimDevice((1, 201), 0x01C0, "Apšvietimas", levels=[0] * 7 + [100] + [0] * 4, channel_names={1: "Lauko"}),
        SimDevice((1, 30), 0x0134, "12in1 Holas", broadcasts=[(0x1647, [40, 1, 200, 0, 0, 0, 0])]),
        SimDevice((1, 40), 0x02CF, "Užuolaidos", functions=[(2, 2, 2)],
                  channel_names={1: "Langas A", 2: "Langas A", 3: "Langas B", 4: "Langas B"}),
        # DLP panel: answers neither search, only heard broadcasting.
        SimDevice((1, 50), 0x0095, answers_remark=False, broadcasts=[(0x1947, [0xF8, 0, 1, 1, 22, 22, 18, 15])]),
        SimDevice((1, 60), 0x0852, "Panelė", functions=[(0, 0, 1), (4, 1, 4), (5, 2, 1)]),
        # A PC running HDL Buspro Setup Tool.
        SimDevice((253, 254), 0xFFFE, answers_remark=False, broadcasts=[(0x000E, [])]),
    ]


async def run_scan(devices, options=FAST, on_progress=None):
    buspro = Buspro((GATEWAY, ("", 6000)), asyncio.get_running_loop())
    bus = FakeBus(buspro, devices)
    buspro.network_interface = bus
    bus.start()
    result = await BusScanner(buspro).scan(options, on_progress)
    return result, bus, buspro


def scan(devices, **kwargs):
    return asyncio.run(run_scan(devices, **kwargs))


def test_finds_devices_with_categories_and_channels():
    result, _bus, buspro = scan(installation())
    devices = {d.address: d for d in result.devices}

    assert set(devices) == {"1.20", "1.30", "1.40", "1.50", "1.60", "1.89", "1.201"}
    assert result.ignored_sources == 1  # the Setup Tool PC; our own echoes are not counted
    assert buspro._telegram_listeners == []
    assert {a: d.category for a, d in devices.items()} == {
        "1.89": "output_module", "1.20": "output_module", "1.201": "output_module", "1.30": "sensor",
        "1.40": "curtain_module", "1.50": "panel", "1.60": "panel"}

    relay = devices["1.89"]
    assert relay.remark == "Rėlės 1 aukštas"  # found although it missed the first search round
    assert relay.mac == "10:20:30:40:50:60:01:59"
    assert [c.kind for c in relay.channels] == ["relay"] * 8
    assert relay.channels[0] == ScannedChannel(1, "relay", "Virtuvė", 0)
    assert relay.channels[1] == ScannedChannel(2, "relay", "Koridorius", 100)
    assert relay.channels[2].name is None

    dimmer = devices["1.20"]
    assert [c.kind for c in dimmer.channels] == ["dimmer"] * 6
    assert dimmer.channels[1] == ScannedChannel(2, "dimmer", "Šviestuvas 2", 50)

    old_relay = devices["1.201"]
    assert old_relay.functions is None
    assert len(old_relay.channels) == 12
    assert {c.kind for c in old_relay.channels} == {"relay"}
    assert [c.name for c in old_relay.channels[:2]] == ["Lauko", None]

    assert devices["1.40"].channels == [ScannedChannel(1, "curtain", "Langas A"),
                                        ScannedChannel(2, "curtain", "Langas B")]
    assert devices["1.30"].remark == "12in1 Holas"
    assert devices["1.50"].type_code == 0x0095
    assert devices["1.60"].channels == []


def test_scan_is_read_only_and_targeted():
    _result, bus, _buspro = scan(installation())

    assert 0x0031 not in bus.sent_codes()  # never switches anything
    for address in [(1, 30), (1, 40), (1, 50), (1, 60)]:  # sensor, curtains, DLP, panel
        assert 0x0033 not in bus.sent_codes(address)
    for address in [(1, 89), (1, 20), (1, 201)]:
        assert 0x0033 in bus.sent_codes(address)


def test_discovery_repeats_search_and_excludes_described_devices():
    _result, bus, _buspro = scan(installation())
    broadcasts = [t for t in bus.sent if tuple(t.target_address) == (255, 255)]

    assert [int.from_bytes(t.operate_code_raw, "big") for t in broadcasts] == [0x000E, 0xE548] * 3
    first, *later = [t.payload for t in broadcasts if t.operate_code_raw == b"\xe5\x48"]
    assert first[2:] == []
    excluded = {tuple(later[0][i:i + 2]) for i in range(2, len(later[0]), 2)}
    assert {(1, 89), (1, 20), (1, 40), (1, 60)} <= excluded
    assert all(p[:2] == first[:2] for p in later)  # one session per scan


def test_exclude_list_rotates_in_windows_of_15():
    relays = [SimDevice((2, n), 0x01BE, f"R{n}", functions=[(1, 1, 1)], levels=[0]) for n in range(1, 21)]
    options = ScanOptions(search_rounds=3, search_interval=0.02, settle_time=0.01, request_timeout=0.02,
                          read_mac=False, read_channel_names=False)
    _result, bus, _buspro = scan(relays, options=options)
    payloads = [t.payload for t in bus.sent if t.operate_code_raw == b"\xe5\x48" and tuple(t.target_address) == (255, 255)]

    assert len(payloads[1]) == 2 + 15 * 2
    assert payloads[1][2:4] == [2, 1]
    assert payloads[2][2:4] == [2, 16]  # next window


def test_mixed_and_undescribed_output_kinds():
    devices = [
        SimDevice((3, 1), 0x0DCE, "Mixed", functions=[(1, 1, 2), (1, 0, 2)], levels=[0, 100, 0, 30]),
        SimDevice((3, 2), 0x1234, "Old", levels=[0, 40, 100]),
    ]
    result, _bus, _buspro = scan(devices)
    kinds = {d.address: [c.kind for c in d.channels] for d in result.devices}

    assert kinds == {"3.1": ["relay", "relay", "dimmer", "dimmer"], "3.2": ["relay", "dimmer", "relay"]}


def test_progress_and_serializable_result():
    phases = []
    result, _bus, _buspro = scan(installation(), on_progress=lambda p: phases.append(p.phase))

    assert phases[0] == "discovery" and phases[-1] == "done"
    assert {"channels", "identify", "mac", "names"} <= set(phases)
    data = json.loads(json.dumps(result.to_dict(), ensure_ascii=False))
    relay = next(d for d in data["devices"] if d["address"] == "1.89")
    assert relay["type_code"] == "0x01AC"
    assert relay["channels"][0] == {"number": 1, "kind": "relay", "name": "Virtuvė", "level": 0}


def test_second_scan_while_running_and_cancel_cleanup():
    async def run():
        buspro = Buspro((GATEWAY, ("", 6000)), asyncio.get_running_loop())
        buspro.network_interface = FakeBus(buspro, installation())
        scanner = BusScanner(buspro)
        slow = ScanOptions(search_rounds=1, search_interval=10, settle_time=0)
        task = asyncio.ensure_future(scanner.scan(slow))
        await asyncio.sleep(0.01)
        with pytest.raises(RuntimeError):
            await scanner.scan(FAST)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return scanner, buspro

    scanner, buspro = asyncio.run(run())
    assert not scanner.running
    assert buspro._telegram_listeners == []


def test_unknown_functions_fall_back_to_type_and_behaviour():
    devices = [
        SimDevice((4, 1), 0x0185, "Sensor", functions=[(16, 1, 1), (16, 4, 1)]),  # known type, odd functions
        SimDevice((4, 2), 0x7777, "Strange", functions=[(16, 1, 1)], levels=[0, 100]),  # answers 0x0033
        SimDevice((4, 3), 0x7778, "Silent", functions=[(16, 1, 1)]),
    ]
    result, bus, _buspro = scan(devices)
    categories = {d.address: d.category for d in result.devices}

    assert categories == {"4.1": "sensor", "4.2": "output_module", "4.3": "unknown"}
    assert 0x0033 not in bus.sent_codes((4, 1))


def test_silent_types_are_not_asked_for_self_description():
    _result, bus, _buspro = scan(installation())
    dlp = [int.from_bytes(t.operate_code_raw, "big") for t in bus.sent if tuple(t.target_address) == (1, 50)]

    assert 0xE548 not in dlp  # DLP panels never answer it
    assert dlp.count(0xF003) == 1  # MAC is read without retries
    assert 0xE548 in bus.sent_codes((1, 201))  # an old relay might still answer
