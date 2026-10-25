"""Payloads taken verbatim from HDL Buspro Setup Tool 2 captures of two installations.

See docs/protocol-captures/2026-10-25-analysis.md.
"""

from pybuspro.scanner import parse_channel_remark, parse_device_remark, parse_module_reply


def payload(hex_string):
    return list(bytes.fromhex(hex_string))


def test_device_remarks_are_cp1257():
    assert parse_device_remark(payload("d0696c64796d6173" + "00" * 12)) == "Šildymas"
    assert parse_device_remark(payload("5376657461696eeb2f20e1207465726173e00000")) == "Svetainė/ į terasą"


def test_device_remark_with_trailing_bytes_or_short():
    # IP modules append data after the 20-byte remark; an old PIR sends only 6 bytes.
    assert parse_device_remark(payload("3141204950206d6f64756c6973000000000000003036365f4e45544950")) == "1A IP modulis"
    assert parse_device_remark(payload("304120506972")) == "0A Pir"


def test_channel_remarks():
    assert parse_channel_remark(payload("01426f696c657269732064312e342e342e32000000")) == (1, "Boileris d1.4.4.2")
    assert parse_channel_remark(payload("02" + "ff" * 20)) == (2, None)


def test_module_reply_relay_and_curtain():
    relay = parse_module_reply(payload("0739526f7a6574eb730000000000000000000000000001010c"))
    assert relay.session == (0x07, 0x39)
    assert relay.remark == "Rozetės"
    assert [(f.big, f.small, f.count, f.category) for f in relay.functions] == [(1, 1, 12, "relay")]

    curtain = parse_module_reply(payload("07395376657461696eeb732075fe756f6c6169646100020001"))
    assert curtain.remark == "Svetainės užuolaida"
    assert [(f.category, f.count) for f in curtain.functions] == [("curtain", 1)]


def test_module_reply_touch_panel_skips_base_triple():
    panel = parse_module_reply(payload(
        "07395376657461696eeb000000000000000000000000000001010c40020308040120070008080208130008090108050101"))
    assert panel.remark == "Svetainė"
    assert [(f.big, f.small, f.count) for f in panel.functions] == [
        (1, 12, 64), (2, 3, 8), (4, 1, 32), (7, 0, 8), (8, 2, 8), (19, 0, 8), (9, 1, 8), (5, 1, 1)]
