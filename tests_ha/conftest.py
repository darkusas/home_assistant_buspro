"""Home Assistant tests (pytest-homeassistant-custom-component); run with `pytest tests_ha`.

The simulated bus in tests/ imports `pybuspro`; alias it to the integration's own copy
so both sides share one set of classes and enums.
"""

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import custom_components.buspro.pybuspro as integration_pybuspro  # noqa: E402

sys.modules.setdefault("pybuspro", integration_pybuspro)
for name, module in list(sys.modules.items()):
    if name.startswith("custom_components.buspro.pybuspro."):
        sys.modules.setdefault(name.replace("custom_components.buspro.", "", 1), module)
sys.path.insert(0, str(ROOT / "tests"))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


async def setup_integration(hass, devices):
    """Set up the integration from a config entry with a simulated bus instead of UDP."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from fakebus import FakeBus

    entry = MockConfigEntry(domain="buspro", data={"host": "127.0.0.1", "port": 6000})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    module = hass.data["buspro"]
    bus = FakeBus(module.hdl, devices)
    module.hdl.network_interface = bus
    return entry, module, bus
