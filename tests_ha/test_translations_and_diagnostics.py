"""Translations, service descriptions and diagnostics."""

import json
import pathlib

import pytest
from homeassistant.helpers.translation import async_get_translations
from homeassistant.util.yaml import load_yaml_dict

from conftest import setup_integration
from custom_components.buspro.diagnostics import async_get_config_entry_diagnostics
from fakebus import SimDevice
from test_panel_api import connect, scan

pytestmark = [
    pytest.mark.parametrize("expected_lingering_tasks", [True]),
    pytest.mark.parametrize("expected_lingering_timers", [True]),
]

COMPONENT = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "buspro"


def keys(data, prefix=""):
    if not isinstance(data, dict):
        return {prefix}
    return set().union(*(keys(value, f"{prefix}.{key}") for key, value in data.items()))


def test_translations_have_the_same_keys():
    english = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
    assert json.loads((COMPONENT / "translations" / "en.json").read_text(encoding="utf-8")) == english
    lithuanian = json.loads((COMPONENT / "translations" / "lt.json").read_text(encoding="utf-8"))
    assert keys(lithuanian) == keys(english)


async def test_services_are_described(hass):
    await setup_integration(hass, [])
    described = load_yaml_dict(str(COMPONENT / "services.yaml"))
    assert set(described) == set(hass.services.async_services_for_domain("buspro"))
    assert described["send_message"]["fields"]["operate_code"]["example"] == "[4, 78]"
    english = await async_get_translations(hass, "en", "services", ["buspro"])
    for service, description in described.items():
        assert f"component.buspro.services.{service}.name" in english
        for field in description["fields"]:
            assert f"component.buspro.services.{service}.fields.{field}.name" in english
    names = await async_get_translations(hass, "lt", "services", ["buspro"])
    assert names["component.buspro.services.scan.name"] == "Skanuoti HDL magistralę"
    issues = await async_get_translations(hass, "lt", "issues", ["buspro"])
    assert "{port}" in issues["component.buspro.issues.udp_port_unavailable.title"]


async def test_diagnostics(hass, hass_ws_client):
    devices = [SimDevice((1, 89), 0x01AC, "Rėlės", functions=[(1, 1, 2)], levels=[0, 100]),
               SimDevice((1, 19), 0x1194, "AS1-2"), SimDevice((1, 21), 0x1194, "AS1-2 b"),
               SimDevice((1, 22), 0x1196, "Kitas")]
    entry, _module, _bus = await setup_integration(hass, devices)
    client = await connect(hass, hass_ws_client)
    await scan(client)
    await client.result({"type": "buspro/type_override/set", "type_code": "0x1196", "category": "sensor"})
    await client.result({"type": "buspro/entities/add", "entities": [
        {"platform": "switch", "address": "1.89", "channel": 1, "name": "Virtuvė", "mac": "10:20:30:40:50:60:01:59"}]})
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["entry"] == {"host": "**REDACTED**", "port": 6000}
    assert diagnostics["unknown_types"] == {"0x1194": 2}  # 0x1196 is set by hand now
    assert diagnostics["type_overrides"] == {"0x1196": {"category": "sensor"}}
    [entity] = diagnostics["entities"]
    assert (entity["key"], entity["platform"], entity["mac"]) == ("1.89.1", "switch", "**REDACTED**")
    assert {d["mac"] for d in diagnostics["last_scan"]["devices"]} == {"**REDACTED**"}
