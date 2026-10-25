"""Live state of channels, curtains, universal switches and sensors, decoded from bus traffic.

Used to show current values while testing devices, before any Home Assistant entity
exists. Layouts are from the official 2013 operation code list, caligo-mentis/smart-bus
and the captures in docs/protocol-captures/; the 0x0032 tail is a channel bitmask.
"""

import logging
import struct
from dataclasses import dataclass

_LOGGER = logging.getLogger(__name__)

CHANNEL = "channel"  # value: level 0..100
CHANNELS_ON = "channels_on"  # value: list of bools, channel 1 first (from the 0x0032 bitmask)
CURTAIN = "curtain"  # value: 0 stop, 1 open, 2 close
UNIVERSAL_SWITCH = "universal_switch"  # value: bool
SENSOR = "sensor"  # value: dict of readings
FLOOR_HEATING = "floor_heating"  # value: dict with status, mode, setpoints (and current temperature)
TEMPERATURE_CHANNEL = "temperature_channel"  # value: °C of one channel of a temperature module


@dataclass(frozen=True)
class StateUpdate:
    address: tuple
    kind: str
    number: int  # channel/curtain/switch number; None for whole-device updates
    value: object
    operate_code: int


def _u16(high, low):
    return (high << 8) + low


def _signed_temperature(value):
    """0xE3E5/0xE3E8: bit 7 is the sign, bits 0-6 the magnitude."""
    return -(value & 0x7F) if value & 0x80 else value


def decode_state(telegram):
    """Return the StateUpdates carried by a telegram (empty for anything else)."""
    code = int.from_bytes(telegram.operate_code_raw, "big")
    address = tuple(telegram.source_address)
    p = telegram.payload
    updates = []

    def add(kind, number, value):
        updates.append(StateUpdate(address, kind, number, value, code))

    if code == 0x0032 and len(p) >= 3:
        if p[1] == 0xF8:
            add(CHANNEL, p[0], p[2])
        if len(p) >= 5 and 0 < p[3] <= 64:
            mask = p[4:4 + (p[3] + 7) // 8]
            if len(mask) * 8 >= p[3]:
                add(CHANNELS_ON, None, [bool(mask[i // 8] >> (i % 8) & 1) for i in range(p[3])])
    elif code in (0x0034, 0x0039) and p and 0 < p[0] <= 64:
        for number, level in enumerate(p[1:1 + p[0]], start=1):
            add(CHANNEL, number, level)
    elif code in (0xE01D, 0xE019) and len(p) >= 2:
        add(UNIVERSAL_SWITCH, p[0], p[1] == 1)
    elif code == 0xE017 and p:
        for number, status in enumerate(p[1:1 + p[0]], start=1):
            add(UNIVERSAL_SWITCH, number, status == 1)
    elif code in (0xE3E1, 0xE3E3) and len(p) >= 2:
        add(CURTAIN, p[0], p[1])
    elif code == 0x1646 and len(p) >= 8:
        add(SENSOR, None, {"temperature": p[1] - 20, "illuminance": _u16(p[2], p[3]), "motion": p[4] == 1,
                           "dry_contact_1": p[6] == 1, "dry_contact_2": p[7] == 1})
    elif code == 0x1647 and len(p) >= 7:
        add(SENSOR, None, {"temperature": p[0] - 20, "illuminance": _u16(p[1], p[2]), "motion": p[3] == 1,
                           "dry_contact_1": p[5] == 1, "dry_contact_2": p[6] == 1})
    elif code == 0x1605 and len(p) >= 10:
        add(SENSOR, None, {"temperature": p[1] - 20, "illuminance": _u16(p[2], p[3]), "motion": p[7] == 1,
                           "dry_contact_1": p[8] == 1, "dry_contact_2": p[9] == 1})
    elif code == 0xDB01 and len(p) >= 4:
        add(SENSOR, None, {"motion": p[3] == 1})
    elif code == 0x1945 and len(p) >= 8:
        add(FLOOR_HEATING, None, {"temperature": p[1], "status": p[2], "mode": p[3], "normal": p[4], "day": p[5],
                                  "night": p[6], "away": p[7]})
    elif code == 0x1947 and len(p) >= 8 and p[0] == 0xF8:
        add(FLOOR_HEATING, None, {"status": p[2], "mode": p[3], "normal": p[4], "day": p[5], "night": p[6],
                                  "away": p[7]})
    elif code == 0x1949 and len(p) >= 5:
        add(TEMPERATURE_CHANNEL, p[0], round(struct.unpack("<f", bytes(p[1:5]))[0], 1))
    elif code in (0xE3E5, 0xE3E8) and len(p) >= 2:
        add(SENSOR, None, {"temperature": _signed_temperature(p[1])})
    elif code == 0xE441 and len(p) >= 4:
        add(SENSOR, None, {"illuminance": _u16(p[2], p[3])})
    return updates


class StateMonitor:
    """Decodes state telegrams for subscribers and remembers the latest value of each."""

    def __init__(self, buspro):
        self._buspro = buspro
        self._subscribers = []
        self._remove_listener = None
        self.latest = {}  # (address, kind, number) -> StateUpdate

    def subscribe(self, callback, address=None):
        """Call callback(update) for updates (from one device if address is given). Returns unsubscribe."""
        entry = (callback, None if address is None else tuple(address))
        self._subscribers.append(entry)
        if self._remove_listener is None:
            self._remove_listener = self._buspro.add_telegram_listener(self._on_telegram)

        def unsubscribe():
            if entry in self._subscribers:
                self._subscribers.remove(entry)
            if not self._subscribers and self._remove_listener is not None:
                self._remove_listener()
                self._remove_listener = None

        return unsubscribe

    def snapshot(self, address):
        address = tuple(address)
        return [u for key, u in self.latest.items() if key[0] == address]

    def _on_telegram(self, telegram):
        for update in decode_state(telegram):
            self.latest[(update.address, update.kind, update.number)] = update
            for callback, address in list(self._subscribers):
                if address is None or address == update.address:
                    try:
                        callback(update)
                    except Exception:
                        _LOGGER.exception("State subscriber failed")
