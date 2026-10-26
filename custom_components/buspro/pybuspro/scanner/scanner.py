"""Find HDL Buspro devices, their channels and the names stored in them.

The scan is read-only: it never sends control telegrams. It works like HDL Buspro
Setup Tool 2 (docs/protocol-captures/2026-10-25-analysis.md):

1. Discovery: broadcast ReadDeviceRemark (0x000E) and ReadDeviceModule (0xE548) for
   several rounds, since one round reaches only ~87% of devices. Everything heard on
   the bus meanwhile is recorded too, so devices that ignore both are still found.
2. Identify: ask devices still missing a name or self-description directly.
   Floor heating modules are asked for their 1-wire floor sensors (0x1D12, 0x1D16), and
   curtain modules for each curtain's position (0xE3E2 [curtain + 16]), which only curtains
   that go to a percentage themselves answer.
3. Channels: ReadStatusOfChannels (0x0033) sent to each possible output module; many
   modules ignore it as a broadcast.
4. MAC: ReadMacAddress (0xF003), a stable id that survives address changes.
5. Names: ReadChannelRemark (0xF00E) for every output and curtain channel, and the zone
   names of floor heating modules (0x1D02).
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass

from ..buspro import BROADCAST_ADDRESS
from ..devices.floor_heating_module import parse_floor_sensor, parse_floor_sensor_count, parse_zone_name
from ..devices.position_cover import POSITION_OFFSET, parse_curtain_position
from ..helpers.enums import OperateCode
from .models import ScannedDevice, ScanResult
from .module_reply import MAX_EXCLUDED_DEVICES, build_module_read_payload, parse_module_reply
from .remarks import parse_channel_remark, parse_device_remark
from .type_codes import (CURTAIN_MODULE, FLOOR_HEATING, GATEWAY, LOGIC, NO_MODULE_REPLY_TYPES, OUTPUT_MODULE,
                         SENSOR, SOFTWARE, UNKNOWN)

# How to ask a sensor for its readings; others are asked with ReadSensorStatus (0x1645).
_SENSOR_READS = {
    0x014A: (OperateCode.ReadSensorsInOneStatus, OperateCode.ReadSensorsInOneStatusResponse),
    0x0018: (OperateCode.ReadMotionSensorStatus, OperateCode.ReadMotionSensorStatusResponse),
}

_LOGGER = logging.getLogger(__name__)

DEFAULT_OWN_ADDRESS = (200, 200)  # source address pybuspro sends from
MAX_CHANNELS = 64

_READ_MAC = 0xF003
_READ_MAC_RESPONSE = 0xF004


@dataclass
class ScanOptions:
    search_rounds: int = 4
    search_interval: float = 10.0  # seconds per discovery round
    settle_time: float = 5.0  # wait for late replies after the last round
    request_timeout: float = 1.0
    request_retries: int = 1
    read_mac: bool = True
    read_channel_names: bool = True


@dataclass
class ScanProgress:
    phase: str  # discovery, identify, channels, mac, names, done
    devices: int
    done: int = 0
    total: int = 0


class BusScanner:
    def __init__(self, buspro, own_address=DEFAULT_OWN_ADDRESS):
        self._buspro = buspro
        self._own_address = tuple(own_address)
        self._devices = {}
        self._running = False
        self._session = None
        self._on_progress = None
        self.type_overrides = {}  # type code -> override set by the user, see ScannedDevice.override

    @property
    def running(self):
        return self._running

    async def scan(self, options=None, on_progress=None):
        """Scan the bus. Raises RuntimeError if a scan is already running."""
        if self._running:
            raise RuntimeError("A bus scan is already running")
        options = options or ScanOptions()
        self._running = True
        self._devices = {}
        self._session = (random.randint(1, 255), random.randint(1, 255))
        self._on_progress = on_progress
        started = time.monotonic()
        remove_listener = self._buspro.add_telegram_listener(self._on_telegram)
        try:
            await self._discover(options)
            await self._identify(options)
            await self._read_channel_status(options)
            if options.read_mac:
                await self._read_macs(options)
            if options.read_channel_names:
                await self._read_channel_names(options)
        finally:
            remove_listener()
            self._running = False

        devices = sorted(self._devices.values(), key=lambda d: (d.subnet_id, d.device_id))
        result = ScanResult(
            devices=[d for d in devices if d.category != SOFTWARE],
            duration=time.monotonic() - started,
            ignored_sources=sum(1 for d in devices if d.category == SOFTWARE),
        )
        self._report("done", len(result.devices))
        return result

    # Passive collection

    def _on_telegram(self, telegram):
        source = tuple(telegram.source_address)
        if source in (self._own_address, BROADCAST_ADDRESS):
            return

        device = self._devices.get(source)
        if device is None:
            device = self._devices[source] = ScannedDevice(*source)
        device.type_codes[int.from_bytes(telegram.source_device_type_raw, "big")] += 1
        device.override = self.type_overrides.get(device.type_code)
        code = int.from_bytes(telegram.operate_code_raw, "big")
        device.operate_codes.add(code)
        payload = telegram.payload

        if code == 0x000F:
            device.remark = parse_device_remark(payload) or device.remark
        elif code == 0xE549:
            reply = parse_module_reply(payload)
            if reply is not None:
                device.functions = reply.functions
                device.remark = device.remark or reply.remark
        elif code == 0x0034 and payload and 0 < payload[0] <= MAX_CHANNELS:
            device.channel_count = payload[0]
            device.levels.update(enumerate(payload[1:1 + payload[0]], start=1))
        elif code == 0x0032 and len(payload) >= 3 and payload[1] == 0xF8:
            device.levels[payload[0]] = payload[2]
        elif code == 0xF00F:
            parsed = parse_channel_remark(payload)
            if parsed is not None:
                device.channel_names[parsed[0]] = parsed[1]
        elif code == _READ_MAC_RESPONSE and len(payload) >= 8:
            device.mac = ":".join(f"{b:02X}" for b in payload[:8])
        elif code in (0xE3E1, 0xE3E3):
            position = parse_curtain_position(payload)
            if position is not None:
                device.curtain_positions[position[0]] = position[1]
        elif code == 0x1D03:
            parsed = parse_zone_name(payload)
            if parsed is not None:
                device.zone_names[parsed[0]] = parsed[1]
        elif code == 0x1D13:
            device.floor_sensor_count = parse_floor_sensor_count(payload)
        elif code == 0x1D17:
            sensor = parse_floor_sensor(payload)
            if sensor is not None:
                device.floor_sensors[sensor.number] = sensor

    # Phases

    async def _discover(self, options):
        offset = 0
        half = options.search_interval / 2
        for round_number in range(1, options.search_rounds + 1):
            self._report("discovery", len(self._devices), round_number, options.search_rounds)
            await self._broadcast(OperateCode.ReadDeviceRemark)
            await asyncio.sleep(half)

            described = sorted(a for a, d in self._devices.items() if d.functions is not None)
            if offset >= len(described):
                offset = 0
            exclude = described[offset:offset + MAX_EXCLUDED_DEVICES]
            offset += len(exclude)
            await self._broadcast(OperateCode.ReadDeviceModule, build_module_read_payload(self._session, exclude))
            await asyncio.sleep(half)
        await asyncio.sleep(options.settle_time)

    async def _read_channel_status(self, options):
        targets = [d for d in self._targets() if d.channel_count is None and d.category in (OUTPUT_MODULE, UNKNOWN)]
        for done, device in enumerate(targets):
            self._report("channels", len(self._devices), done, len(targets))
            await self._request(options, device, OperateCode.ReadStatusOfChannels, (),
                                OperateCode.ReadStatusOfChannelsResponse)

    async def _identify(self, options):
        targets = [d for d in self._targets() if d.remark is None or d.functions is None or d.may_have_floor_heating
                   or (d.category == SENSOR and not d.features()) or d.category in (FLOOR_HEATING, CURTAIN_MODULE)]
        for done, device in enumerate(targets):
            self._report("identify", len(self._devices), done, len(targets))
            if device.functions is None and device.type_code not in NO_MODULE_REPLY_TYPES:
                await self._request(options, device, OperateCode.ReadDeviceModule,
                                    build_module_read_payload(self._session), OperateCode.ReadDeviceModuleResponse)
            if device.remark is None:
                await self._request(options, device, OperateCode.ReadDeviceRemark, (),
                                    OperateCode.ReadDeviceRemarkResponse)
            if device.category == SENSOR and not device.features():
                # Sensors broadcast their readings only now and then; ask for them.
                read, answer = _SENSOR_READS.get(device.type_code, (OperateCode.ReadSensorStatus,
                                                                    OperateCode.ReadSensorStatusResponse))
                await self._request(options, device, read, (), answer, retries=0)
            if device.may_have_floor_heating and not device.operate_codes & {0x1945, 0x1947}:
                await self._request(options, device, OperateCode.ReadFloorHeatingStatus, (),
                                    OperateCode.ReadFloorHeatingStatusResponse, retries=0)
            if device.category == FLOOR_HEATING:
                await self._read_floor_sensors(options, device)
            if device.category == CURTAIN_MODULE:
                await self._read_curtain_positions(options, device)

    async def _read_curtain_positions(self, options, device):
        for curtain in range(1, device.curtain_count + 1):
            if curtain not in device.curtain_positions:
                number = curtain + POSITION_OFFSET
                await self._request(options, device, OperateCode.CurtainSwitchStatus, [number],
                                    OperateCode.CurtainSwitchStatusResponse,
                                    match=lambda telegram, number=number: telegram.payload[:1] == [number], retries=0)

    async def _read_floor_sensors(self, options, device):
        if device.floor_sensor_count is None:
            await self._request(options, device, OperateCode.ReadFloorSensorCount, (),
                                OperateCode.ReadFloorSensorCountResponse)
        for number in range(1, (device.floor_sensor_count or 0) + 1):
            if number not in device.floor_sensors:
                await self._request(options, device, OperateCode.ReadFloorSensor, [number],
                                    OperateCode.ReadFloorSensorResponse,
                                    match=lambda telegram, number=number: telegram.payload[:1] == [number])

    async def _read_macs(self, options):
        targets = [d for d in self._targets() if d.mac is None]
        for done, device in enumerate(targets):
            self._report("mac", len(self._devices), done, len(targets))
            # Nice to have, so no retries: silent devices would double the time spent here.
            await self._request(options, device, _READ_MAC, (), _READ_MAC_RESPONSE, retries=0)

    async def _read_channel_names(self, options):
        channel = (OperateCode.ReadChannelRemark, OperateCode.ReadChannelRemarkResponse)
        zone = (OperateCode.ReadFloorHeatingZoneRemark, OperateCode.ReadFloorHeatingZoneRemarkResponse)
        work = [(d, n, channel) for d in self._targets() for n in d.channel_numbers_with_names()
                if n not in d.channel_names]
        work += [(d, n, zone) for d in self._targets() for n in d.zone_numbers() if n not in d.zone_names]
        for done, (device, number, (read, answer)) in enumerate(work):
            self._report("names", len(self._devices), done, len(work))
            await self._request(options, device, read, [number], answer,
                                match=lambda telegram, number=number: telegram.payload[:1] == [number])

    # Helpers

    def _targets(self):
        """Devices worth asking directly, in address order."""
        devices = sorted(self._devices.values(), key=lambda d: (d.subnet_id, d.device_id))
        return [d for d in devices if d.category not in (SOFTWARE, GATEWAY, LOGIC)]

    async def _broadcast(self, operate_code, payload=()):
        await self._buspro.network_interface.send_telegram(
            self._buspro.build_telegram(BROADCAST_ADDRESS, operate_code, payload))

    async def _request(self, options, device, operate_code, payload, response_operate_code, match=None,
                       retries=None):
        return await self._buspro.request(
            (device.subnet_id, device.device_id), operate_code, payload, response_operate_code, match,
            timeout=options.request_timeout, retries=options.request_retries if retries is None else retries)

    def _report(self, phase, devices, done=0, total=0):
        if self._on_progress is None:
            return
        try:
            self._on_progress(ScanProgress(phase, devices, done, total))
        except Exception:
            _LOGGER.exception("Scan progress callback failed")
