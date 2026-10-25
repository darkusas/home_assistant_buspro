"""Switch channels, curtains, universal switches and floor heating zones on the bus, with confirmation.

Used to test a channel before it is added to Home Assistant: every command waits for
the device's own answer, so the result says what the device really did. A pulse
turns a channel on for a few seconds and then restores its previous level.
"""

import asyncio
import logging
import time
from dataclasses import asdict, dataclass

from ..devices.floor_heating_module import build_zone_control, parse_zone_status
from ..helpers.enums import OperateCode

_LOGGER = logging.getLogger(__name__)

DEFAULT_CONFIRM_TIMEOUT = 1.5
DEFAULT_PULSE_SECONDS = 2.0
MIN_COMMAND_INTERVAL = 0.3  # per channel, so repeated clicks do not hammer a load
SUCCESS = 0xF8

OUTPUT = "output"
CURTAIN = "curtain"
UNIVERSAL_SWITCH = "universal_switch"
HEATING_ZONE = "heating_zone"

CURTAIN_STOP = 0
CURTAIN_OPEN = 1
CURTAIN_CLOSE = 2


class BusControlError(Exception):
    pass


@dataclass
class CommandResult:
    address: str
    kind: str
    number: int
    requested: int
    confirmed: bool  # the device answered with the requested value
    value: int = None  # what the device reported, None if it did not answer
    confirmed_by: str = None  # operate code of the answer, e.g. "0x0032"
    latency: float = None  # seconds until the answer
    error: str = None
    previous: int = None  # pulse: level before the pulse, restored afterwards

    def to_dict(self):
        result = asdict(self)
        if result["latency"] is not None:
            result["latency"] = round(result["latency"], 3)
        return result


def _address_text(address):
    return "%d.%d" % tuple(address)


def _code_text(telegram):
    return "0x" + telegram.operate_code_raw.hex().upper()


