"""What a bus scan found: devices, their category and their channels."""

from collections import Counter
from dataclasses import asdict, dataclass, field

from .module_reply import BIG_CURTAIN, BIG_FLOOR_HEATING, BIG_OUTPUT, BIG_PANEL, BIG_SENSOR
from .type_codes import (
    CURTAIN_MODULE, DRY_CONTACT_MODULE, FLOOR_HEATING, KNOWN_TYPES, LOGIC, LOGIC_OPERATE_CODES,
    OUTPUT_MODULE, PANEL, PANEL_OPERATE_CODES, SENSOR, SENSOR_OPERATE_CODES, SOFTWARE, SOFTWARE_TYPES,
    UNKNOWN,
)


@dataclass
class ScannedChannel:
    number: int
    kind: str  # relay, dimmer, dmx, curtain, dry_contact, floor_heating, motion, illuminance, ...
    name: str = None
    level: int = None

    def to_dict(self):
        return asdict(self)


@dataclass
class ScannedDevice:
    subnet_id: int
    device_id: int
    type_codes: Counter = field(default_factory=Counter)
    remark: str = None
    mac: str = None
    functions: list = None  # ModuleFunction list from 0xE549; None if the device never answered
    channel_count: int = None  # from ReadStatusOfChannelsResponse
    levels: dict = field(default_factory=dict)  # channel -> 0..100
    channel_names: dict = field(default_factory=dict)  # channel -> name, None if unnamed
    operate_codes: set = field(default_factory=set)  # every code heard from the device

    @property
    def address(self):
        return f"{self.subnet_id}.{self.device_id}"

    @property
    def type_code(self):
        """Most used type code, preferring real device types over software ones."""
        for code, _count in self.type_codes.most_common():
            if code not in SOFTWARE_TYPES:
                return code
        return next(iter(self.type_codes.most_common(1)), (None,))[0]

    @property
    def category(self):
        if self.type_codes and all(code in SOFTWARE_TYPES for code in self.type_codes):
            return SOFTWARE
        if self.functions:
            category = self._category_from_functions()
            if category != UNKNOWN:
                return category
        if self.channel_count:
            return OUTPUT_MODULE
        known = KNOWN_TYPES.get(self.type_code)
        if known is not None:
            return known[0]
        if self.operate_codes & SENSOR_OPERATE_CODES:
            return SENSOR
        if self.operate_codes & PANEL_OPERATE_CODES:
            return PANEL
        if self.operate_codes & LOGIC_OPERATE_CODES:
            return LOGIC
        return UNKNOWN

    def _category_from_functions(self):
        bigs = {f.big for f in self.functions}
        # Panels list what they control (lights, curtains, AC...), not outputs of their own.
        if any(f.big == BIG_PANEL and f.small != 0 for f in self.functions):
            return PANEL
        if BIG_OUTPUT in bigs:
            return OUTPUT_MODULE
        if BIG_CURTAIN in bigs:
            return CURTAIN_MODULE
        if BIG_FLOOR_HEATING in bigs:
            return FLOOR_HEATING
        if BIG_PANEL in bigs:
            return DRY_CONTACT_MODULE
        if BIG_SENSOR in bigs:
            return SENSOR
        return UNKNOWN

    def _functions(self, big):
        return [f for f in self.functions or () if f.big == big]

    @property
    def curtain_count(self):
        return sum(f.count for f in self._functions(BIG_CURTAIN))

    def channel_numbers_with_names(self):
        """Channel numbers whose remark (0xF00E) is worth reading."""
        category = self.category
        if category == OUTPUT_MODULE:
            return list(range(1, self._output_count() + 1))
        if category == CURTAIN_MODULE:
            # Each curtain uses two relay channels (up, down), both named after the curtain.
            return list(range(1, 2 * self.curtain_count + 1))
        return []

    def _output_count(self):
        return self.channel_count or sum(f.count for f in self._functions(BIG_OUTPUT))

    def _output_kinds(self):
        count = self._output_count()
        kinds = [f.category for f in self._functions(BIG_OUTPUT) for _ in range(f.count)][:count]
        for number in range(len(kinds) + 1, count + 1):
            level = self.levels.get(number)
            kinds.append("dimmer" if level is not None and level not in (0, 100) else "relay")
        return kinds

    @property
    def channels(self):
        category = self.category
        if category == OUTPUT_MODULE:
            return [ScannedChannel(number, kind, self.channel_names.get(number), self.levels.get(number))
                    for number, kind in enumerate(self._output_kinds(), start=1)]
        if category == CURTAIN_MODULE:
            return [ScannedChannel(number, "curtain",
                                   self.channel_names.get(2 * number - 1) or self.channel_names.get(2 * number))
                    for number in range(1, self.curtain_count + 1)]
        if category == FLOOR_HEATING:
            return [ScannedChannel(number, "floor_heating")
                    for number in range(1, sum(f.count for f in self._functions(BIG_FLOOR_HEATING)) + 1)]
        if category == DRY_CONTACT_MODULE:
            zones = sum(f.count for f in self._functions(BIG_PANEL) if f.small == 0)
            return [ScannedChannel(number, "dry_contact") for number in range(1, zones + 1)]
        if category == SENSOR:
            # Numbered per kind: motion 1, illuminance 1, dry_contact 1, dry_contact 2, ...
            return [ScannedChannel(number, f.category)
                    for f in self._functions(BIG_SENSOR) for number in range(1, f.count + 1)]
        return []

    def to_dict(self):
        type_code = self.type_code
        known = KNOWN_TYPES.get(type_code)
        return {
            "address": self.address,
            "type_code": None if type_code is None else f"0x{type_code:04X}",
            "type_description": known[1] if known else None,
            "category": self.category,
            "remark": self.remark,
            "mac": self.mac,
            "functions": None if self.functions is None else [[f.big, f.small, f.count] for f in self.functions],
            "channels": [channel.to_dict() for channel in self.channels],
            "operate_codes": sorted(f"0x{code:04X}" for code in self.operate_codes),
        }


@dataclass
class ScanResult:
    devices: list
    duration: float
    ignored_sources: int = 0  # software sources such as Setup Tool PCs

    def to_dict(self):
        return {
            "duration": round(self.duration, 1),
            "ignored_sources": self.ignored_sources,
            "devices": [device.to_dict() for device in self.devices],
        }
