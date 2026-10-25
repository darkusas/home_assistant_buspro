"""Shared test helpers: wire-format telegrams and a fake network interface."""

import asyncio

from pybuspro.core.telegram import Telegram
from pybuspro.helpers.enums import DeviceType
from pybuspro.helpers.generics import Generics
from pybuspro.helpers.telegram_helper import TelegramHelper

GATEWAY = ("192.168.1.10", 6000)


def wire_telegram(source, target, operate_code, payload=(), device_type=DeviceType.SB_DN_R0816):
    """Build a telegram, encode it to UDP bytes and parse it back, as if received from the bus."""
    telegram = Telegram()
    telegram.source_address = source
    telegram.target_address = target
    if isinstance(device_type, DeviceType):
        telegram.source_device_type = device_type
    else:
        telegram.source_device_type = None
        telegram.source_device_type_raw = Generics.operate_code_to_bytes(device_type)
    telegram.operate_code = None
    telegram.operate_code_raw = Generics.operate_code_to_bytes(operate_code)
    telegram.payload = list(payload)

    helper = TelegramHelper()
    data = bytes(helper.build_send_buffer(telegram))
    return helper.build_telegram_from_udp_data(data, GATEWAY)


class FakeNetworkInterface:
    """Records sent telegrams; responder(sent) may return reply telegrams to deliver."""

    def __init__(self, buspro, responder=None):
        self.buspro = buspro
        self.responder = responder
        self.sent = []

    async def send_telegram(self, telegram):
        helper = TelegramHelper()
        data = bytes(helper.build_send_buffer(telegram))
        sent = helper.build_telegram_from_udp_data(data, GATEWAY)
        self.sent.append(sent)
        if self.responder is not None:
            for reply in self.responder(sent) or ():
                asyncio.get_running_loop().call_soon(self.buspro._callback_all_messages, reply)
