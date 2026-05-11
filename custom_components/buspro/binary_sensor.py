"""
This component provides binary sensor support for Buspro.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/...
"""

import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA, 
    BinarySensorEntity,
)
from homeassistant.const import (
    CONF_NAME, 
    CONF_DEVICES, 
    CONF_ADDRESS, 
    CONF_TYPE, 
    CONF_DEVICE_CLASS, 
    CONF_ICON,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import callback

from datetime import timedelta
from ..buspro import DATA_BUSPRO
from .address_validation import validate_buspro_address_str

_LOGGER = logging.getLogger(__name__)

DEFAULT_CONF_DEVICE_CLASS = "None"
DEFAULT_CONF_SCAN_INTERVAL = 0
DEFAULT_CONF_DEVICE= "None"
DEFAULT_VIRTUAL_INITIAL_STATE = False
DEFAULT_VIRTUAL_CHANNEL_ON_VALUE = 100
CONF_DEVICE = "device"
CONF_INITIAL_STATE = "initial_state"
CONF_MOTION = 'motion'
CONF_DRY_CONTACT_1 = 'dry_contact_1'
CONF_DRY_CONTACT_2 = 'dry_contact_2'
CONF_UNIVERSAL_SWITCH = 'universal_switch'
CONF_SINGLE_CHANNEL = 'single_channel'
CONF_DRY_CONTACT = 'dry_contact'
CONF_VIRTUAL_DEVICES = "virtual_devices"

SENSOR_TYPES = {
    CONF_MOTION,
    CONF_DRY_CONTACT_1,
    CONF_DRY_CONTACT_2,
    CONF_UNIVERSAL_SWITCH,
    CONF_SINGLE_CHANNEL,
    CONF_DRY_CONTACT,
}


def _parse_channel_address(address: str) -> tuple[tuple[int, int], int]:
    """Parse a Buspro channel address in format subnet.device.channel."""
    validated_address = validate_buspro_address_str(address)
    address_parts = validated_address.split(".")
    if len(address_parts) != 3:
        raise ValueError(
            f"Invalid Buspro channel address '{address}': expected format "
            "'subnet.device.channel' with numeric values"
        )
    return (int(address_parts[0]), int(address_parts[1])), int(address_parts[2])


VIRTUAL_DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_INITIAL_STATE, default=DEFAULT_VIRTUAL_INITIAL_STATE): cv.boolean,
    vol.Optional(CONF_TYPE, default=CONF_SINGLE_CHANNEL): vol.In(SENSOR_TYPES),
    vol.Optional(CONF_DEVICE_CLASS): cv.string,
    vol.Optional(CONF_ICON): cv.icon,
})

def _validate_platform_config(config):
    if not config[CONF_DEVICES] and not config[CONF_VIRTUAL_DEVICES]:
        raise vol.Invalid("Configure at least one of 'devices' or 'virtual_devices'")
    return config


PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend({
        vol.Optional(CONF_DEVICES, default=[]):
            vol.All(cv.ensure_list, [
                vol.All({
                    vol.Required(CONF_ADDRESS): vol.All(validate_buspro_address_str, cv.string),
                    vol.Required(CONF_NAME): cv.string,
                    vol.Required(CONF_TYPE): vol.In(SENSOR_TYPES),
                    vol.Optional(CONF_DEVICE_CLASS, default=DEFAULT_CONF_DEVICE_CLASS): cv.string,
                    vol.Optional(CONF_DEVICE, default=DEFAULT_CONF_DEVICE): cv.string,
                    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_CONF_SCAN_INTERVAL): cv.string,
                })
            ]),
        vol.Optional(CONF_VIRTUAL_DEVICES, default={}): {validate_buspro_address_str: VIRTUAL_DEVICE_SCHEMA},
    }),
    _validate_platform_config,
)


