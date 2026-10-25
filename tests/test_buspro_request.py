import asyncio

from pybuspro.buspro import Buspro
from pybuspro.helpers.enums import OperateCode

from fakes import GATEWAY, FakeNetworkInterface, wire_telegram

REMARK = list("Rėlės 1".encode("cp1257")) + [0] * 13


def make_buspro(responder):
    buspro = Buspro((GATEWAY, ("", 6000)), asyncio.get_running_loop())
    buspro.network_interface = FakeNetworkInterface(buspro, responder)
    return buspro


def test_request_returns_matching_reply():
    def responder(sent):
        if sent.operate_code is OperateCode.ReadDeviceRemark:
            return [wire_telegram(sent.target_address, (200, 200), OperateCode.ReadDeviceRemarkResponse, REMARK)]

    async def run():
        buspro = make_buspro(responder)
        reply = await buspro.request((1, 89), OperateCode.ReadDeviceRemark,
                                     response_operate_code=OperateCode.ReadDeviceRemarkResponse)
        return buspro, reply

    buspro, reply = asyncio.run(run())
    assert reply.source_address == (1, 89)
    assert reply.payload == REMARK
    assert buspro._telegram_listeners == []


def test_request_ignores_other_devices_and_times_out():
    def responder(sent):
        return [wire_telegram((1, 90), (200, 200), OperateCode.ReadDeviceRemarkResponse, REMARK)]

    async def run():
        buspro = make_buspro(responder)
        reply = await buspro.request((1, 89), OperateCode.ReadDeviceRemark,
                                     response_operate_code=OperateCode.ReadDeviceRemarkResponse, timeout=0.05)
        return buspro, reply

    buspro, reply = asyncio.run(run())
    assert reply is None
    assert buspro._telegram_listeners == []


def test_request_retries_until_answered():
    attempts = []

    def responder(sent):
        attempts.append(sent)
        if len(attempts) == 2:
            return [wire_telegram((1, 89), (200, 200), OperateCode.ReadStatusOfChannelsResponse, [2, 100, 0])]

    async def run():
        buspro = make_buspro(responder)
        return await buspro.request((1, 89), OperateCode.ReadStatusOfChannels,
                                    response_operate_code=OperateCode.ReadStatusOfChannelsResponse,
                                    timeout=0.05, retries=2)

    reply = asyncio.run(run())
    assert reply.payload == [2, 100, 0]
    assert len(attempts) == 2


def test_request_with_raw_codes_and_match():
    """Unknown/unverified codes work as raw values; match() picks the right channel."""
    def responder(sent):
        channel = sent.payload[0]
        return [
            wire_telegram((1, 89), (200, 200), 0xF00F, [channel + 1] + REMARK),
            wire_telegram((1, 89), (200, 200), 0xF00F, [channel] + REMARK),
        ]

    async def run():
        buspro = make_buspro(responder)
        reply = await buspro.request((1, 89), [0xF0, 0x0E], [3], response_operate_code=0xF00F,
                                     match=lambda telegram: telegram.payload[0] == 3)
        return buspro, reply

    buspro, reply = asyncio.run(run())
    assert reply.payload[0] == 3
    assert buspro.network_interface.sent[0].operate_code_raw == b"\xf0\x0e"


def test_broadcast_request_accepts_any_source():
    def responder(sent):
        return [wire_telegram((3, 7), (200, 200), OperateCode.ReadDeviceModuleResponse, [9, 9] + REMARK)]

    async def run():
        buspro = make_buspro(responder)
        return await buspro.request((255, 255), OperateCode.ReadDeviceModule, [9, 9],
                                    response_operate_code=OperateCode.ReadDeviceModuleResponse)

    reply = asyncio.run(run())
    assert reply.source_address == (3, 7)
