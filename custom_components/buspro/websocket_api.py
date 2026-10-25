"""WebSocket commands for the HDL Buspro panel (admins only)."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
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


@callback
def async_register(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_list_entities)
    websocket_api.async_register_command(hass, ws_add_entities)
    websocket_api.async_register_command(hass, ws_remove_entities)


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
