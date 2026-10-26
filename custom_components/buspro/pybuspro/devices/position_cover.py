"""Curtains that know their position and go to a percentage themselves (e.g. curtain motors).

The HDL operation code list (as given by caligo-mentis/smart-bus) addresses the position of
curtain n as curtain n + 16: CurtainSwitchControl (0xE3E0) [n + 16, percent] moves it there,
and CurtainSwitchStatus (0xE3E2) [n + 16] is answered with 0xE3E3 [n + 16, percent]. Open, close
and stop stay [n, 1 | 2 | 0]. 0 % is taken as closed, like Home Assistant; this has not yet been
tried on real hardware.
"""

from .device import Device
from ..helpers.enums import OperateCode

POSITION_OFFSET = 16
CURTAIN_ANSWER_CODES = (0xE3E1, 0xE3E3)
STOP, OPEN, CLOSE = 0, 1, 2


def parse_curtain_position(payload):
    """(curtain, percent) from a 0xE3E1/0xE3E3 payload about a position, else None."""
    if len(payload) >= 2 and payload[0] > POSITION_OFFSET and payload[1] <= 100:
        return payload[0] - POSITION_OFFSET, payload[1]
    return None


class PositionCover(Device):
    def __init__(self, buspro, device_address, curtain, name=""):
        super().__init__(buspro, device_address, name)
        self.curtain = curtain
        self.position = None  # 0 closed .. 100 open
        self.status = None  # STOP, OPEN (opening) or CLOSE (closing)
        self.register_telegram_received_cb(self._telegram_received_cb)

    def _telegram_received_cb(self, telegram):
        if int.from_bytes(telegram.operate_code_raw, "big") not in CURTAIN_ANSWER_CODES or len(telegram.payload) < 2:
            return
        position = parse_curtain_position(telegram.payload)
        if position is not None and position[0] == self.curtain:
            self.position = position[1]
        elif telegram.payload[0] == self.curtain and telegram.payload[1] in (STOP, OPEN, CLOSE):
            self.status = telegram.payload[1]
        else:
            return
        self._call_device_updated()

    @property
    def is_opening(self):
        return self.status == OPEN

    @property
    def is_closing(self):
        return self.status == CLOSE

    async def read_position(self):
        await self._send(OperateCode.CurtainSwitchStatus, [self.curtain + POSITION_OFFSET])

    async def read_status(self):
        await self._send(OperateCode.CurtainSwitchStatus, [self.curtain])

    async def set_position(self, position):
        await self._send(OperateCode.CurtainSwitchControl, [self.curtain + POSITION_OFFSET, int(position)])

    # Named like Cover's; close() is Device's, which stops listening to the bus.
    async def set_open(self):
        await self._send(OperateCode.CurtainSwitchControl, [self.curtain, OPEN])

    async def set_close(self):
        await self._send(OperateCode.CurtainSwitchControl, [self.curtain, CLOSE])

    async def set_stop(self):
        await self._send(OperateCode.CurtainSwitchControl, [self.curtain, STOP])

    async def _send(self, operate_code, payload):
        await self._send_telegram(self._buspro.build_telegram(self._device_address, operate_code, payload))

    @property
    def device_identifier(self):
        # The same as Cover, so switching a curtain between time and position control keeps its entity.
        return f"{self._device_address}-{self.curtain}"
