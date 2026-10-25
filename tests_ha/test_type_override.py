"""Device types set by hand for what the scan cannot classify, and the UDP port repair issue."""

from unittest.mock import Mock, patch

import pytest
from homeassistant.helpers import issue_registry as ir

from conftest import setup_integration
from fakebus import SimDevice
from test_panel_api import connect, scan

pytestmark = [
    pytest.mark.parametrize("expected_lingering_tasks", [True]),
    pytest.mark.parametrize("expected_lingering_timers", [True]),
]


UDP_CLIENT = "custom_components.buspro.pybuspro.transport.udp_client.UDPClient"


def unknown():
    return SimDevice((1, 19), 0x1194, "AS1-2")


def scanned(data):
    [device] = data["scan"]["devices"]
    return device


async def test_set_and_remove_type_override(hass, hass_ws_client, hass_storage):
    await setup_integration(hass, [unknown()])
    client = await connect(hass, hass_ws_client)
    await scan(client)
    device = scanned(await client.result({"type": "buspro/devices"}))
    assert (device["type_code"], device["category"], device["channels"], device["override"]) == (
        "0x1194", "unknown", [], None)

    result = await client.result({"type": "buspro/type_override/set", "type_code": "0x1194",
                                  "category": "output_module", "kind": "dimmer", "count": 2})
    assert result == {"type_code": "0x1194",
                      "override": {"category": "output_module", "kind": "dimmer", "count": 2}}
    device = scanned(await client.result({"type": "buspro/devices"}))
    assert device["category"] == "output_module"
    assert [(c["number"], c["kind"]) for c in device["channels"]] == [(1, "dimmer"), (2, "dimmer")]
    assert hass_storage["buspro.type_overrides"]["data"] == {
        "overrides": {"0x1194": {"category": "output_module", "kind": "dimmer", "count": 2}}}

    await scan(client)  # a new scan keeps it
    assert scanned(await client.result({"type": "buspro/devices"}))["category"] == "output_module"

    await client.result({"type": "buspro/type_override/set", "type_code": "0x1194", "category": "curtain_module",
                         "kind": "dimmer", "count": 1})
    device = scanned(await client.result({"type": "buspro/devices"}))
    assert device["override"] == {"category": "curtain_module", "count": 1}  # kind is for output modules only
    assert [c["kind"] for c in device["channels"]] == ["curtain"]

    await client.result({"type": "buspro/type_override/remove", "type_code": "0x1194"})
    assert scanned(await client.result({"type": "buspro/devices"}))["category"] == "unknown"
    assert hass_storage["buspro.type_overrides"]["data"] == {"overrides": {}}


async def test_overrides_load_from_storage(hass, hass_ws_client, hass_storage):
    hass_storage["buspro.type_overrides"] = {"version": 1, "minor_version": 1, "key": "buspro.type_overrides",
                                             "data": {"overrides": {"0x1194": {"category": "sensor"}}}}
    _entry, module, _bus = await setup_integration(hass, [unknown()])
    assert module.scanner.type_overrides == {0x1194: {"category": "sensor"}}
    client = await connect(hass, hass_ws_client)
    await scan(client)
    assert scanned(await client.result({"type": "buspro/devices"}))["category"] == "sensor"


async def test_invalid_override_is_rejected(hass, hass_ws_client, hass_read_only_access_token):
    await setup_integration(hass, [unknown()])
    client = await connect(hass, hass_ws_client)
    for message in ({"type_code": "1194", "category": "sensor"},
                    {"type_code": "0x1194", "category": "light"},
                    {"type_code": "0x1194", "category": "output_module", "count": 0}):
        response = await client.call({"type": "buspro/type_override/set", **message})
        assert response["error"]["code"] == "invalid_format", message

    reader = await connect(hass, hass_ws_client, hass_read_only_access_token)
    response = await reader.call({"type": "buspro/type_override/set", "type_code": "0x1194", "category": "sensor"})
    assert response["error"]["code"] == "unauthorized"


async def test_repair_issue_when_udp_port_is_unavailable(hass):
    with patch(f"{UDP_CLIENT}._create_multicast_sock", return_value=None):
        await setup_integration(hass, [])
    issue = ir.async_get(hass).async_get_issue("buspro", "udp_port_unavailable")
    assert issue is not None and issue.translation_placeholders == {"port": "6000"}


async def test_no_repair_issue_when_udp_port_opens(hass):
    async def connect(self):
        self.transport = Mock()

    with patch(f"{UDP_CLIENT}._connect", connect):
        await setup_integration(hass, [])
    assert ir.async_get(hass).async_get_issue("buspro", "udp_port_unavailable") is None
