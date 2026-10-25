"""The panel's WebSocket API and its registration in the sidebar."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.setup import async_setup_component

from conftest import setup_integration
from fakebus import SimDevice

# pybuspro devices schedule a delayed first status read and lights poll hourly.
pytestmark = [
    pytest.mark.parametrize("expected_lingering_tasks", [True]),
    pytest.mark.parametrize("expected_lingering_timers", [True]),
]


def relay():
    return SimDevice((1, 89), 0x01AC, "Rėlės 1 aukštas", functions=[(1, 1, 3)], levels=[0, 100, 0],
                     channel_names={1: "Virtuvė", 2: None, 3: None})


class Client:
    """Keeps results and subscription events apart: an event can arrive before a command's result."""

    def __init__(self, raw):
        self.raw = raw
        self.events = []
        self.last_id = 0

    async def call(self, message):
        """Send a command and return its whole result message."""
        self.last_id += 1
        await self.raw.send_json({**message, "id": self.last_id})
        while True:
            response = await asyncio.wait_for(self.raw.receive_json(), 5)
            if response["type"] == "result" and response["id"] == self.last_id:
                return response
            self.events.append(response)

    async def result(self, message):
        response = await self.call(message)
        assert response["success"], response
        return response["result"]

    async def event(self):
        message = self.events.pop(0) if self.events else await asyncio.wait_for(self.raw.receive_json(), 5)
        assert message["type"] == "event", message
        return message["event"]


async def connect(hass, hass_ws_client, *args):
    return Client(await hass_ws_client(hass, *args))


async def scan(client):
    await client.result({"type": "buspro/scan/subscribe"})
    await client.result({"type": "buspro/scan/start", "rounds": 1, "interval": 0.2})
    events = []
    while not events or events[-1]["event"] != "done":
        events.append(await client.event())
    return events


async def test_panel_is_registered_and_served(hass, hass_client):
    hass.config.components.add("frontend")  # the real frontend needs the hass_frontend package
    with patch("custom_components.buspro.panel.panel_custom.async_register_panel", AsyncMock()) as register, \
            patch("custom_components.buspro.panel.frontend.async_remove_panel") as remove:
        entry, _module, _bus = await setup_integration(hass, [relay()])
        kwargs = register.call_args.kwargs
        assert (kwargs["frontend_url_path"], kwargs["webcomponent_name"], kwargs["require_admin"]) == (
            "buspro", "buspro-panel", True)

        client = await hass_client()
        response = await client.get(kwargs["module_url"])
        assert response.status == 200
        assert 'customElements.define("buspro-panel"' in await response.text()

        assert await hass.config_entries.async_unload(entry.entry_id)
        remove.assert_called_once()
        assert await hass.config_entries.async_setup(entry.entry_id)  # static path is not registered twice
        assert register.call_count == 2


async def test_scan_then_add_from_the_panel(hass, hass_ws_client):
    await setup_integration(hass, [relay()])
    client = await connect(hass, hass_ws_client)
    assert (await client.result({"type": "buspro/devices"}))["scan"] is None

    events = await scan(client)
    assert events[0]["event"] == "progress" and events[0]["progress"]["phase"] == "discovery"
    assert events[-1] == {"event": "done", "devices": 1}

    data = await client.result({"type": "buspro/devices"})
    assert data["scanning"] is False
    [device] = data["scan"]["devices"]
    assert (device["address"], device["remark"], device["category"]) == ("1.89", "Rėlės 1 aukštas", "output_module")
    assert [(c["number"], c["name"], c["level"], c["entity"]) for c in device["channels"]] == [
        (1, "Virtuvė", 0, None), (2, None, 100, None), (3, None, 0, None)]

    await client.result({"type": "buspro/entities/add", "entities": [
        {"platform": "switch", "address": "1.89", "channel": 1, "name": "Virtuvė"}]})
    await hass.async_block_till_done()
    channel = (await client.result({"type": "buspro/devices"}))["scan"]["devices"][0]["channels"][0]
    assert channel["entity"] == {"key": "1.89.1", "source": "panel", "platform": "switch",
                                 "entity_id": "switch.virtuve", "name": "Virtuvė"}


async def test_yaml_channels_are_marked(hass, hass_ws_client):
    assert await async_setup_component(hass, "buspro", {"buspro": {"host": "127.0.0.1", "port": 6000}})
    assert await async_setup_component(hass, "switch", {"switch": [
        {"platform": "buspro", "devices": {"1.89.3": {"name": "Yaml relay"}}}]})
    await hass.async_block_till_done()
    await setup_integration(hass, [relay()])
    client = await connect(hass, hass_ws_client)
    await scan(client)

    channels = (await client.result({"type": "buspro/devices"}))["scan"]["devices"][0]["channels"]
    assert channels[2]["entity"] == {"key": "1.89.3", "source": "yaml", "platform": "switch",
                                     "entity_id": "switch.yaml_relay", "name": None}


async def test_scan_start_while_running(hass, hass_ws_client):
    await setup_integration(hass, [relay()])
    client = await connect(hass, hass_ws_client)
    await client.result({"type": "buspro/scan/start", "rounds": 1, "interval": 1})
    response = await client.call({"type": "buspro/scan/start"})
    assert response["error"]["code"] == "scan_running"
    await asyncio.sleep(1.6)  # let the first scan finish


async def test_channel_test_with_live_state(hass, hass_ws_client):
    device = relay()
    await setup_integration(hass, [device])
    client = await connect(hass, hass_ws_client)

    await client.result({"type": "buspro/state/subscribe", "address": "1.89"})

    refreshed = await client.result({"type": "buspro/device/refresh", "address": "1.89"})
    assert refreshed == {"levels": [0, 100, 0]}
    event = await client.event()
    assert [(u["kind"], u["number"], u["value"]) for u in event["updates"]] == [
        ("channel", 1, 0), ("channel", 2, 100), ("channel", 3, 0)]

    result = await client.result({"type": "buspro/channel/test", "address": "1.89", "channel": 1, "action": "on"})
    assert (result["confirmed"], result["value"], result["confirmed_by"]) == (True, 100, "0x0032")
    event = await client.event()
    assert ("channel", 1, 100) in [(u["kind"], u["number"], u["value"]) for u in event["updates"]]
    assert device.levels[0] == 100

    response = await client.call({"type": "buspro/channel/test", "address": "1.89", "channel": 1,
                                  "target": "curtain", "action": "on"})
    assert response["error"]["code"] == "test_failed"
    assert "not available" in response["error"]["message"]


async def test_panel_api_requires_admin(hass, hass_ws_client, hass_read_only_access_token):
    await setup_integration(hass, [relay()])
    client = await connect(hass, hass_ws_client, hass_read_only_access_token)
    for message in ({"type": "buspro/devices"}, {"type": "buspro/scan/start"},
                    {"type": "buspro/channel/test", "address": "1.89", "channel": 1, "action": "on"}):
        response = await client.call(message)
        assert response["error"]["code"] == "unauthorized", message
