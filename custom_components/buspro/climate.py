"""
This component provides sensor support for Buspro.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/...
"""

import logging
from typing import Optional, List

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.climate import (
    PLATFORM_SCHEMA,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_DEVICES,
    CONF_ADDRESS,
    ATTR_TEMPERATURE,
)
#from homeassistant.const import UnitOfTemperature.CELSIUS
from homeassistant.const import UnitOfTemperature
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect

# from homeassistant.helpers.entity import Entity
from ..buspro import DATA_BUSPRO
from .const import SIGNAL_ENTITIES_ADDED
from .entity_helpers import entity_id_changing
from .storage import device_info
# noinspection PyUnresolvedReferences
from .pybuspro.devices.climate import ControlPanelAC
# noinspection PyUnresolvedReferences
from .pybuspro.helpers.enums import OnOffStatus
from datetime import timedelta
import homeassistant.helpers.event as event

from .address_validation import (
    validate_buspro_address_str,
    validate_optional_buspro_address_str,
)

_LOGGER = logging.getLogger(__name__)

PRESET_NONE = "none"
PRESET_AWAY = "away"
PRESET_HOME = "home"
PRESET_SLEEP = "sleep"

HA_PRESET_TO_HDL = {
    PRESET_NONE: 1,     # Normal
    PRESET_HOME: 2,     # Day
    PRESET_SLEEP: 3,    # Night
    PRESET_AWAY: 4,     # Away
}
HDL_TO_HA_PRESET = {
    1: PRESET_NONE,     # Normal
    2: PRESET_HOME,     # Day
    3: PRESET_SLEEP,    # Night
    4: PRESET_AWAY,     # Away
}

CONF_PRESET_MODES = "preset_modes"
CONF_RELAY_ADDRESS = "relay_address"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICES):
        vol.All(cv.ensure_list, [
            vol.All({
                vol.Required(CONF_ADDRESS): vol.All(validate_buspro_address_str, cv.string),
                vol.Required(CONF_NAME): cv.string,
                vol.Optional(CONF_PRESET_MODES, default=[]): vol.All(
                    cv.ensure_list, [vol.In(HA_PRESET_TO_HDL)]
                ),
                vol.Optional(CONF_RELAY_ADDRESS, default=''): vol.All(
                    validate_optional_buspro_address_str,
                    cv.string,
                ),
            })
        ])
})


# noinspection PyUnusedLocal
async def async_setup_platform(hass, config, async_add_entites, discovery_info=None):
    """Set up Buspro switch devices."""
    # noinspection PyUnresolvedReferences
    from .pybuspro.devices import Climate
    from .pybuspro.devices import Sensor

    hdl = hass.data[DATA_BUSPRO].hdl
    devices = []

    for device_config in config[CONF_DEVICES]:
        address = device_config[CONF_ADDRESS]
        name = device_config[CONF_NAME]
        preset_modes = device_config[CONF_PRESET_MODES]

        address2 = address.split('.')
        device_address = (int(address2[0]), int(address2[1]))

        _LOGGER.debug("Adding climate '{}' with address {}".format(name, device_address))

        climate = Climate(hdl, device_address, name)

        relay_sensor = None
        relay_address = device_config[CONF_RELAY_ADDRESS]
        if relay_address:
            relay_address2 = relay_address.split('.')
            relay_device_address = (int(relay_address2[0]), int(relay_address2[1]))
            relay_channel_number = int(relay_address2[2])
            relay_sensor = Sensor(hdl, relay_device_address, channel_number=relay_channel_number)

        devices.append(BusproClimate(hass, climate, preset_modes, relay_sensor))

    async_add_entites(devices)
    for device in devices:
        await device.async_read_status()
    for device in devices:
        await device.async_read_temperature()



