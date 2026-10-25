"""Make the bundled pybuspro library importable as a top-level package.

pybuspro has no Home Assistant dependency, so these tests run without Home Assistant.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "buspro"))
