"""WebSocket commands for the HDL Buspro panel (admins only)."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .address_validation import parse_device_address
from .const import DOMAIN
from .storage import OUTPUT_PLATFORMS, EntitySpec

ENTITY_SCHEMA = vol.Schema({
    vol.Required("platform"): vol.In(OUTPUT_PLATFORMS),
    vol.Required("address"): vol.All(cv.string, parse_device_address),
    vol.Required("channel"): vol.All(vol.Coerce(int), vol.Range(min=1, max=255)),
    vol.Required("name"): vol.All(cv.string, vol.Length(min=1, max=100)),
    vol.Optional("dimmable", default=True): cv.boolean,
    vol.Optional("running_time", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=3600)),
    vol.Optional("device_name"): vol.Any(None, cv.string),
    vol.Optional("device_model"): vol.Any(None, cv.string),
    vol.Optional("mac"): vol.Any(None, cv.string),
})


TEST_ACTIONS = ["on", "off", "level", "pulse", "open", "close", "stop"]


@callback
def async_register(hass: HomeAssistant) -> None:
    for command in (ws_list_entities, ws_add_entities, ws_remove_entities, ws_devices, ws_scan_start,
                    ws_scan_subscribe, ws_channel_test, ws_device_refresh, ws_state_subscribe):
        websocket_api.async_register_command(hass, command)


def _spec_from_message(item: dict) -> EntitySpec:
    subnet_id, device_id = item["address"]
    options = {"dimmable": item["dimmable"], "running_time": item["running_time"]} if item["platform"] == "light" else {}
    return EntitySpec(item["platform"], subnet_id, device_id, item["channel"], item["name"], options,
                      item.get("device_name"), item.get("device_model"), item.get("mac"))


def _entity_info(hass: HomeAssistant, spec: EntitySpec) -> dict:
    entity_id = er.async_get(hass).async_get_entity_id(spec.platform, DOMAIN, spec.unique_id)
    return {"key": spec.key, "entity_id": entity_id, **spec.as_dict()}


@websocket_api.websocket_command({vol.Required("type"): "buspro/entities/list"})
@websocket_api.require_admin
@callback
def ws_list_entities(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    store = hass.data[DOMAIN].entity_store
    connection.send_result(msg["id"], {"entities": [_entity_info(hass, spec) for spec in store.specs]})


@websocket_api.websocket_command({
    vol.Required("type"): "buspro/entities/add",
    vol.Required("entities"): [ENTITY_SCHEMA],
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_add_entities(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    specs = [_spec_from_message(item) for item in msg["entities"]]
    added, rejected = await hass.data[DOMAIN].async_add_entity_specs(specs)
    connection.send_result(msg["id"], {
        "added": [spec.key for spec in added],
        "rejected": [{"key": spec.key, "reason": reason} for spec, reason in rejected],
    })


@websocket_api.websocket_command({
    vol.Required("type"): "buspro/entities/remove",
    vol.Required("keys"): [cv.string],
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_remove_entities(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    removed = await hass.data[DOMAIN].async_remove_entity_specs(msg["keys"])
    connection.send_result(msg["id"], {"removed": [spec.key for spec in removed]})


# Scan, test and live state for the panel


def _scan_with_entities(module) -> dict | None:
    """The last scan result, with the entity (if any) of every output channel."""
    if module.last_scan is None:
        return None
    data = module.last_scan.to_dict()
    for device in data["devices"]:
        subnet_id, device_id = (int(part) for part in device["address"].split("."))
        for channel in device["channels"]:
            channel["entity"] = (module.channel_entity(subnet_id, device_id, channel["number"])
                                 if device["category"] == "output_module" else None)
    return data


@websocket_api.websocket_command({vol.Required("type"): "buspro/devices"})
@websocket_api.require_admin
@callback
def ws_devices(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    module = hass.data[DOMAIN]
    progress = module.scan_progress
    connection.send_result(msg["id"], {
        "scanning": module.scanner.running,
        "progress": vars(progress) if progress else None,
        "scan": _scan_with_entities(module),
    })


@websocket_api.websocket_command({
    vol.Required("type"): "buspro/scan/start",
    vol.Optional("rounds", default=4): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
    vol.Optional("interval", default=10): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=60)),
    vol.Optional("read_names", default=True): cv.boolean,
    vol.Optional("read_mac", default=True): cv.boolean,
})
@websocket_api.require_admin
@callback
def ws_scan_start(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    module = hass.data[DOMAIN]
    if module.scanner.running:
        connection.send_error(msg["id"], "scan_running", "An HDL bus scan is already running")
        return
    options = module.scan_options(msg["rounds"], msg["interval"], msg["read_names"], msg["read_mac"])
    hass.async_create_background_task(module.async_run_scan(options), "buspro bus scan")
    connection.send_result(msg["id"])


@websocket_api.websocket_command({vol.Required("type"): "buspro/scan/subscribe"})
@websocket_api.require_admin
@callback
def ws_scan_subscribe(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    @callback
    def forward(event: dict) -> None:
        connection.send_message(websocket_api.event_message(msg["id"], event))

    connection.subscriptions[msg["id"]] = hass.data[DOMAIN].add_scan_listener(forward)
    connection.send_result(msg["id"])


@websocket_api.websocket_command({
    vol.Required("type"): "buspro/channel/test",
    vol.Required("address"): vol.All(cv.string, parse_device_address),
    vol.Required("channel"): vol.All(vol.Coerce(int), vol.Range(min=1, max=255)),
    vol.Optional("target", default="output"): vol.In(["output", "curtain", "universal_switch"]),
    vol.Required("action"): vol.In(TEST_ACTIONS),
    vol.Optional("level"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    vol.Optional("duration", default=2): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=30)),
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_channel_test(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    try:
        result = await hass.data[DOMAIN].async_test_channel(
            msg["address"], msg["channel"], msg["target"], msg["action"], msg.get("level"), msg["duration"])
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "test_failed", str(err))
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({
    vol.Required("type"): "buspro/device/refresh",
    vol.Required("address"): vol.All(cv.string, parse_device_address),
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_device_refresh(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Read channel levels again; the answer also reaches state subscribers."""
    from .pybuspro.helpers.enums import OperateCode

    reply = await hass.data[DOMAIN].hdl.request(msg["address"], OperateCode.ReadStatusOfChannels, (),
                                                OperateCode.ReadStatusOfChannelsResponse, timeout=1.5)
    levels = None
    if reply is not None and reply.payload:
        levels = reply.payload[1:1 + reply.payload[0]]
    connection.send_result(msg["id"], {"levels": levels})


def _update_dict(update) -> dict:
    return {"kind": update.kind, "number": update.number, "value": update.value,
            "operate_code": f"0x{update.operate_code:04X}"}


@websocket_api.websocket_command({
    vol.Required("type"): "buspro/state/subscribe",
    vol.Required("address"): vol.All(cv.string, parse_device_address),
})
@websocket_api.require_admin
@callback
def ws_state_subscribe(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Live values of one device; updates from one telegram arrive together."""
    monitor = hass.data[DOMAIN].state_monitor
    pending = []

    @callback
    def flush() -> None:
        if pending and msg["id"] in connection.subscriptions:
            connection.send_message(websocket_api.event_message(
                msg["id"], {"updates": [_update_dict(update) for update in pending]}))
        pending.clear()

    @callback
    def on_update(update) -> None:
        if not pending:
            hass.loop.call_soon(flush)
        pending.append(update)

    connection.subscriptions[msg["id"]] = monitor.subscribe(on_update, msg["address"])
    connection.send_result(msg["id"])
    pending.extend(monitor.snapshot(msg["address"]))
    flush()
