"""Floor heating module (type 0x00CF, HDL-MFH06.432): heating zones and 1-wire floor sensors.

Read layouts are confirmed by a capture of HDL Buspro Setup Tool 2 reading a 6-zone module
(docs/protocol-captures/2026-10-25-analysis.md):

- 0x1C5E [zone] -> 0x1C5F, and 0x1C5D which the module broadcasts whenever the room temperature
  or the valve changes: [zone, work (type << 4 | on), temperature type, mode, normal, day, night,
  away, timer (0 day, 1 night), room temperature (0x80 = no sensor), valve, ...] (14 bytes).
  caligo-mentis/smart-bus documents an older 13-byte layout without the room temperature.
- 0x1D02 [zone] -> 0x1D03 [zone, name (20 bytes, UTF-16BE)].
- 0x1D12 -> 0x1D13 [?, sensor count, ...]; 0x1D16 [sensor] -> 0x1D17 [sensor, 1-wire ROM (8),
  ?, ?, name (20 bytes, ANSI like other remarks), zone, temperature].

Control (0x1C5C) uses the 10-byte layout of the HDL operation code list as given by smart-bus,
[zone, work, temperature type, mode, normal, day, night, away, valve, watering time]; it has not
been seen in a capture yet, so its effect is confirmed by the 0x1C5D answer.
"""

from dataclasses import dataclass, field

from .device import Device
from ..helpers.enums import OperateCode, TemperatureMode

ZONE_STATUS_CODES = (0x1C5F, 0x1C5D)
FLOOR_SENSOR_CODE = 0x1D17
NO_TEMPERATURE = 0x80
NAME_LENGTH = 20
MAX_FLOOR_SENSORS = 13
SETPOINT_NAMES = ("normal", "day", "night", "away")


def _temperature(value):
    """Whole degrees with the sign in bit 7, like 0xE3E5; 0x80 means no sensor."""
    if value == NO_TEMPERATURE:
        return None
    return -(value & 0x7F) if value & 0x80 else value


@dataclass
class ZoneStatus:
    zone: int
    on: bool
    work_type: int  # high nibble of the work byte; 0 in the captures (heating)
    temperature_type: int  # 0 Celsius, 1 Fahrenheit
    mode: int  # TemperatureMode value
    setpoints: dict  # normal, day, night, away
    timer: int  # 0 day, 1 night: which setpoint the timer mode uses now
    room_temperature: int = None
    valve: bool = None
    raw: list = field(default_factory=list, repr=False)

    @property
    def active_setpoint(self):
        """Name of the setpoint the zone heats to now."""
        if self.mode == TemperatureMode.Timer.value:
            return "night" if self.timer == 1 else "day"
        return {TemperatureMode.Day.value: "day", TemperatureMode.Night.value: "night",
                TemperatureMode.Away.value: "away"}.get(self.mode, "normal")

    def as_dict(self):
        return {"on": self.on, "mode": self.mode, "timer": self.timer, "temperature": self.room_temperature,
                "valve": self.valve, **self.setpoints, "target": self.setpoints.get(self.active_setpoint)}


def parse_zone_status(payload):
    """Decode 0x1C5F/0x1C5D; None if too short."""
    p = list(payload)
    if len(p) < 13:
        return None
    if len(p) >= 14:  # current firmware: room temperature at 9, valve at 10
        room, valve = _temperature(p[9]), bool(p[10])
    else:  # layout in the operation code list: valve at 9
        room, valve = None, bool(p[9])
    return ZoneStatus(zone=p[0], on=bool(p[1] & 0x0F), work_type=p[1] >> 4, temperature_type=p[2], mode=p[3],
                      setpoints=dict(zip(SETPOINT_NAMES, p[4:8])), timer=p[8], room_temperature=room, valve=valve,
                      raw=p)


def build_zone_control(status, on=None, mode=None, setpoints=None):
    """0x1C5C payload that changes on/off, mode or setpoints and keeps everything else as reported."""
    setpoints = {**status.setpoints, **(setpoints or {})}
    on = status.on if on is None else on
    raw = status.raw
    valve = raw[10] if len(raw) >= 14 else raw[9]
    watering_time = raw[13] if len(raw) >= 14 else raw[12]
    return [status.zone, status.work_type << 4 | (1 if on else 0), status.temperature_type,
            status.mode if mode is None else mode, *(int(setpoints[name]) for name in SETPOINT_NAMES),
            valve, watering_time]


def parse_zone_name(payload):
    """Decode 0x1D03 [zone, name as 20 bytes of UTF-16BE] -> (zone, name or None)."""
    p = bytes(b & 0xFF for b in payload)
    if not p:
        return None
    text = p[1:1 + NAME_LENGTH].decode("utf-16-be", errors="ignore").split("\x00", 1)[0]
    text = "".join(ch for ch in text if ch.isprintable() and ch != "￿").strip()
    return p[0], text or None


