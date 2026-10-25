"""WebSocket commands for the HDL Buspro panel (admins only)."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .address_validation import parse_device_address
from .const import DOMAIN
from .storage import KIND_PLATFORMS, PLATFORMS_IN_USE, SENSOR_KINDS, EntitySpec

ENTITY_SCHEMA = vol.Schema({
    vol.Optional("kind", default="output"): vol.In(list(KIND_PLATFORMS)),
    vol.Required("platform"): vol.In(PLATFORMS_IN_USE),
    vol.Required("address"): vol.All(cv.string, parse_device_address),
    vol.Optional("channel", default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=255)),
    vol.Required("name"): vol.All(cv.string, vol.Length(min=1, max=100)),
    vol.Optional("dimmable", default=True): cv.boolean,
    vol.Optional("running_time", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=3600)),
    vol.Optional("opening_time", default=20): vol.All(vol.Coerce(int), vol.Range(min=1, max=600)),
    vol.Optional("device_class"): vol.Any(None, cv.string),
    vol.Optional("device_name"): vol.Any(None, cv.string),
    vol.Optional("device_model"): vol.Any(None, cv.string),
    vol.Optional("device_category"): vol.Any(None, cv.string),
    vol.Optional("mac"): vol.Any(None, cv.string),
})

# Which scanned channels can become which kind of entity.
_SENSOR_CHANNEL_KINDS = ("temperature", "illuminance", "motion", "floor_heating")


TEST_ACTIONS = ["on", "off", "level", "pulse", "open", "close", "stop"]


@callback
def async_register(hass: HomeAssistant) -> None:
    for command in (ws_list_entities, ws_add_entities, ws_remove_entities, ws_devices, ws_scan_start,
                    ws_scan_subscribe, ws_channel_test, ws_device_refresh, ws_state_subscribe):
        websocket_api.async_register_command(hass, command)


def _spec_from_message(module, item: dict) -> EntitySpec:
    subnet_id, device_id = item["address"]
    kind, platform = item["kind"], item["platform"]
    options = {}
    if kind == "output" and platform == "light":
        options = {"dimmable": item["dimmable"], "running_time": item["running_time"]}
    elif kind == "curtain":
        options = {"opening_time": item["opening_time"]}
    elif kind in SENSOR_KINDS:
        options = {"device": module.sensor_read_method(subnet_id, device_id, item.get("device_model"),
                                                       item.get("device_category"))}
        if platform == "binary_sensor":
            options["device_class"] = item.get("device_class") or ("motion" if kind == "motion" else None)
    elif kind == "universal_switch" and platform == "binary_sensor":
        options = {"device_class": item.get("device_class")}
    return EntitySpec(platform, subnet_id, device_id, item["channel"], item["name"], options,
                      item.get("device_name"), item.get("device_model"), item.get("mac"), kind)


def entity_kind(category: str, channel_kind: str, number: int) -> str | None:
    """The entity kind a scanned channel can be added as, or None if it cannot be added (yet)."""
    if category == "output_module":
        return "output"
    if category == "curtain_module" and channel_kind == "curtain":
        return "curtain"
    if category in ("sensor", "panel"):
        if channel_kind in _SENSOR_CHANNEL_KINDS and number == 1:
            return channel_kind
        if channel_kind == "dry_contact" and category == "sensor" and number <= 2:
            return f"dry_contact_{number}"
    return None


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
    module = hass.data[DOMAIN]
    specs, invalid = [], []
    for item in msg["entities"]:
        spec = _spec_from_message(module, item)
        if spec.platform not in KIND_PLATFORMS[spec.kind]:
            invalid.append({"key": spec.key, "reason": f"{spec.kind} cannot be a {spec.platform}"})
        else:
            specs.append(spec)
    added, rejected = await module.async_add_entity_specs(specs)
    connection.send_result(msg["id"], {
        "added": [spec.key for spec in added],
        "rejected": invalid + [{"key": spec.key, "reason": reason} for spec, reason in rejected],
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
    """The last scan result, with what each channel can be added as and its entity, if any."""
    if module.last_scan is None:
        return None
    data = module.last_scan.to_dict()
    for device in data["devices"]:
        subnet_id, device_id = (int(part) for part in device["address"].split("."))
        for channel in device["channels"]:
            kind = entity_kind(device["category"], channel["kind"], channel["number"])
            # Outputs and curtains are numbered; sensor readings are one entity per device and kind.
            number = channel["number"] if kind in ("output", "curtain") else 1
            channel["entity_kind"] = kind
            channel["entity_number"] = number if kind else None
            channel["entity"] = module.entity_for(subnet_id, device_id, kind, number) if kind else None
        device["universal_switches"] = [
            {"number": spec.channel, "entity": module.entity_for(subnet_id, device_id, "universal_switch", spec.channel)}
            for spec in module.entity_store.specs
            if spec.kind == "universal_switch" and spec.device_address == (subnet_id, device_id)
        ]
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
    """Ask a device for its current state; the answers also reach state subscribers."""
    from .pybuspro.helpers.enums import OperateCode

    module = hass.data[DOMAIN]
    address = msg["address"]
    scanned = next((d for d in (module.last_scan.devices if module.last_scan else [])
                    if (d.subnet_id, d.device_id) == tuple(address)), None)
    levels = None
    if scanned is None or scanned.category == "output_module":
        reply = await module.hdl.request(address, OperateCode.ReadStatusOfChannels, (),
                                         OperateCode.ReadStatusOfChannelsResponse, timeout=1.5)
        if reply is not None and reply.payload:
            levels = reply.payload[1:1 + reply.payload[0]]
    else:
        for operate_code, payload in _state_reads(module, scanned):
            await module.hdl.network_interface.send_telegram(module.hdl.build_telegram(address, operate_code, payload))
    connection.send_result(msg["id"], {"levels": levels})


def _state_reads(module, device) -> list:
    """Read requests that make a sensor, panel or curtain module report its state."""
    from .pybuspro.helpers.enums import OperateCode

    kinds = {channel.kind for channel in device.channels}
    reads = []
    if device.category == "curtain_module":
        reads += [(OperateCode.CurtainSwitchStatus, [c.number]) for c in device.channels]
    if device.category == "sensor":
        method = module.sensor_read_method(device.subnet_id, device.device_id, f"0x{device.type_code or 0:04X}")
        reads.append({"sensors_in_one": (OperateCode.ReadSensorsInOneStatus, []),
                      "pir": (OperateCode.ReadMotionSensorStatus, [])}.get(method, (OperateCode.ReadSensorStatus, [])))
    if device.category == "panel" and "temperature" in kinds:
        reads.append((OperateCode.ReadTemperature, [1]))
    if "floor_heating" in kinds:
        reads.append((OperateCode.ReadFloorHeatingStatus, []))
    return reads


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
