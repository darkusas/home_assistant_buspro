"""
This component provides sensor support for Buspro.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/...
"""

import logging
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, 
    CONF_DEVICES, 
    CONF_ADDRESS, 
    CONF_TYPE, 
    CONF_UNIT_OF_MEASUREMENT,
    ILLUMINANCE, 
    TEMPERATURE, 
    CONF_DEVICE_CLASS, 
    CONF_SCAN_INTERVAL,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfTemperature
from homeassistant.core import callback
from homeassistant.helpers import event
from homeassistant.helpers.entity import Entity

from homeassistant.helpers.dispatcher import async_dispatcher_connect

from ..buspro import DATA_BUSPRO
from .address_validation import validate_buspro_address_str
from .const import SIGNAL_ENTITIES_ADDED
from .storage import device_info

DEFAULT_CONF_UNIT_OF_MEASUREMENT = ""
DEFAULT_CONF_DEVICE_CLASS = "None"
DEFAULT_CONF_SCAN_INTERVAL = 0
DEFAULT_CONF_OFFSET = 0
CONF_DEVICE = "device"
CONF_OFFSET = "offset"
SCAN_INTERVAL = timedelta(minutes=2)

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    ILLUMINANCE,
    TEMPERATURE,
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICES):
        vol.All(cv.ensure_list, [
            vol.All({
                vol.Required(CONF_ADDRESS): vol.All(validate_buspro_address_str, cv.string),
                vol.Required(CONF_NAME): cv.string,
                vol.Required(CONF_TYPE): vol.In(SENSOR_TYPES),
                vol.Optional(CONF_UNIT_OF_MEASUREMENT, default=DEFAULT_CONF_UNIT_OF_MEASUREMENT): cv.string,
                vol.Optional(CONF_DEVICE_CLASS, default=DEFAULT_CONF_DEVICE_CLASS): cv.string,
                #vol.Optional(CONF_DEVICE, default=None): cv.string,
                vol.Optional(CONF_DEVICE, default=""): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_CONF_SCAN_INTERVAL): cv.string,
                vol.Optional(CONF_OFFSET, default=DEFAULT_CONF_OFFSET): cv.string,
            })
        ])
})


# noinspection PyUnusedLocal
#async def async_setup_platform(hass, config, async_add_entites, discovery_info=None):
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up Buspro switch devices."""
    # noinspection PyUnresolvedReferences
    from .pybuspro.devices import Sensor

    hdl = hass.data[DATA_BUSPRO].hdl
    devices = []

    for device_config in config[CONF_DEVICES]:
        address = device_config[CONF_ADDRESS]
        name = device_config[CONF_NAME]
        sensor_type = device_config[CONF_TYPE]
        device = device_config[CONF_DEVICE]
        offset = device_config[CONF_OFFSET]
        
        scan_interval = device_config[CONF_SCAN_INTERVAL]
        interval = 0
        if scan_interval is not None:
            interval = int(scan_interval)
            
        address2 = address.split('.')
        device_address = (int(address2[0]), int(address2[1]))

        _LOGGER.debug("Adding sensor '{}' with address {}, sensor type '{}'".format(
            name, device_address, sensor_type))

        sensor = Sensor(hdl, device_address, device=device, name=name)

        devices.append(BusproSensor(hass, sensor, sensor_type, interval, offset))

    #async_add_entites(devices)
    #for device in devices:
    #    await device.async_read_status()
    async_add_entities(devices)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up temperature and illuminance sensors, and floor heating module floor sensors, from the bus scan."""
    # noinspection PyUnresolvedReferences
    from .pybuspro.devices import FloorSensor, Sensor

    module = hass.data[DATA_BUSPRO]

    def entity(spec):
        if spec.kind == "floor_sensor":
            return BusproFloorSensor(FloorSensor(module.hdl, spec.device_address, spec.channel, spec.name),
                                     device_info(spec))
        return BusproSensor(hass, Sensor(module.hdl, spec.device_address, device=spec.options.get("device", ""),
                                         name=spec.name), spec.kind, 0, DEFAULT_CONF_OFFSET, device_info(spec))

    @callback
    def add(specs):
        async_add_entities([entity(spec) for spec in specs])

    add(module.entity_store.for_platform("sensor"))
    config_entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_ENTITIES_ADDED.format("sensor"), add))


