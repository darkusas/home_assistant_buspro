"""Decode HDL "remarks": the device and channel names stored by HDL Buspro Setup Tool.

A remark is a fixed 20-byte text field padded with 0x00 (or 0xFF in unprogrammed
flash). The tool writes it in the PC's ANSI code page, so the encoding is not fixed;
cp1257 is the Baltic one (ąčęėįšųūž), gbk covers installers using Chinese Windows.
The encoding order still has to be confirmed on real devices (docs/device-scan-plan.md, stage 0).
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

    Returns (channel, remark) or None if the payload is too short. Layout taken from a
    third-party relay emulator and not yet verified on HDL hardware.
    """
    if len(payload) < 2:
        return None
    return payload[0], decode_remark(payload[1:1 + REMARK_LENGTH], encodings)
