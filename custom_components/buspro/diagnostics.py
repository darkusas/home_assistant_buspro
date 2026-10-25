"""Diagnostics for Buspro: the gateway, the last bus scan, types set by hand and the entities added from the panel."""

from collections import Counter

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {"mac", "host"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    module = hass.data.get(DOMAIN)
    last_scan = getattr(module, "last_scan", None)
    scan = None if last_scan is None else last_scan.to_dict()
    entity_store = getattr(module, "entity_store", None)
    override_store = getattr(module, "type_override_store", None)
    return async_redact_data({
        "entry": dict(entry.data),
        "connected": getattr(module, "connected", False),
        "last_scan": scan,
        # What to report so the type can be recognised: type code -> how many devices.
        "unknown_types": None if scan is None else dict(Counter(
            device["type_code"] for device in scan["devices"] if device["category"] == "unknown")),
        "type_overrides": None if override_store is None else {
            f"0x{code:04X}": override for code, override in sorted(override_store.overrides.items())},
        "entities": None if entity_store is None else [{"key": spec.key, **spec.as_dict()} for spec in entity_store.specs],
    }, TO_REDACT)
