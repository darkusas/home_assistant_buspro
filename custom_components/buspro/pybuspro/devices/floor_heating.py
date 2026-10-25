"""Floor heating controlled by a DLP panel (0x1944 read, 0x1946 control).

Read layouts are confirmed by captures (docs/protocol-captures/2026-10-25-analysis.md):
0x1945 [type, current temperature, status, mode, normal, day, night, away, ...] from panels
that are asked, and 0x1947 [0xF8, type, status, mode, normal, day, night, away], which DLP
panels also broadcast on their own. Control (0x1946, same layout as 0x1947 without the
success byte) follows the official operation code list and has not been seen in a capture.
"""

from .control import _ControlFloorHeatingStatus, _ReadFloorHeatingStatus
from .device import Device
from ..helpers.enums import OperateCode, TemperatureMode

MODE_SETPOINT = {
    TemperatureMode.Normal.value: "normal",
    TemperatureMode.Day.value: "day",
    TemperatureMode.Night.value: "night",
    TemperatureMode.Away.value: "away",
    TemperatureMode.Timer.value: "normal",  # the timer switches between day and night itself
}


class FloorHeating(Device):
    def __init__(self, buspro, device_address, name=""):
        super().__init__(buspro, device_address, name)
        self.temperature_type = 0  # 0 Celsius, 1 Fahrenheit
        self.status = None  # 0 off, 1 on
        self.mode = None  # TemperatureMode value
        self.current_temperature = None
        self.setpoints = {}  # normal, day, night, away
        self.register_telegram_received_cb(self._telegram_received_cb)

    def _telegram_received_cb(self, telegram):
        payload = telegram.payload
        if telegram.operate_code == OperateCode.ReadFloorHeatingStatusResponse and len(payload) >= 8:
            self.current_temperature = payload[1]
            self._update(payload[0], payload[2], payload[3], payload[4:8])
        elif telegram.operate_code == OperateCode.ControlFloorHeatingStatusResponse and len(payload) >= 8:
            if payload[0] == 0xF8:
                self._update(payload[1], payload[2], payload[3], payload[4:8])

    def _update(self, temperature_type, status, mode, setpoints):
        self.temperature_type = temperature_type
        self.status = status
        self.mode = mode
        self.setpoints = dict(zip(("normal", "day", "night", "away"), setpoints))
        self._call_device_updated()

    @property
    def known(self):
        return self.status is not None and len(self.setpoints) == 4

    @property
    def is_on(self):
        return self.status == 1

    @property
    def target_temperature(self):
        return self.setpoints.get(MODE_SETPOINT.get(self.mode, "normal"))

    async def read_status(self):
        read = _ReadFloorHeatingStatus(self._buspro)
        read.subnet_id, read.device_id = self._device_address
        await read.send()

    async def set(self, on=None, mode=None, temperature=None):
        """Change status, mode or the setpoint of the current mode; needs a known state first."""
        if not self.known:
            raise ValueError("The floor heating state has not been read yet")
        setpoints = dict(self.setpoints)
        mode = self.mode if mode is None else mode
        if temperature is not None:
            setpoints[MODE_SETPOINT.get(mode, "normal")] = int(round(temperature))

        status = (1 if on else 0) if on is not None else self.status
        control = _ControlFloorHeatingStatus(self._buspro)
        control.subnet_id, control.device_id = self._device_address
        control.temperature_type = self.temperature_type
        control.status = status
        control.mode = mode
        control.normal_temperature = setpoints["normal"]
        control.day_temperature = setpoints["day"]
        control.night_temperature = setpoints["night"]
        control.away_temperature = setpoints["away"]
        await control.send()
        # Assume it applies, so a second command sent before the answer builds on this one;
        # the panel's 0x1947 answer then confirms or corrects it.
        self._update(self.temperature_type, status, mode, [setpoints[k] for k in ("normal", "day", "night", "away")])

    @property
    def device_identifier(self):
        return f"{self._device_address}-floor_heating"
