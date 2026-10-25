"""Decode HDL "remarks": the device and channel names stored by HDL Buspro Setup Tool.

A remark is a fixed 20-byte text field padded with 0x00, or 0xFF when it was never set.
The tool writes it in the PC's ANSI code page, so the encoding is not fixed. Captures from
two Lithuanian installations decode correctly as cp1257 and never as valid utf-8; gbk
covers installers using Chinese Windows (docs/protocol-captures/2026-10-25-analysis.md).
"""

REMARK_LENGTH = 20
DEFAULT_ENCODINGS = ("utf-8", "cp1257", "gbk", "latin-1")


def decode_remark(data, encodings=DEFAULT_ENCODINGS):
    """Return the remark as text, or None if it is empty or has no printable characters."""
    raw = bytes(b & 0xFF for b in data)
    raw = raw.split(b"\x00", 1)[0].rstrip(b"\xff")

    for encoding in encodings:
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("latin-1")

    text = "".join(ch for ch in text if ch.isprintable()).strip()
    return text or None


def parse_device_remark(payload, encodings=DEFAULT_ENCODINGS):
    """Decode a ReadDeviceRemarkResponse (0x000F) payload, which is the remark itself."""
    return decode_remark(payload[:REMARK_LENGTH], encodings)


def parse_channel_remark(payload, encodings=DEFAULT_ENCODINGS):
    """Decode a ReadChannelRemarkResponse (0xF00F) payload: [channel, remark (20 bytes)].

    Returns (channel, remark) or None if the payload is too short. Unnamed channels
    are all 0xFF and give (channel, None).
    """
    if len(payload) < 2:
        return None
    return payload[0], decode_remark(payload[1:1 + REMARK_LENGTH], encodings)
