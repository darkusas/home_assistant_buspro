"""
This component provides light support for Buspro.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/...
"""

import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.light import (
    LightEntity, 
    ColorMode, 
    PLATFORM_SCHEMA, 
    ATTR_BRIGHTNESS
)
from homeassistant.const import (CONF_NAME, CONF_DEVICES)
from homeassistant.core import callback

from ..buspro import DATA_BUSPRO
from .address_validation import validate_buspro_address_str
from datetime import timedelta
import homeassistant.helpers.event as event


_LOGGER = logging.getLogger(__name__)

DEFAULT_DEVICE_RUNNING_TIME = 0
DEFAULT_PLATFORM_RUNNING_TIME = 0
DEFAULT_DIMMABLE = True
DEFAULT_VIRTUAL_DIMMABLE = True
DEFAULT_VIRTUAL_INITIAL_BRIGHTNESS = 0
BRIGHTNESS_LEVEL_VALIDATOR = vol.All(vol.Coerce(int), vol.Range(min=0, max=100))

DEVICE_SCHEMA = vol.Schema({
    vol.Optional("running_time", default=DEFAULT_DEVICE_RUNNING_TIME): cv.positive_int,
    vol.Optional("dimmable", default=DEFAULT_DIMMABLE): cv.boolean,
    vol.Required(CONF_NAME): cv.string,
})

VIRTUAL_DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional("dimmable", default=DEFAULT_VIRTUAL_DIMMABLE): cv.boolean,
    vol.Optional("initial_brightness", default=DEFAULT_VIRTUAL_INITIAL_BRIGHTNESS): BRIGHTNESS_LEVEL_VALIDATOR,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional("running_time", default=DEFAULT_PLATFORM_RUNNING_TIME): cv.positive_int,
    vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA},
    vol.Optional("virtual_devices", default={}): {validate_buspro_address_str: VIRTUAL_DEVICE_SCHEMA},
})