class BusController:
    def __init__(self, buspro, confirm_timeout=DEFAULT_CONFIRM_TIMEOUT, min_command_interval=MIN_COMMAND_INTERVAL):
        self._buspro = buspro
        self._confirm_timeout = confirm_timeout
        self._min_command_interval = min_command_interval
        self._last_command = {}  # (address, kind, number) -> monotonic time
        self._pulses = {}  # (address, number) -> (restore task, previous level)

    @property
    def pending_pulses(self):
        return sorted(self._pulses)

    # Outputs (relay, dimmer, DMX channels)

    async def read_channel(self, address, channel):
        """Current level 0..100 of one channel, or None if the device does not answer."""
        reply = await self._buspro.request(tuple(address), OperateCode.ReadStatusOfChannels, (),
                                           OperateCode.ReadStatusOfChannelsResponse, timeout=self._confirm_timeout)
        if reply is None or not reply.payload or channel > reply.payload[0] or len(reply.payload) <= channel:
            return None
        return reply.payload[channel]

    async def set_channel(self, address, channel, level):
        """SingleChannelControl, confirmed by the device's broadcast answer or a status read."""
        address = tuple(address)
        if not 0 <= level <= 100:
            raise BusControlError(f"level must be 0-100, got {level}")
        self._check_rate((address, OUTPUT, channel))
        # An explicit command wins over a pulse that would restore the old level later.
        pending = self._pulses.pop((address, channel), None)
        if pending is not None:
            pending[0].cancel()
        return await self._set_channel(address, channel, level)

    async def pulse_channel(self, address, channel, level=100, seconds=DEFAULT_PULSE_SECONDS):
        """Set a channel for `seconds`, then restore the level it had before the first pulse."""
        address = tuple(address)
        if not 0 <= level <= 100:
            raise BusControlError(f"level must be 0-100, got {level}")
        self._check_rate((address, OUTPUT, channel))
        key = (address, channel)
        if key in self._pulses:
            # Pulsing again extends the pulse but keeps the original level to restore.
            task, previous = self._pulses.pop(key)
            task.cancel()
        else:
            previous = await self.read_channel(address, channel)

        result = await self._set_channel(address, channel, level)
        result.previous = previous
        if previous is not None:
            # Restore even if unconfirmed: the device may have switched without answering.
            task = asyncio.ensure_future(self._restore_later(key, previous, seconds))
            self._pulses[key] = (task, previous)
        else:
            result.error = "Could not read the current level, so it will not be restored"
        return result

    async def restore_pending(self):
        """Restore every channel with a running pulse now (e.g. when Home Assistant stops)."""
        pulses, self._pulses = self._pulses, {}
        for (address, channel), (task, previous) in sorted(pulses.items()):
            task.cancel()
            await self._set_channel(address, channel, previous)

    async def _restore_later(self, key, previous, seconds):
        await asyncio.sleep(seconds)
        self._pulses.pop(key, None)
        address, channel = key
        try:
            result = await self._set_channel(address, channel, previous)
        except Exception:
            _LOGGER.exception("Restoring %s channel %d after a pulse failed", _address_text(address), channel)
            return
        if not result.confirmed:
            _LOGGER.warning("Could not confirm restoring %s channel %d to %d", _address_text(address), channel,
                            previous)

    async def _set_channel(self, address, channel, level):
        started = time.monotonic()
        reply = await self._buspro.request(
            address, OperateCode.SingleChannelControl, [channel, level, 0, 0],
            OperateCode.SingleChannelControlResponse, match=lambda t: t.payload[:1] == [channel],
            timeout=self._confirm_timeout)
        result = CommandResult(_address_text(address), OUTPUT, channel, level, confirmed=False)
        if reply is not None and len(reply.payload) >= 3:
            result.latency = time.monotonic() - started
            result.confirmed_by = _code_text(reply)
            if reply.payload[1] == SUCCESS:
                result.value = reply.payload[2]
                result.confirmed = result.value == level
            else:
                result.error = "The device reported a failure"
        else:
            # Some devices do not broadcast an answer; read the channel instead.
            value = await self.read_channel(address, channel)
            if value is not None:
                result.latency = time.monotonic() - started
                result.value = value
                result.confirmed_by = "0x0034"
                result.confirmed = value == level
            else:
                result.error = "No answer from the device"
        self._log(result)
        return result

    # Curtains and universal switches

    async def set_curtain(self, address, curtain, status):
        """CurtainSwitchControl with status CURTAIN_STOP, CURTAIN_OPEN or CURTAIN_CLOSE."""
        if status not in (CURTAIN_STOP, CURTAIN_OPEN, CURTAIN_CLOSE):
            raise BusControlError(f"unknown curtain status {status}")
        return await self._command_with_answer(
            tuple(address), CURTAIN, curtain, status, OperateCode.CurtainSwitchControl, [curtain, status],
            OperateCode.CurtainSwitchControlResponse, OperateCode.CurtainSwitchStatus, [curtain],
            OperateCode.CurtainSwitchStatusResponse, lambda payload: payload[1])

    async def set_universal_switch(self, address, switch, on):
        return await self._command_with_answer(
            tuple(address), UNIVERSAL_SWITCH, switch, 1 if on else 0, OperateCode.UniversalSwitchControl,
            [switch, 255 if on else 0], OperateCode.UniversalSwitchControlResponse,
            OperateCode.ReadStatusOfUniversalSwitch, [switch], OperateCode.ReadStatusOfUniversalSwitchResponse,
            lambda payload: 1 if payload[1] == 1 else 0)

    async def _command_with_answer(self, address, kind, number, requested, code, payload, answer_code,
                                   read_code, read_payload, read_answer_code, value_of):
        self._check_rate((address, kind, number))
        started = time.monotonic()
        result = CommandResult(_address_text(address), kind, number, requested, confirmed=False)

        def same_number(telegram):
            return len(telegram.payload) >= 2 and telegram.payload[0] == number

        reply = await self._buspro.request(address, code, payload, answer_code, match=same_number,
                                           timeout=self._confirm_timeout)
        if reply is None:
            reply = await self._buspro.request(address, read_code, read_payload, read_answer_code,
                                               match=same_number, timeout=self._confirm_timeout)
        if reply is None:
            result.error = "No answer from the device"
        else:
            result.latency = time.monotonic() - started
            result.confirmed_by = _code_text(reply)
            result.value = value_of(reply.payload)
            result.confirmed = result.value == requested
        self._log(result)
        return result

    # Floor heating module zones

    async def read_heating_zone(self, address, zone):
        """ZoneStatus of one zone, or None if the module does not answer."""
        reply = await self._buspro.request(
            tuple(address), OperateCode.ReadFloorHeatingModuleStatus, [zone],
            OperateCode.ReadFloorHeatingModuleStatusResponse, match=lambda t: t.payload[:1] == [zone],
            timeout=self._confirm_timeout)
        return None if reply is None else parse_zone_status(reply.payload)

    async def set_heating_zone(self, address, zone, on=None, temperature=None):
        """Switch a zone on or off, or change the setpoint it uses now (°C).

        The module also broadcasts 0x1C5D when the room temperature changes, so only an answer
        with the requested value confirms; otherwise the zone is read again to report its value.
        """
        address = tuple(address)
        self._check_rate((address, HEATING_ZONE, zone))
        requested = (1 if on else 0) if temperature is None else int(round(temperature))

        def value_of(status):
            return (1 if status.on else 0) if temperature is None else status.setpoints[status.active_setpoint]

        result = CommandResult(_address_text(address), HEATING_ZONE, zone, requested, confirmed=False)
        started = time.monotonic()
        status = await self.read_heating_zone(address, zone)
        if status is None:
            result.error = "No answer from the device"
            self._log(result)
            return result

        setpoints = {} if temperature is None else {status.active_setpoint: requested}
        payload = build_zone_control(status, on=on, setpoints=setpoints)

        def confirms(telegram):
            answer = parse_zone_status(telegram.payload)
            return answer is not None and answer.zone == zone and value_of(answer) == requested

        reply = await self._buspro.request(address, OperateCode.ControlFloorHeatingModuleStatus, payload,
                                           OperateCode.ControlFloorHeatingModuleStatusResponse, match=confirms,
                                           timeout=self._confirm_timeout)
        answer = parse_zone_status(reply.payload) if reply is not None else await self.read_heating_zone(address, zone)
        if answer is None:
            result.error = "No answer from the device"
        else:
            result.latency = time.monotonic() - started
            result.confirmed_by = _code_text(reply) if reply is not None else "0x1C5F"
            result.value = value_of(answer)
            result.confirmed = result.value == requested
        self._log(result)
        return result

    # Helpers

    def _check_rate(self, key):
        now = time.monotonic()
        last = self._last_command.get(key)
        if last is not None and now - last < self._min_command_interval:
            raise BusControlError("Too many commands for this channel; wait a moment")
        self._last_command[key] = now

    @staticmethod
    def _log(result):
        if result.confirmed:
            _LOGGER.info("Test %s %s %d -> %d confirmed by %s in %.2f s", result.address, result.kind, result.number,
                         result.requested, result.confirmed_by, result.latency)
        else:
            _LOGGER.warning("Test %s %s %d -> %d not confirmed: value %s, %s", result.address, result.kind,
                            result.number, result.requested, result.value, result.error)