def parse_floor_sensor_count(payload):
    """Decode 0x1D13; the second byte is the number of sensors Setup Tool then reads."""
    if len(payload) >= 2 and 0 <= payload[1] <= MAX_FLOOR_SENSORS:
        return payload[1]
    return None


@dataclass
class FloorSensorInfo:
    number: int
    name: str
    zone: int  # zone the sensor belongs to, None if none
    temperature: int
    rom: str  # 1-wire ROM code, e.g. 28-...


def parse_floor_sensor(payload):
    """Decode 0x1D17; None if too short or the sensor slot is empty."""
    from ..scanner.remarks import decode_remark  # not at the top: the scanner package imports devices

    p = list(payload)
    if len(p) < 33:
        return None
    rom = p[1:9]
    if all(b == 0xFF for b in rom) or all(b == 0 for b in rom):
        return None
    zone = p[31] if 1 <= p[31] <= 64 else None
    return FloorSensorInfo(number=p[0], name=decode_remark(p[11:11 + NAME_LENGTH]), zone=zone,
                           temperature=_temperature(p[32]), rom="-".join(f"{b:02X}" for b in rom))


class FloorHeatingZone(Device):
    """One zone of a floor heating module, with the same interface as FloorHeating (DLP panels)."""

    def __init__(self, buspro, device_address, zone, name=""):
        super().__init__(buspro, device_address, name)
        self.zone = zone
        self.status = None  # ZoneStatus
        self.register_telegram_received_cb(self._telegram_received_cb)

    def _telegram_received_cb(self, telegram):
        if int.from_bytes(telegram.operate_code_raw, "big") in ZONE_STATUS_CODES:
            status = parse_zone_status(telegram.payload)
            if status is not None and status.zone == self.zone:
                self.status = status
                self._call_device_updated()

    @property
    def known(self):
        return self.status is not None

    @property
    def is_on(self):
        return self.known and self.status.on

    @property
    def mode(self):
        return self.status.mode if self.known else None

    @property
    def current_temperature(self):
        return self.status.room_temperature if self.known else None

    @property
    def target_temperature(self):
        return self.status.setpoints.get(self.status.active_setpoint) if self.known else None

    @property
    def heating(self):
        """True while the valve is open, None if unknown."""
        return self.status.valve if self.known else None

    async def read_status(self):
        await self._send_telegram(self._buspro.build_telegram(
            self._device_address, OperateCode.ReadFloorHeatingModuleStatus, [self.zone]))

    async def set(self, on=None, mode=None, temperature=None):
        """Change on/off, mode or the setpoint used now; needs a known state first."""
        if not self.known:
            raise ValueError("The floor heating zone state has not been read yet")
        status = self.status
        setpoints = {}
        if temperature is not None:
            target_mode = status.mode if mode is None else mode
            preview = ZoneStatus(**{**status.__dict__, "mode": target_mode})
            setpoints[preview.active_setpoint] = int(round(temperature))
        payload = build_zone_control(status, on=on, mode=mode, setpoints=setpoints)
        await self._send_telegram(self._buspro.build_telegram(
            self._device_address, OperateCode.ControlFloorHeatingModuleStatus, payload))
        # Assume it applies, so a second command sent before the answer builds on this one;
        # the module's 0x1C5D answer then confirms or corrects it.
        self.status = ZoneStatus(**{**status.__dict__, "on": bool(payload[1] & 0x0F), "mode": payload[3],
                                    "setpoints": dict(zip(SETPOINT_NAMES, payload[4:8]))})
        self._call_device_updated()

    @property
    def device_identifier(self):
        return f"{self._device_address}-heating_zone-{self.zone}"


class FloorSensor(Device):
    """A 1-wire floor temperature sensor connected to a floor heating module."""

    def __init__(self, buspro, device_address, number, name=""):
        super().__init__(buspro, device_address, name)
        self.number = number
        self.info = None  # FloorSensorInfo
        self.register_telegram_received_cb(self._telegram_received_cb)

    def _telegram_received_cb(self, telegram):
        if int.from_bytes(telegram.operate_code_raw, "big") == FLOOR_SENSOR_CODE:
            info = parse_floor_sensor(telegram.payload)
            if info is not None and info.number == self.number:
                self.info = info
                self._call_device_updated()

    @property
    def temperature(self):
        return self.info.temperature if self.info else None

    async def read_status(self):
        await self._send_telegram(self._buspro.build_telegram(
            self._device_address, OperateCode.ReadFloorSensor, [self.number]))

    @property
    def device_identifier(self):
        return f"{self._device_address}-floor_sensor-{self.number}"
