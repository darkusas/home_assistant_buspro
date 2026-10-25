"""Diagnostics for Buspro: the result of the last bus scan."""

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {"mac"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    module = hass.data.get(DOMAIN)
    last_scan = getattr(module, "last_scan", None)
    return {
        "last_scan": None if last_scan is None else async_redact_data(last_scan.to_dict(), TO_REDACT),
    }
