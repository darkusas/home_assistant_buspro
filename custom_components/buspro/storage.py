"""Entities added from the bus scan, stored in .storage/buspro.entities (included in backups)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.storage import Store

from .const import DOMAIN

STORAGE_KEY = "buspro.entities"
STORAGE_VERSION = 1

OUTPUT_PLATFORMS = ("switch", "light")


@dataclass
class EntitySpec:
    platform: str
    subnet_id: int
    device_id: int
    channel: int
    name: str
    options: dict = field(default_factory=dict)  # light: dimmable, running_time
    device_name: str | None = None  # HDL device remark, used for the device registry
    device_model: str | None = None
    mac: str | None = None

    @property
    def key(self) -> str:
        """One output entity per channel, whatever its platform."""
        return f"{self.subnet_id}.{self.device_id}.{self.channel}"

    @property
    def device_address(self) -> tuple[int, int]:
        return self.subnet_id, self.device_id

    @property
    def unique_id(self) -> str:
        # Same format as YAML-configured lights and switches (pybuspro device_identifier),
        # so a channel moved from YAML keeps its entity registry entry.
        return f"{self.device_address}-{self.channel}"

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
        for item in data.get("entities", []):
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
