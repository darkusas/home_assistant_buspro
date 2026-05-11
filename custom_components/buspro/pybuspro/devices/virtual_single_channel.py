from .device import Device
from ..core.telegram import Telegram
from ..helpers.enums import DeviceType, OperateCode


class VirtualSingleChannel(Device):
    def __init__(self, buspro, device_address, channel_number, name="", initial_brightness=0):
        super().__init__(buspro, device_address, name)

        self._channel = channel_number
        self._brightness = self._normalize_level(initial_brightness)
        self._previous_brightness = self._brightness if self._brightness > 0 else None
        self.register_telegram_received_cb(self._telegram_received_cb)

    def _telegram_received_cb(self, telegram):
        if telegram is None:
            return

        if telegram.operate_code == OperateCode.SingleChannelControl:
            if len(telegram.payload) < 2:
                return

            channel = telegram.payload[0]
            if channel != self._channel:
                return

            self._brightness = self._normalize_level(telegram.payload[1])
            self._set_previous_brightness(self._brightness)
            self._call_device_updated()
            self._schedule_send_single_channel_control_response()

        elif telegram.operate_code == OperateCode.ReadStatusOfChannels:
            self._schedule_send_status_response(OperateCode.ReadStatusOfChannelsResponse, telegram.source_address)

        elif telegram.operate_code == OperateCode.ReadActualStatusOfSingleChannel:
            self._schedule_send_status_response(OperateCode.ReadActualStatusOfSingleChannelResponse, telegram.source_address)

    def _schedule_send_single_channel_control_response(self):
        async def _run():
            await self._send_single_channel_control_response()

        self._buspro.loop.create_task(_run())

    def _schedule_send_status_response(self, response_operate_code, source_address):
        async def _run():
            await self._send_status_response(response_operate_code, source_address)

        self._buspro.loop.create_task(_run())

    async def _send_single_channel_control_response(self):
        channel_total, channel_statuses = self._build_channel_status_list()
        telegram = Telegram()
        telegram.source_address = self._device_address
        telegram.source_device_type = DeviceType.PyBusPro
        telegram.target_address = (255, 255)
        telegram.operate_code = OperateCode.SingleChannelControlResponse
        telegram.payload = [self._channel, 0xF8, self._brightness, channel_total, *channel_statuses]
        await self._send_telegram(telegram)

    async def _send_status_response(self, response_operate_code, source_address):
        channel_total, channel_statuses = self._build_channel_status_list()
        telegram = Telegram()
        telegram.source_address = self._device_address
        telegram.source_device_type = DeviceType.PyBusPro
        telegram.target_address = source_address if source_address is not None else (255, 255)
        telegram.operate_code = response_operate_code
        telegram.payload = [channel_total, *channel_statuses]
        await self._send_telegram(telegram)

    def _build_channel_status_list(self):
        channel_total = 1
        channel_statuses = [self._brightness]
        return channel_total, channel_statuses

    @staticmethod
    def _normalize_level(value):
        try:
            value_int = int(value)
        except (TypeError, ValueError):
            value_int = 0
        return max(0, min(100, value_int))

    def _set_previous_brightness(self, brightness):
        if brightness > 0:
            self._previous_brightness = brightness

    async def set_on(self, running_time_seconds=0):
        await self.set_brightness(100, running_time_seconds)

    async def set_off(self, running_time_seconds=0):
        await self.set_brightness(0, running_time_seconds)

    async def set_brightness(self, intensity, running_time_seconds=0):
        self._brightness = self._normalize_level(intensity)
        self._set_previous_brightness(self._brightness)
        self._call_device_updated()
        await self._send_single_channel_control_response()

    async def read_status(self):
        self._call_device_updated()

    @property
    def supports_brightness(self):
        return True

    @property
    def previous_brightness(self):
        return self._previous_brightness

    @property
    def current_brightness(self):
        return self._brightness

    @property
    def is_on(self):
        return self._brightness > 0

    @property
    def device_identifier(self):
        return f"{self._device_address}-{self._channel}-virtual"
