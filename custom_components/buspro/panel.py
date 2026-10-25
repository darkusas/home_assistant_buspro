"""The "HDL Buspro" sidebar panel: scan the bus, test channels and add them as entities."""

from __future__ import annotations

import hashlib
import logging
import pathlib

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback

_LOGGER = logging.getLogger(__name__)

PANEL_URL_PATH = "buspro"
STATIC_URL = "/buspro_static"
WEBCOMPONENT = "buspro-panel"
FRONTEND_DIR = pathlib.Path(__file__).parent / "frontend"
_STATIC_REGISTERED = "buspro_static_registered"


def _file_version() -> str:
    """Changes whenever the panel file does, so browsers do not keep an old copy."""
    return hashlib.sha256((FRONTEND_DIR / f"{WEBCOMPONENT}.js").read_bytes()).hexdigest()[:12]


async def async_register(hass: HomeAssistant) -> bool:
    """Register the panel; returns False when the frontend is not loaded."""
    if "frontend" not in hass.config.components:
        _LOGGER.warning("The frontend is not loaded, so the HDL Buspro panel is not available")
        return False
    version = await hass.async_add_executor_job(_file_version)
    if not hass.data.get(_STATIC_REGISTERED):
        # A static path cannot be registered twice, e.g. after the config entry is reloaded.
        await hass.http.async_register_static_paths([StaticPathConfig(STATIC_URL, str(FRONTEND_DIR), False)])
        hass.data[_STATIC_REGISTERED] = True
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=WEBCOMPONENT,
        sidebar_title="HDL Buspro",
        sidebar_icon="mdi:lan",
        module_url=f"{STATIC_URL}/{WEBCOMPONENT}.js?v={version}",
        require_admin=True,
        config={},
    )
    return True


@callback
def async_unregister(hass: HomeAssistant) -> None:
    frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