# noinspection PyAbstractClass
class BusproClimate(ClimateEntity):
    """Representation of a Buspro switch."""

    def __init__(self, hass, device, preset_modes, relay_sensor):
        self._hass = hass
        self._device = device
        self._target_temperature = self._device.target_temperature
        self._is_on = self._device.is_on
        self._preset_modes = preset_modes
        self._mode = self._device.mode  # 1/3/4

        self._relay_sensor = relay_sensor
        self._relay_sensor_is_on = None
        if self._relay_sensor is not None:
            self._relay_sensor_is_on = self._relay_sensor.single_channel_is_on

        self._enable_turn_on_off_backwards_compatibility = False
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
        
        self._polling_interval = timedelta(minutes=60)
        event.async_track_time_interval(hass, self.async_update, self._polling_interval)
        self.async_register_callbacks()

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.COOL)
    
    @callback
    def async_register_callbacks(self):
        """Register callbacks to update hass after device was changed."""

        # noinspection PyUnusedLocal
        async def after_update_callback(device):
            """Call after device was updated."""
            self._device = device
            self._target_temperature = device.target_temperature
            self._is_on = device.is_on
            self._mode = device.mode

            _LOGGER.debug(f"Device '{self._device.name}', " \
                            f"IsOn: {self._is_on}, " \
                            f"Mode: {self._device.mode}, " \
                            f"TargetTemp: {self._device.target_temperature}")

            if self._hass is not None:
                self.async_write_ha_state()

        async def after_relay_sensor_update_callback(device):
            """Call after device was updated."""
            self._relay_sensor_is_on = device.single_channel_is_on
            self.async_write_ha_state()

        self._device.register_device_updated_cb(after_update_callback)

        if self._relay_sensor is not None:
            self._relay_sensor.register_device_updated_cb(after_relay_sensor_update_callback)

    @property
    def should_poll(self):
        """No polling needed within Buspro."""
        return True

    async def async_update(self, *args):
        """Fetch new state data for this light."""
        await self.async_read_status()
        await self.async_read_temperature()

    @property
    def name(self):
        """Return the display name of this light."""
        return self._device.name

    @property
    def available(self):
        """Return True if entity is available."""
        return self._hass.data[DATA_BUSPRO].connected

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return "°C"

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._device.target_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        target_temperature = self._target_temperature
        if target_temperature is None:
            target_temperature = self._device.target_temperature

        return target_temperature

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp.
        """
        if self._mode not in list(HDL_TO_HA_PRESET):
            return PRESET_NONE
        return HDL_TO_HA_PRESET[self._mode]

    @property
    def preset_modes(self) -> Optional[List[str]]:
        """Return a list of available preset modes.
        Requires SUPPORT_PRESET_MODE.
        """
        if len(self._preset_modes) == 0:
            return None

        keys = HA_PRESET_TO_HDL.keys() & self._preset_modes
        ha_preset_to_hdl_configured = {k:HA_PRESET_TO_HDL[k] for k in keys}
        return list(ha_preset_to_hdl_configured)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode not in list(HA_PRESET_TO_HDL):
            preset_mode = PRESET_NONE
        mode = HA_PRESET_TO_HDL[preset_mode]

        _LOGGER.debug(f"Setting preset mode to '{preset_mode}' ({mode}) for device '{self._device.name}'")

        climate_control = ControlPanelAC()
        climate_control.status = mode

        await self._device.control_ac_status(climate_control)
        self.async_write_ha_state()

    @property
    def hvac_action(self) -> Optional[str]:
        """Return current action ie. heating, idle, off."""
        if self._is_on:
            if self._relay_sensor_is_on is None:
                return HVACAction.COOLING
            else:
                if self._relay_sensor_is_on:
                    return HVACAction.COOLING
                else:
                    return HVACAction.IDLE
        else:
            return HVACAction.OFF

    @property
    def hvac_mode(self) -> Optional[str]:
        """Return current operation ie. heat, cool, idle."""
        if self._is_on:
            return HVACMode.COOL
        else:
            return HVACMode.OFF

    @property
    def hvac_modes(self) -> Optional[List[str]]:
        """Return the list of available operation modes."""
        return [HVACMode.COOL, HVACMode.OFF]

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set operation mode."""
        if hvac_mode == HVACMode.OFF:
            climate_control = ControlPanelAC()
            climate_control.status = OnOffStatus.OFF.value
            await self._device.control_ac_status(climate_control)
            self.async_write_ha_state()
        elif hvac_mode == HVACMode.COOL:
            climate_control = ControlPanelAC()
            climate_control.status = OnOffStatus.ON.value
            await self._device.control_ac_status(climate_control)
            self.async_write_ha_state()
        else:
            _LOGGER.error("Unrecognized hvac mode: %s", hvac_mode)
            return

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._device.device_identifier

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        climate_control = ControlPanelAC()
        target_temperature = int(temperature)

        _LOGGER.debug(f"Setting temperature to {target_temperature}")

        climate_control.normal_temperature = target_temperature
     
        await self._device.control_ac_temperature(climate_control)
        self.async_write_ha_state()

    async def async_read_status(self):
        """Read the status of the device."""
        await self._device.read_status()
        self.async_write_ha_state()

    async def async_read_temperature(self):
        """Read the status of the device."""
        await self._device.read_temperature()
        self.async_write_ha_state()


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up floor heating added from the bus scan: DLP panels and floor heating module zones."""
    # noinspection PyUnresolvedReferences
    from .pybuspro.devices import FloorHeating, FloorHeatingZone

    module = hass.data[DATA_BUSPRO]

    def device(spec):
        if spec.kind == "heating_zone":
            return FloorHeatingZone(module.hdl, spec.device_address, spec.channel, spec.name)
        return FloorHeating(module.hdl, spec.device_address, spec.name)

    @callback
    def add(specs):
        async_add_entities([BusproFloorHeating(device(spec), device_info(spec)) for spec in specs])

    add(module.entity_store.for_platform("climate"))
    config_entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_ENTITIES_ADDED.format("climate"), add))


# HDL floor heating modes (TemperatureMode) as Home Assistant presets.
FLOOR_HEATING_PRESETS = {"normal": 1, "day": 2, "night": 3, "away": 4, "timer": 5}
FLOOR_HEATING_POLL_INTERVAL = timedelta(minutes=1)  # DLP panels do not broadcast the room temperature


# noinspection PyAbstractClass
class BusproFloorHeating(ClimateEntity):
    """Floor heating controlled by a DLP panel, or one zone of a floor heating module."""

    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_preset_modes = list(FLOOR_HEATING_PRESETS)
    _attr_supported_features = (ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
                                | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF)
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1
    _attr_min_temp = 5
    _attr_max_temp = 35
    _attr_should_poll = False

    def __init__(self, device, device_info=None):
        self._device = device
        self._attr_device_info = device_info
        self._attr_name = device.name
        self._attr_unique_id = device.device_identifier

    async def async_added_to_hass(self):
        async def updated(_device):
            self.async_write_ha_state()

        self._device.register_device_updated_cb(updated)
        self.async_on_remove(lambda: self._device.unregister_device_updated_cb(updated))
        self.async_on_remove(event.async_track_time_interval(self.hass, self._async_poll, FLOOR_HEATING_POLL_INTERVAL))
        await self._device.read_status()

    async def async_will_remove_from_hass(self):
        if not entity_id_changing(self):
            self._device.close()

    async def _async_poll(self, _now=None):
        await self._device.read_status()

    @property
    def available(self):
        return self.hass.data[DATA_BUSPRO].connected and self._device.known

    @property
    def hvac_mode(self):
        return HVACMode.HEAT if self._device.is_on else HVACMode.OFF

    @property
    def current_temperature(self):
        return self._device.current_temperature

    @property
    def hvac_action(self):
        """Floor heating modules report their valve; DLP panels do not."""
        heating = getattr(self._device, "heating", None)
        if heating is None:
            return None
        if not self._device.is_on:
            return HVACAction.OFF
        return HVACAction.HEATING if heating else HVACAction.IDLE

    @property
    def target_temperature(self):
        return self._device.target_temperature

    @property
    def preset_mode(self):
        return next((name for name, mode in FLOOR_HEATING_PRESETS.items() if mode == self._device.mode), None)

    async def _set(self, **changes):
        try:
            await self._device.set(**changes)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_set_hvac_mode(self, hvac_mode):
        await self._set(on=hvac_mode == HVACMode.HEAT)

    async def async_turn_on(self):
        await self._set(on=True)

    async def async_turn_off(self):
        await self._set(on=False)

    async def async_set_temperature(self, **kwargs):
        if ATTR_TEMPERATURE in kwargs:
            await self._set(temperature=kwargs[ATTR_TEMPERATURE])

    async def async_set_preset_mode(self, preset_mode):
        await self._set(mode=FLOOR_HEATING_PRESETS[preset_mode])
