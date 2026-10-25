"""Entities added from the bus scan, stored in .storage/buspro.entities (included in backups)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.storage import Store

from .const import DOMAIN

STORAGE_KEY = "buspro.entities"
STORAGE_VERSION = 1

# What can be added from a scan, and as which platforms.
KIND_PLATFORMS = {
    "output": ("switch", "light"),
    "curtain": ("cover",),
    "temperature": ("sensor",),
    "illuminance": ("sensor",),
    "motion": ("binary_sensor",),
    "dry_contact_1": ("binary_sensor",),
    "dry_contact_2": ("binary_sensor",),
    "universal_switch": ("switch", "binary_sensor"),
    "floor_heating": ("climate",),
    "heating_zone": ("climate",),
    "floor_sensor": ("sensor",),
}
OUTPUT_PLATFORMS = KIND_PLATFORMS["output"]
PLATFORMS_IN_USE = sorted({platform for platforms in KIND_PLATFORMS.values() for platform in platforms})
SENSOR_KINDS = ("temperature", "illuminance", "motion", "dry_contact_1", "dry_contact_2")


@dataclass
class EntitySpec:
    platform: str
    subnet_id: int
    device_id: int
    channel: int  # output channel, curtain or universal switch number; 1 for one-per-device kinds
    name: str
    options: dict = field(default_factory=dict)  # light: dimmable, running_time; cover: opening_time; ...
    device_name: str | None = None  # HDL device remark, used for the device registry
    device_model: str | None = None
    mac: str | None = None
    kind: str = "output"  # a key of KIND_PLATFORMS

    @property
    def key(self) -> str:
        """One entity per channel (or per kind and number), whatever its platform."""
        if self.kind == "output":
            return f"{self.subnet_id}.{self.device_id}.{self.channel}"
        return f"{self.subnet_id}.{self.device_id}.{self.kind}.{self.channel}"

    @property
    def device_address(self) -> tuple[int, int]:
        return self.subnet_id, self.device_id

    @property
    def unique_id(self) -> str:
        # Where YAML has the same entity, this is its format (pybuspro device_identifier),
        # so an entity moved from YAML keeps its registry entry.
        address = self.device_address
        if self.kind in ("output", "curtain"):
            return f"{address}-{self.channel}"
        if self.kind in SENSOR_KINDS:
            return f"{address}-None-None-None-{self.kind}"
        if self.kind == "universal_switch":
            if self.platform == "switch":
                return f"{address}-universal-{self.channel}"
            return f"{address}-{self.channel}-None-None-universal_switch"
        if self.kind in ("heating_zone", "floor_sensor"):  # several per floor heating module
            return f"{address}-{self.kind}-{self.channel}"
        return f"{address}-{self.kind}"

    def yaml_unique_ids(self) -> list[tuple[str, str]]:
        """(platform, unique_id) of a YAML entity for the same channel, sensor or switch."""
        address = self.device_address
        if self.kind == "output":
            return [(platform, self.unique_id) for platform in OUTPUT_PLATFORMS]
        if self.kind == "curtain":
            return [("cover", self.unique_id)]
        if self.kind in ("temperature", "illuminance"):
            return [("sensor", self.unique_id)]
        if self.kind in SENSOR_KINDS:
            # YAML binary sensors of one device share this id, whatever their type.
            return [("binary_sensor", f"{address}-None-None-None")]
        if self.kind == "universal_switch":
            return [("binary_sensor", f"{address}-{self.channel}-None-None")]
        return []

    def as_dict(self) -> dict:
        return asdict(self)


def device_info(spec: EntitySpec) -> DeviceInfo:
    """The HDL device an entity belongs to, so its channels are grouped in Home Assistant."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{spec.subnet_id}.{spec.device_id}")},
        name=spec.device_name or f"HDL {spec.subnet_id}.{spec.device_id}",
        manufacturer="HDL",
        model=spec.device_model,
        serial_number=spec.mac,
    )


class EntityStore:
    def __init__(self, hass: HomeAssistant) -> None:
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._specs: dict[str, EntitySpec] = {}

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self._specs = {}
        for item in data.get("entities", []):  # entries without "kind" are outputs (first version)
            spec = EntitySpec(**item)
            self._specs[spec.key] = spec

    @property
    def specs(self) -> list[EntitySpec]:
        return list(self._specs.values())

    def get(self, key: str) -> EntitySpec | None:
        return self._specs.get(key)

    def for_platform(self, platform: str) -> list[EntitySpec]:
        return [spec for spec in self._specs.values() if spec.platform == platform]

    async def async_add(self, specs: list[EntitySpec]) -> None:
        for spec in specs:
            self._specs[spec.key] = spec
        await self._save()

    async def async_remove(self, keys: list[str]) -> list[EntitySpec]:
        removed = [self._specs.pop(key) for key in keys if key in self._specs]
        if removed:
            await self._save()
        return removed

    async def _save(self) -> None:
        await self._store.async_save({"entities": [spec.as_dict() for spec in self._specs.values()]})


TYPE_OVERRIDES_KEY = "buspro.type_overrides"
OVERRIDE_CATEGORIES = ("output_module", "curtain_module", "sensor", "panel", "logic", "gateway")


class TypeOverrideStore:
    """What the user said a device type is, for types the scan cannot classify (or gets wrong)."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store = Store(hass, STORAGE_VERSION, TYPE_OVERRIDES_KEY)
        self.overrides: dict[int, dict] = {}

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self.overrides = {int(code, 16): override for code, override in data.get("overrides", {}).items()}

    async def async_set(self, type_code: int, override: dict | None) -> None:
        if override is None:
            self.overrides.pop(type_code, None)
        else:
            self.overrides[type_code] = override
        await self._store.async_save(
            {"overrides": {f"0x{code:04X}": value for code, value in sorted(self.overrides.items())}})