# noinspection PyUnusedLocal
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up Buspro switch devices."""
    # noinspection PyUnresolvedReferences
    from .pybuspro.devices import Sensor
    from .pybuspro.devices import VirtualSingleChannel

    hdl = hass.data[DATA_BUSPRO].hdl
    devices = []

    for device_config in config[CONF_DEVICES]:
        address = device_config[CONF_ADDRESS]
        name = device_config[CONF_NAME]
        sensor_type = device_config[CONF_TYPE]
        device_class = device_config[CONF_DEVICE_CLASS]
        device=device_config[CONF_DEVICE]
        universal_switch_number = None
        channel_number = None
        switch_number = None

        scan_interval = device_config[CONF_SCAN_INTERVAL]
        interval = 0
        if scan_interval is not None:
            interval = int(scan_interval)
            
        if interval > 0:
            SCAN_INTERVAL = timedelta(seconds=interval)
            
        address2 = address.split('.')
        device_address = (int(address2[0]), int(address2[1]))

        if sensor_type == CONF_UNIVERSAL_SWITCH:
            universal_switch_number = int(address2[2])
            _LOGGER.debug("Adding binary sensor '{}' with address {}, universal_switch_number {}, sensor type '{}' "
                            "and device class '{}'".format(name, device_address, universal_switch_number, sensor_type,
                            device_class))
        elif sensor_type == CONF_SINGLE_CHANNEL:
            channel_number = int(address2[2])
            _LOGGER.debug("Adding binary sensor '{}' with address {}, channel_number {}, sensor type '{}' and "
                            "device class '{}'".format(name, device_address, channel_number, sensor_type, device_class))
        elif sensor_type == CONF_DRY_CONTACT:
            switch_number = int(address2[2])
            _LOGGER.debug("Adding binary sensor '{}' with address {}, switch_number '{}' and "
                            "device class '{}'".format(name, device_address, switch_number, device_class))
        else:
            _LOGGER.debug("Adding binary sensor '{}' with address {}, sensor type '{}' and device class '{}'".
                            format(name, device_address, sensor_type, device_class))

        sensor = Sensor(hdl, device_address, universal_switch_number=universal_switch_number,
                        channel_number=channel_number,device=device, switch_number=switch_number, name=name)

        devices.append(BusproBinarySensor(hass, sensor, sensor_type, device_class, interval))

    for address, virtual_device_config in config[CONF_VIRTUAL_DEVICES].items():
        name = virtual_device_config[CONF_NAME]
        sensor_type = virtual_device_config[CONF_TYPE]
        device_class = virtual_device_config.get(CONF_DEVICE_CLASS)
        icon = virtual_device_config.get(CONF_ICON)
        device_address, channel_number = _parse_channel_address(address)
        initial_channel_value = (
            DEFAULT_VIRTUAL_CHANNEL_ON_VALUE
            if bool(virtual_device_config[CONF_INITIAL_STATE])
            else 0
        )

        _LOGGER.debug(
            "Adding virtual binary sensor '%s' with address %s, channel number %s, sensor type '%s', device class '%s'",
            name,
            device_address,
            channel_number,
            sensor_type,
            device_class,
        )

        virtual_sensor = VirtualSingleChannel(
            hdl,
            device_address,
            channel_number,
            name,
            # VirtualSingleChannel stores the raw HDL single-channel level (0-100).
            initial_brightness=initial_channel_value,
        )
        devices.append(
            BusproBinarySensor(
                hass,
                virtual_sensor,
                sensor_type,
                device_class,
                0,
                icon=icon,
                is_virtual=True,
            )
        )

    async_add_entities(devices)


# noinspection PyAbstractClass
class BusproBinarySensor(BinarySensorEntity):
    """Representation of a Buspro switch."""

    def __init__(self, hass, device, sensor_type, device_class, scan_interval, icon=None, is_virtual=False):
        self._hass = hass
        self._device = device
        self._device_class = device_class
        self._icon = icon
        self._is_virtual = is_virtual
        self._sensor_type = sensor_type
        
        self._should_poll = False
        if scan_interval > 0:
            self._should_poll = True

        self.async_register_callbacks()

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
        return self._should_poll

    async def async_update(self, *args):
        if not self._is_virtual and (
            self._sensor_type == CONF_UNIVERSAL_SWITCH or self._sensor_type == CONF_MOTION
        ):
            await self._device.read_sensor_status()

    @property
    def name(self):
        """Return the display name of this light."""
        return self._device.name

    @property
    def available(self):
        """Return True if entity is available."""
        return self._hass.data[DATA_BUSPRO].connected

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    @property
    def icon(self):
        """Return the configured icon."""
        return self._icon

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._device.device_identifier

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        if self._is_virtual:
            return self._device.single_channel_is_on
        if self._sensor_type == CONF_MOTION:
            # _LOGGER.info("----> {}".format(self._device.movement))
            return self._device.movement
        if self._sensor_type == CONF_DRY_CONTACT_1:
            # _LOGGER.info("----> {}".format(self._device.dry_contact_1_is_on))
            return self._device.dry_contact_1_is_on
        if self._sensor_type == CONF_DRY_CONTACT_2:
            return self._device.dry_contact_2_is_on
        if self._sensor_type == CONF_UNIVERSAL_SWITCH:
            return self._device.universal_switch_is_on
        if self._sensor_type == CONF_SINGLE_CHANNEL:
            return self._device.single_channel_is_on
        if self._sensor_type == CONF_DRY_CONTACT:
            return self._device.switch_status
