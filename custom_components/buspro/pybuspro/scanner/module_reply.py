"""ReadDeviceModule (0xE548) request and its reply (0xE549): a device describing itself.

HDL Buspro Setup Tool 2 broadcasts 0xE548 to find devices. Every device not in the
request's exclude list answers 0xE549 with its remark and a list of function
triples (big, small, count), e.g. (1, 1, 8) = 8 relay channels.

Request payload: [session_1, session_2, subnet_1, device_1, subnet_2, device_2, ...]
Reply payload:   [session_1, session_2, remark (20 bytes), big, small, count, ...]

Panels report what they can control (e.g. (1, 12, 64) on a touch panel), not physical
outputs; only devices that answer ReadStatusOfChannels have real channels. Older devices
(DLP panels, logic modules, IP modules, some sensors) do not answer 0xE548 at all.
"""

from dataclasses import dataclass, field

from .remarks import REMARK_LENGTH, DEFAULT_ENCODINGS, decode_remark

# Setup Tool 2 never sends more than 15 pairs (a 32-byte payload).
MAX_EXCLUDED_DEVICES = 15
_FUNCTIONS_OFFSET = 2 + REMARK_LENGTH

BIG_OUTPUT = 1
BIG_CURTAIN = 2
BIG_PANEL = 4
BIG_SENSOR = 5
BIG_AC = 7
BIG_FLOOR_HEATING = 8


@dataclass(frozen=True)
class ModuleFunction:
    big: int
    small: int
    count: int

    @property
    def category(self):
        """Short name of what this function is, as used by the scanner."""
        if self.big == BIG_OUTPUT:
            return {0: "dimmer", 1: "relay", 8: "dmx"}.get(self.small, "output")
        if self.big == BIG_CURTAIN:
            return "curtain"
        if self.big == BIG_PANEL:
            return "dry_contact" if self.small == 0 else "button"
        if self.big == BIG_SENSOR:
            if self.small in (0, 25):
                return "dry_contact"
            # 1 and 4 inferred from motion + illuminance sensors (types 0x0155, 0x0156).
            return {1: "motion", 2: "temperature", 4: "illuminance"}.get(self.small, "sensor")
        if self.big == BIG_AC:
            return "ac"
        if self.big == BIG_FLOOR_HEATING:
            return "floor_heating"
        return "unknown"


@dataclass
class ModuleReply:
    session: tuple
    remark: str = None
    functions: list = field(default_factory=list)


def build_module_read_payload(session, exclude=()):
    """Build a 0xE548 payload. Devices listed in exclude (at most 15) do not answer."""
    session_1, session_2 = session
    if not (1 <= session_1 <= 255 and 1 <= session_2 <= 255):
        raise ValueError("session bytes must be 1-255")

    payload = [session_1, session_2]
    for subnet_id, device_id in list(exclude)[:MAX_EXCLUDED_DEVICES]:
        payload.extend((subnet_id, device_id))
    return payload


def parse_module_reply(payload, encodings=DEFAULT_ENCODINGS):
    """Parse a 0xE549 payload. Returns None if it is too short to hold the remark."""
    if len(payload) < _FUNCTIONS_OFFSET:
        return None

    reply = ModuleReply(
        session=(payload[0], payload[1]),
        remark=decode_remark(payload[2:_FUNCTIONS_OFFSET], encodings),
    )

    rest = payload[_FUNCTIONS_OFFSET:]
    for i in range(0, len(rest) - len(rest) % 3, 3):
        big, small, count = rest[i], rest[i + 1], rest[i + 2]
        # big == 0 holds a base-panel address on some relay/dimmer bases, not a function.
        if big == 0 or count == 0:
            continue
        reply.functions.append(ModuleFunction(big, small, count))
    return reply
