import asyncio

import pytest

from pybuspro.buspro import Buspro
from pybuspro.devices.generic import Generic
from pybuspro.helpers.enums import DeviceType, OperateCode
from pybuspro.helpers.generics import Generics
from pybuspro.helpers.telegram_helper import TelegramHelper
from pybuspro.transport.network_interface import NetworkInterface

from fakes import GATEWAY, wire_telegram


def test_known_operate_code_round_trip():
    telegram = wire_telegram((1, 89), (200, 200), OperateCode.ReadStatusOfChannelsResponse, [3, 0, 100, 0])

    assert telegram.operate_code is OperateCode.ReadStatusOfChannelsResponse
    assert telegram.operate_code_raw == b"\x00\x34"
    assert telegram.source_address == (1, 89)
    assert telegram.source_device_type is DeviceType.SB_DN_R0816
    assert telegram.source_device_type_raw == b"\x01\xac"
    assert telegram.payload == [3, 0, 100, 0]


def test_unknown_codes_are_kept_raw():
    telegram = wire_telegram((1, 50), (200, 200), 0x1234, [7], device_type=0x0141)

    assert telegram.operate_code is None
    assert telegram.operate_code_raw == b"\x12\x34"
    assert telegram.source_device_type is None
    assert telegram.source_device_type_raw == b"\x01\x41"
    assert "0x1234" in str(telegram)


def test_identification_codes_have_canonical_names():
    assert OperateCode(b"\x00\x0e") is OperateCode.ReadDeviceRemark
    assert OperateCode(b"\x00\x0e").name == "ReadDeviceRemark"
    # The older name is kept as an alias.
    assert OperateCode.QUERY_12in1_FROM_SETUP_TOOL_1 is OperateCode.ReadDeviceRemark
    assert OperateCode(b"\xe5\x49") is OperateCode.ReadDeviceModuleResponse
    assert OperateCode(b"\xf0\x0f") is OperateCode.ReadChannelRemarkResponse


@pytest.mark.parametrize("value", [OperateCode.ReadDeviceRemark, b"\x00\x0e", [0, 14], (0, 14), 0x000E])
def test_operate_code_to_bytes(value):
    assert Generics.operate_code_to_bytes(value) == b"\x00\x0e"


@pytest.mark.parametrize("value", [[1], [1, 2, 3], 0x10000, -1])
def test_operate_code_to_bytes_rejects_bad_values(value):
    with pytest.raises(ValueError):
        Generics.operate_code_to_bytes(value)


def test_bad_crc_is_dropped():
    telegram = wire_telegram((1, 89), (200, 200), OperateCode.ReadDeviceRemark)
    data = bytearray(telegram.udp_data)
    data[-1] ^= 0xFF

    assert TelegramHelper().build_telegram_from_udp_data(bytes(data), GATEWAY) is None


def test_send_message_service_accepts_list_operate_code():
    """Regression: buspro.send_message passes the operate code as [hi, lo]."""
    sent = []

    class CapturingInterface:
        async def send_telegram(self, telegram):
            sent.append(bytes(TelegramHelper().build_send_buffer(telegram)))

    class FakeBuspro:
        network_interface = CapturingInterface()

    asyncio.run(Generic(FakeBuspro(), (1, 74), [1, 100, 0, 3], [4, 78]).run())

    parsed = TelegramHelper().build_telegram_from_udp_data(sent[0], GATEWAY)
    assert parsed.operate_code_raw == b"\x04\x4e"
    assert parsed.target_address == (1, 74)
    assert parsed.payload == [1, 100, 0, 3]


def test_none_telegram_is_ignored():
    async def run():
        buspro = Buspro((GATEWAY, ("", 6000)), asyncio.get_running_loop())
        calls = []
        buspro.register_telegram_received_device_cb(calls.append, (1, 89))
        buspro.add_telegram_listener(calls.append)

        buspro._callback_all_messages(None)
        return calls

    assert asyncio.run(run()) == []


def test_listeners_are_isolated_and_removable():
    async def run():
        buspro = Buspro((GATEWAY, ("", 6000)), asyncio.get_running_loop())
        seen = []

        def broken(_telegram):
            raise RuntimeError("boom")

        buspro.add_telegram_listener(broken)
        remove = buspro.add_telegram_listener(seen.append)
        telegram = wire_telegram((1, 89), (200, 200), OperateCode.ReadDeviceRemarkResponse)

        buspro._callback_all_messages(telegram)
        remove()
        remove()  # removing twice is harmless
        buspro._callback_all_messages(telegram)
        return seen

    assert len(asyncio.run(run())) == 1


def test_send_interval_spaces_telegrams():
    async def run():
        buspro = Buspro((GATEWAY, ("", 6000)), asyncio.get_running_loop())
        interface = NetworkInterface(buspro, (GATEWAY, ("", 6000)), min_send_interval=0.05)
        times = []

        class FakeUdpClient:
            async def send_message(self, _message):
                times.append(asyncio.get_running_loop().time())

        interface.udp_client = FakeUdpClient()
        telegram = Buspro.build_telegram((1, 89), OperateCode.ReadStatusOfChannels)
        await asyncio.gather(*(interface.send_telegram(telegram) for _ in range(3)))
        return times

    times = asyncio.run(run())
    assert len(times) == 3
    assert all(later - earlier >= 0.045 for earlier, later in zip(times, times[1:]))


def test_device_close_unregisters_callbacks():
    from pybuspro.devices import Switch

    async def run():
        buspro = Buspro((GATEWAY, ("", 6000)), asyncio.get_running_loop())
        switch = Switch(buspro, (1, 89), 3, "Test")
        switch.register_device_updated_cb(lambda device: None)
        registered = len(buspro._telegram_received_cbs)
        switch.close()
        switch.close()  # closing twice is harmless
        return registered, buspro._telegram_received_cbs, switch.device_updated_cbs

    registered, remaining, updated = asyncio.run(run())
    assert registered == 1 and remaining == [] and updated == []
