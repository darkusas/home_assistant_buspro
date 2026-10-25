import asyncio
import time

from .udp_client import UDPClient
from ..helpers.telegram_helper import TelegramHelper
# from ..devices.control import Control

# Minimum gap between outgoing telegrams. A short frame already takes about this long
# on the 9600 baud bus, so this smooths bursts without lowering real throughput.
DEFAULT_MIN_SEND_INTERVAL = 0.02


class NetworkInterface:
    def __init__(self, buspro, gateway_address_send_receive, min_send_interval=DEFAULT_MIN_SEND_INTERVAL):
        self.buspro = buspro
        self.gateway_address_send_receive = gateway_address_send_receive
        self.udp_client = None
        self.callback = None
        self._init_udp_client()
        self._th = TelegramHelper()
        self._min_send_interval = min_send_interval
        self._send_lock = asyncio.Lock()
        self._last_send_time = None

    def _init_udp_client(self):
        self.udp_client = UDPClient(self.buspro, self.gateway_address_send_receive, self._udp_request_received)

    def _udp_request_received(self, data, address):
        if self.callback is not None:
            telegram = self._th.build_telegram_from_udp_data(data, address)
            self.callback(telegram)

    async def _send_message(self, message):
        await self.udp_client.send_message(message)

    """
    public methods
    """
    def register_callback(self, callback):
        self.callback = callback

    async def start(self):
        await self.udp_client.start()

    async def stop(self):
        if self.udp_client is not None:
            await self.udp_client.stop()
            self.udp_client = None

    async def send_telegram(self, telegram):
        message = self._th.build_send_buffer(telegram)

        gateway_address_send, _ = self.gateway_address_send_receive
        self.buspro.logger.debug(self._th.build_telegram_from_udp_data(message, gateway_address_send))

        async with self._send_lock:
            if self._min_send_interval > 0 and self._last_send_time is not None:
                delay = self._min_send_interval - (time.monotonic() - self._last_send_time)
                if delay > 0:
                    await asyncio.sleep(delay)
            await self.udp_client.send_message(message)
            self._last_send_time = time.monotonic()