# noinspection PyUnusedLocal
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up Buspro light devices."""
    # noinspection PyUnresolvedReferences
    from .pybuspro.devices import Light
    from .pybuspro.devices import VirtualSingleChannel

    hdl = hass.data[DATA_BUSPRO].hdl
    devices = []
    platform_running_time = int(config["running_time"])

    for address, device_config in config[CONF_DEVICES].items():
        name = device_config[CONF_NAME]
        device_running_time = int(device_config["running_time"])
        dimmable = bool(device_config["dimmable"])

        if device_running_time == 0:
            device_running_time = platform_running_time
        if dimmable:
            device_running_time = 0

        address2 = address.split('.')
        device_address = (int(address2[0]), int(address2[1]))
        channel_number = int(address2[2])
        _LOGGER.debug("Adding light '{}' with address {} and channel number {}".format(name, device_address, channel_number))

        light = Light(hdl, device_address, channel_number, name)
        devices.append(BusproLight(hass, light, device_running_time, dimmable))

    for address, virtual_device_config in config["virtual_devices"].items():
        name = virtual_device_config[CONF_NAME]
        address2 = address.split(".")
        device_address = (int(address2[0]), int(address2[1]))
        channel_number = int(address2[2])
        dimmable = bool(virtual_device_config["dimmable"])
        initial_brightness = int(virtual_device_config["initial_brightness"])

        if not dimmable and initial_brightness > 0:
            _LOGGER.debug(
                "Virtual device '%s' is configured as non-dimmable, mapping initial_brightness=%s to ON state",
                name,
                initial_brightness,
            )
            initial_brightness = 100

        _LOGGER.debug(
            "Adding virtual light '{}' with address {} and channel number {}".format(
                name,
                device_address,
                channel_number,
            )
        )

        virtual_light = VirtualSingleChannel(
            hdl,
            device_address,
            channel_number,
            name,
            initial_brightness=initial_brightness,
        )
        devices.append(BusproLight(hass, virtual_light, 0, dimmable))

    async_add_entities(devices)
    for device in devices:
        await device.async_read_status()


# noinspection PyAbstractClass
class BusproLight(LightEntity):
    """Representation of a Buspro light."""

    def __init__(self, hass, device, running_time, dimmable):
        self._hass = hass
        self._device = device
        self._running_time = running_time
        self._dimmable = dimmable
        
        # <--- OPTIMISTIC MODE: Initialize the override variable
        self._optimistic_brightness = None 

        if self._dimmable:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        else:
            self._attr_color_mode = ColorMode.ONOFF
            self._attr_supported_color_modes = {ColorMode.ONOFF}
        self.async_register_callbacks()
         # Set the polling interval (e.g., every 60 minutes)
        self._polling_interval = timedelta(minutes=60)
        event.async_track_time_interval(hass, self.async_update, self._polling_interval)


    @callback
    def async_register_callbacks(self):
        """Register callbacks to update hass after device was changed."""

        async def after_update_callback(device):
            """Call after device was updated."""
            
            if self._optimistic_brightness is not None:
                if self._dimmable:
                    # Check if hardware reached target brightness
                    target_hdl = int(self._optimistic_brightness / 255 * 100)
                    if device.current_brightness == target_hdl:
                        self._optimistic_brightness = None
                else:
                    # Check ON/OFF for non-dimmable
                    hardware_is_on = device.is_on
                    target_is_on = (self._optimistic_brightness > 0)
                    if hardware_is_on == target_is_on:
                        self._optimistic_brightness = None

            self.async_write_ha_state()

        self._device.register_device_updated_cb(after_update_callback)

    @property
    def should_poll(self):
        """No polling needed within Buspro."""
        return False # Changed to False because we use callbacks, but keeping True is fine too if needed.

    async def async_update(self, *args):
        """Fetch new state data for this light asynchronously."""
        # FIRE AND FORGET: Ask HDL for state, but return instantly.
        # When HDL responds, pybuspro's telegram callback will automatically
        # trigger after_update_callback and refresh the UI later.
        self.hass.async_create_task(self._device.read_status())

    @property
    def name(self):
        """Return the display name of this light."""
        return self._device.name

    @property
    def available(self):
        """Return True if entity is available."""
        return self._hass.data[DATA_BUSPRO].connected

    @property
    def brightness(self):
        """Return the brightness of the light."""
        # <--- OPTIMISTIC MODE: Return fake brightness if pending
        if self._optimistic_brightness is not None:
            return self._optimistic_brightness

        # Standard Logic
        if self._device.current_brightness is None:
            return 0
        brightness = self._device.current_brightness / 100 * 255
        return brightness

    @property
    def is_on(self):
        """Return true if light is on."""
        # <--- OPTIMISTIC MODE: Return fake state if pending
        if self._optimistic_brightness is not None:
            return self._optimistic_brightness > 0
            
        return self._device.is_on

    async def async_turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        target_ha_brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        hdl_brightness = int(target_ha_brightness / 255 * 100)

        if not self.is_on and self._device.previous_brightness is not None and hdl_brightness == 100:
            hdl_brightness = self._device.previous_brightness

        # 1. Update HA instantly so Google Home sees the change immediately
        self._optimistic_brightness = target_ha_brightness
        self.async_write_ha_state()

        # 2. FIRE AND FORGET: Send command to HDL in the background
        self.hass.async_create_task(
            self._device.set_brightness(hdl_brightness, self._running_time)
        )

    async def async_turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        # 1. Update HA instantly so Google Home sees the change immediately
        self._optimistic_brightness = 0
        self.async_write_ha_state()

        # 2. FIRE AND FORGET: Send command to HDL in the background
        self.hass.async_create_task(
            self._device.set_off(self._running_time)
        )
    @property
    def unique_id(self):
        """Return the unique id."""
        return self._device.device_identifier

    async def async_read_status(self):
        """Read the status of the device."""
        await self._device.read_status()
        self.async_write_ha_state()
