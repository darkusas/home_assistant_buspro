import pytest

from pybuspro.scanner import (
    ModuleFunction,
    build_module_read_payload,
    decode_remark,
    parse_channel_remark,
    parse_device_remark,
    parse_module_reply,
)


def remark_bytes(text, encoding="cp1257", pad=0x00):
    data = list(text.encode(encoding))
    return data + [pad] * (20 - len(data))


@pytest.mark.parametrize("text, encoding", [
    ("Virtuvė", "cp1257"),
    ("Šildymas ŽĄČ", "cp1257"),
    ("Svetainė", "utf-8"),
    ("Relay 1", "ascii"),
])
def test_decode_remark(text, encoding):
    assert decode_remark(remark_bytes(text, encoding)) == text


def test_decode_remark_padding_and_empty():
    assert decode_remark(remark_bytes("Hall", pad=0xFF)) == "Hall"
    assert decode_remark(remark_bytes("  Hall  ")) == "Hall"
    assert decode_remark([0xFF] * 20) is None
    assert decode_remark([0] * 20) is None
    assert decode_remark([1, 2, 3, 0]) is None


def test_decode_remark_custom_encodings():
    data = remark_bytes("Virtuvė", "cp1257")
    assert decode_remark(data, encodings=("latin-1",)) == "Virtuvë"


def test_parse_device_and_channel_remark():
    assert parse_device_remark(remark_bytes("Rėlės 1 aukštas")) == "Rėlės 1 aukštas"
    assert parse_channel_remark([4] + remark_bytes("LED juosta")) == (4, "LED juosta")
    assert parse_channel_remark([4]) is None


def test_parse_module_reply():
    payload = [17, 42] + remark_bytes("MR0816") + [1, 1, 8, 0, 3, 5, 2, 0, 2, 7, 7]
    reply = parse_module_reply(payload)

    assert reply.session == (17, 42)
    assert reply.remark == "MR0816"
    # (0, 3, 5) is a base-panel address and the trailing [7, 7] is incomplete.
    assert reply.functions == [ModuleFunction(1, 1, 8), ModuleFunction(2, 0, 2)]
    assert [f.category for f in reply.functions] == ["relay", "curtain"]


def test_parse_module_reply_too_short():
    assert parse_module_reply([1, 2, 3]) is None
    assert parse_module_reply([1, 2] + remark_bytes("X")).functions == []


@pytest.mark.parametrize("big, small, category", [
    (1, 0, "dimmer"), (1, 1, "relay"), (2, 0, "curtain"), (4, 0, "dry_contact"), (4, 1, "button"),
    (5, 0, "dry_contact"), (5, 25, "dry_contact"), (5, 2, "temperature"), (5, 9, "sensor"),
    (7, 0, "ac"), (8, 0, "floor_heating"), (99, 0, "unknown"),
])
def test_module_function_category(big, small, category):
    assert ModuleFunction(big, small, 1).category == category


def test_build_module_read_payload():
    exclude = [(1, d) for d in range(1, 41)]
    payload = build_module_read_payload((5, 6), exclude)

    assert payload[:2] == [5, 6]
    assert len(payload) == 2 + 32 * 2
    assert payload[2:6] == [1, 1, 1, 2]
    with pytest.raises(ValueError):
        build_module_read_payload((0, 6))
