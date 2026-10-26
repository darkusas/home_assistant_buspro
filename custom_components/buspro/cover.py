"""
This component provides cover support for Buspro.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/...
"""

import asyncio
import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.cover import CoverEntity, CoverEntityFeature, CoverDeviceClass, PLATFORM_SCHEMA, ATTR_POSITION
from homeassistant.const import (CONF_NAME, CONF_DEVICES)
from homeassistant.core import callback

from homeassistant.helpers.dispatcher import async_dispatcher_connect

from ..buspro import DATA_BUSPRO
from .const import SIGNAL_ENTITIES_ADDED
from .storage import device_info
from datetime import timedelta
import homeassistant.helpers.event as event
_LOGGER = logging.getLogger(__name__)
DEFAULT_OPENING_TIME = 20
DEFAULT_ADJUSTABLE = True
_adjustable=True

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional("opening_time", default=DEFAULT_OPENING_TIME): cv.positive_int,
    vol.Optional("adjustable", default=DEFAULT_ADJUSTABLE): cv.boolean,    
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICES): {cv.string: DEVICE_SCHEMA},

})


# noinspection PyUnusedLocal
async def async_setup_platform(hass, config, async_add_entites, discovery_info=None):
    """Set up Buspro cover devices."""
    # noinspection PyUnresolvedReferences
    from .pybuspro.devices import Cover

    hdl = hass.data[DATA_BUSPRO].hdl
    devices = []

    for address, device_config in config[CONF_DEVICES].items():
        name = device_config[CONF_NAME]
        opening_time=int(device_config["opening_time"])
        _adjustable=bool(device_config["adjustable"])

        address2 = address.split('.')
        device_address = (int(address2[0]), int(address2[1]))
        channel_number = int(address2[2])
        _LOGGER.debug("Adding cover '{}' with address {} and channel number {} and is adjustable {}".format(name, device_address,
                                                                                        channel_number, _adjustable))

        cover = Cover(hdl, device_address, channel_number, name, opening_time )

        devices.append(BusproCover(hass, cover))

    async_add_entites(devices)
        # Read status of all devices on startup
    for device in devices:
        await device.async_update()


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up curtains added from the bus scan: by running time, or by position for curtains that know it."""
    # noinspection PyUnresolvedReferences
    from .pybuspro.devices import Cover, PositionCover

    module = hass.data[DATA_BUSPRO]

    def entity(spec):
        if spec.options.get("position"):
            return BusproPositionCover(PositionCover(module.hdl, spec.device_address, spec.channel, spec.name),
                                       device_info(spec))
        return BusproCover(hass, Cover(module.hdl, spec.device_address, spec.channel, spec.name,
                                       int(spec.options.get("opening_time", DEFAULT_OPENING_TIME))), device_info(spec))

    @callback
    def add(specs):
        async_add_entities([entity(spec) for spec in specs])

    add(module.entity_store.for_platform("cover"))
    config_entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_ENTITIES_ADDED.format("cover"), add))


# noinspection PyAbstractClass
class BusproCover(CoverEntity):
    """Representation of a Buspro cover."""

    def __init__(self, hass, device, device_info=None):
        self._hass = hass
        self._device = device
        self._attr_device_class = CoverDeviceClass.CURTAIN
        self._attr_device_info = device_info
        # self.setup_features()
        self.async_register_callbacks()
                 # Set the polling interval (e.g., every 30 seconds)
        self._polling_interval = timedelta(minutes=60)

    async def async_added_to_hass(self):
        """Start polling; the timer is cancelled when the entity is removed."""
        self.async_on_remove(event.async_track_time_interval(self.hass, self.async_update, self._polling_interval))

    async def async_will_remove_from_hass(self):
        """Stop listening to the bus when the entity is removed."""
        self._device.close()

    @callback
    def async_register_callbacks(self):
        """Register callbacks to update hass after device was changed."""

        # noinspection PyUnusedLocal
        async def after_update_callback(device):
            """Call after device was updated."""
            self.async_write_ha_state()

        self._device.register_device_updated_cb(after_update_callback)

    @property
    def should_poll(self):
        """No polling needed within Buspro."""
        return True

    @property
    def name(self):
        """Return the display name of this cover."""
        return self._device.name

    @property
    def available(self):
        """Return True if entity is available."""
        return self._hass.data[DATA_BUSPRO].connected

    @property
    def is_closed(self):
        """Return true if cover is closed."""
        return self._device.is_closed

    @property
    def is_closing(self):
        """Return true if cover is closing for 30 seconds after command."""
        return self._device.is_closing

    @property
    def is_opening(self):
        """Return true if cover is opening for 30 seconds after command."""
        return self._device.is_opening
        
    @property
    def current_cover_position(self):
        """Return true if cover is opening for 30 seconds after command."""
        return self._device.current_cover_position
    

    # def setup_features(self):
    #     """Return the list of supported features."""
    #     self._attr_supported_features = (   CoverEntityFeature.OPEN |
    #                                         CoverEntityFeature.CLOSE |
    #                                         CoverEntityFeature.STOP)

    @property
    def supported_features(self) -> CoverEntityFeature:
        """Flag supported features."""
        if _adjustable:
            features = (
                CoverEntityFeature.OPEN
                | CoverEntityFeature.CLOSE
                | CoverEntityFeature.STOP
                | CoverEntityFeature.SET_POSITION
            )
        else:
                features = (
                CoverEntityFeature.OPEN
                | CoverEntityFeature.CLOSE
                | CoverEntityFeature.STOP
            )
        return features

    async def async_open_cover(self, **kwargs):
        """Instruct the cover to open."""
        await self._device.set_open()

    async def async_close_cover(self, **kwargs):
        """Instruct the cover to close."""
        await self._device.set_close()


    async def async_stop_cover(self, **kwargs):
        """Instruct the cover to stop."""
        await self._device.set_stop()

    async def async_read_status(self):
        """Read the status of the device."""
        status = self._device._status
        if status == None:
            """Fetch new state data for this light."""
            await self._device.read_status()
        self.async_write_ha_state()
    
    async def async_update(self, *args):
        """Fetch new state data for this light."""
        await self.async_read_status()

#    async def async_update(self):
 #       """Fetch new state data for this light."""
  #      await self.async_read_status()
    
    async def async_set_cover_position(self, **kwargs):
        position = int(kwargs.get(ATTR_POSITION))
        await self._device.set_position(position)

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._device.device_identifier
        


POSITION_POLL_INTERVAL = timedelta(seconds=30)
FOLLOW_INTERVAL = 2  # seconds between position reads while the curtain moves
FOLLOW_LIMIT = 90  # seconds to follow a movement at most


# noinspection PyAbstractClass
class BusproPositionCover(CoverEntity):
    """A curtain that goes to a percentage itself and reports its position."""

    _attr_device_class = CoverDeviceClass.CURTAIN
    _attr_supported_features = (CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
                                | CoverEntityFeature.SET_POSITION)
    _attr_should_poll = False

    def __init__(self, device, device_info=None):
        self._device = device
        self._attr_device_info = device_info
        self._attr_name = device.name
        self._attr_unique_id = device.device_identifier
        self._follow_task = None

    async def async_added_to_hass(self):
        async def updated(_device):
            self.async_write_ha_state()

        self._device.register_device_updated_cb(updated)
        self.async_on_remove(event.async_track_time_interval(self.hass, self._async_poll, POSITION_POLL_INTERVAL))
        await self._device.read_position()

    async def async_will_remove_from_hass(self):
        if self._follow_task is not None:
            self._follow_task.cancel()
        self._device.close()

    async def _async_poll(self, _now=None):
        await self._device.read_position()

    def _follow(self):
        """Read the position while the curtain moves, until it stops changing."""
        if self._follow_task is not None:
            self._follow_task.cancel()
        self._follow_task = self.hass.async_create_background_task(self._async_follow(), "buspro curtain position")

    async def _async_follow(self):
        last = None
        for _ in range(FOLLOW_LIMIT // FOLLOW_INTERVAL):
            await asyncio.sleep(FOLLOW_INTERVAL)
            if self._device.position is not None and self._device.position == last:
                break
            last = self._device.position
            await self._device.read_position()
        self._device.status = None  # stopped, or no longer followed
        self.async_write_ha_state()

    @property
    def available(self):
        return self.hass.data[DATA_BUSPRO].connected and self._device.position is not None

    @property
    def current_cover_position(self):
        return self._device.position

    @property
    def is_closed(self):
        return None if self._device.position is None else self._device.position == 0

    @property
    def is_opening(self):
        return self._device.is_opening

    @property
    def is_closing(self):
        return self._device.is_closing

    async def async_open_cover(self, **kwargs):
        await self._device.set_open()
        self._follow()

    async def async_close_cover(self, **kwargs):
        await self._device.set_close()
        self._follow()

    async def async_stop_cover(self, **kwargs):
        await self._device.set_stop()
        self._follow()

    async def async_set_cover_position(self, **kwargs):
        await self._device.set_position(int(kwargs[ATTR_POSITION]))
        self._follow()
