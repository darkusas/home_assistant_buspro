import asyncio
import logging

from .control import _ReadStatusOfChannels

_LOGGER = logging.getLogger(__name__)



class Device(object):
    def __init__(self, buspro, device_address, name=""):
        # device_address = (subnet_id, device_id, ...)

        self._device_address = device_address
        self._buspro = buspro
        self._name = name
        self.device_updated_cbs = []
        self._registered_telegram_cbs = []  # (callback, postfix) registered by this device

    @property
    def name(self):
        return self._name

    def register_telegram_received_cb(self, telegram_received_cb, postfix=None):
        self._buspro.register_telegram_received_device_cb(telegram_received_cb, self._device_address, postfix)
        self._registered_telegram_cbs.append((telegram_received_cb, postfix))

    def unregister_telegram_received_cb(self, telegram_received_cb, postfix=None):
        self._buspro.unregister_telegram_received_device_cb(telegram_received_cb, self._device_address, postfix)
        if (telegram_received_cb, postfix) in self._registered_telegram_cbs:
            self._registered_telegram_cbs.remove((telegram_received_cb, postfix))

    def close(self):
        """Stop receiving telegrams and sending updates, e.g. when its entity is removed."""
        for telegram_received_cb, postfix in list(self._registered_telegram_cbs):
            self.unregister_telegram_received_cb(telegram_received_cb, postfix)
        self.device_updated_cbs.clear()

    def register_device_updated_cb(self, device_updated_cb):
        """Register device updated callback."""
        self.device_updated_cbs.append(device_updated_cb)

    def unregister_device_updated_cb(self, device_updated_cb):
        """Unregister device updated callback."""
        self.device_updated_cbs.remove(device_updated_cb)

    async def _device_updated(self):
        for device_updated_cb in self.device_updated_cbs:
            #await device_updated_cb(self)
            try:
                await device_updated_cb(self)
            except Exception:
                _LOGGER.exception("Device updated callback failed")
                
    async def _send_telegram(self, telegram):
        await self._buspro.network_interface.send_telegram(telegram)

    # async def _send_control(self, control):
    #     await self._buspro.network_interface.send_control(control)

    def _call_device_updated(self):
        asyncio.ensure_future(self._device_updated(), loop=self._buspro.loop)

    def _call_read_current_status_of_channels(self, run_from_init=False):

        async def read_current_state_of_channels():
            if run_from_init:
                await asyncio.sleep(3)

            read_status_of_channels = _ReadStatusOfChannels(self._buspro)
            read_status_of_channels.subnet_id, read_status_of_channels.device_id = self._device_address

            await read_status_of_channels.send()

        asyncio.ensure_future(read_current_state_of_channels(), loop=self._buspro.loop)
