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