# noinspection PyAbstractClass
class BusproSensor(Entity):
    """Representation of a Buspro switch."""

    def __init__(self, hass, device, sensor_type, scan_interval, offset, device_info=None):
        #self._hass = hass
        self._device = device
        self._attr_device_info = device_info
        self._sensor_type = sensor_type
        #self.async_register_callbacks()
        self._after_update_callback = None        
        self._offset = offset
        self._temperature = None
        self._brightness = None

        self._should_poll = False
        if scan_interval > 0:
            self._should_poll = True

    @callback
    def async_register_callbacks(self):
        """Register callbacks to update hass after device was changed."""

        if self._after_update_callback is not None:
            return

        # noinspection PyUnusedLocal
        async def after_update_callback(device):
            """Call after device was updated."""
            #if self._hass is not None:
                #self._temperature = self._device.temperature
                #self._brightness = self._device.brightness
            self._temperature = self._device.temperature
            self._brightness = self._device.brightness

            # Entity.hass is set by Home Assistant when the entity is added,
            # and set back to None when the entity is removed/unloaded.
            if self.hass is not None:               
                self.async_write_ha_state()

        self._after_update_callback = after_update_callback
        self._device.register_device_updated_cb(after_update_callback)

    async def async_added_to_hass(self):
        self.async_register_callbacks()
        await self.async_read_status()

    async def async_will_remove_from_hass(self):
        if self._after_update_callback is not None:
            self._device.unregister_device_updated_cb(self._after_update_callback)
            self._after_update_callback = None
        self._device.close()


    @property
    def should_poll(self):
        """No polling needed within Buspro unless explicitly set."""
        return self._should_poll

    async def async_update(self, *args):
        await self._device.read_sensor_status()

    @property
    def name(self):
        """Return the display name of this light."""
        return self._device.name

    @property
    def available(self):
        """Return True if entity is available."""
        #connected = self._hass.data[DATA_BUSPRO].connected

        if self.hass is None:
            return False

        connected = self.hass.data[DATA_BUSPRO].connected

        if self._sensor_type == TEMPERATURE:
            return connected and self._current_temperature is not None

        if self._sensor_type == ILLUMINANCE:
            return connected and self._brightness is not None

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._sensor_type == TEMPERATURE:
            return self._current_temperature

        if self._sensor_type == ILLUMINANCE:
            return self._brightness

    @property
    def _current_temperature(self):
        if self._temperature is None:
            return None

        temperature = self._temperature
        if self._offset is not None and temperature != 0:
            temperature = temperature + int(self._offset)

        return temperature

    @property
    def device_class(self):
        """Return the class of this sensor."""
        if self._sensor_type == TEMPERATURE:
            return "temperature"
        if self._sensor_type == ILLUMINANCE:
            return "illuminance"
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        if self._sensor_type == TEMPERATURE:
            return "°C"
        if self._sensor_type == ILLUMINANCE:
            return "lux"
        return ""

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = {}
        attributes['state_class'] = "measurement"
        return attributes

    @property
    def unique_id(self):
        """Return the unique id."""
        return f"{self._device.device_identifier}-{self._sensor_type}"

    async def async_read_status(self):
        """Read the status of the device."""
        await self._device.read_sensor_status()
        #self.async_write_ha_state()
        if self.hass is not None:
            self.async_write_ha_state()

FLOOR_SENSOR_POLL_INTERVAL = timedelta(minutes=1)  # the module reports floor sensors only when asked


# noinspection PyAbstractClass
class BusproFloorSensor(SensorEntity):
    """A 1-wire floor sensor of a floor heating module."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
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
        self.async_on_remove(event.async_track_time_interval(self.hass, self._async_poll, FLOOR_SENSOR_POLL_INTERVAL))
        await self._device.read_status()

    async def async_will_remove_from_hass(self):
        self._device.close()

    async def _async_poll(self, _now=None):
        await self._device.read_status()

    @property
    def available(self):
        return self.hass.data[DATA_BUSPRO].connected and self._device.info is not None

    @property
    def native_value(self):
        return self._device.temperature
