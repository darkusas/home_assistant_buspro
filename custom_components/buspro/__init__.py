"""
Support for Buspro devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/...
"""

import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.const import (
    CONF_HOST, 
    CONF_PORT, 
    CONF_NAME,
)
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.config_entries import ConfigEntry

from .address_validation import validate_buspro_address_str

_LOGGER = logging.getLogger(__name__)

DOMAIN = "buspro"
DATA_BUSPRO = "buspro"
DEPENDENCIES = []

DEFAULT_CONF_NAME = ""

DEFAULT_SCENE_NAME = "BUSPRO SCENE"
DEFAULT_SEND_MESSAGE_NAME = "BUSPRO MESSAGE"

SERVICE_BUSPRO_SEND_MESSAGE = "send_message"
SERVICE_BUSPRO_ACTIVATE_SCENE = "activate_scene"
SERVICE_BUSPRO_UNIVERSAL_SWITCH = "set_universal_switch"
SERVICE_BUSPRO_SCAN = "scan"
SERVICE_BUSPRO_TEST_CHANNEL = "test_channel"

SERVICE_BUSPRO_ATTR_OPERATE_CODE = "operate_code"
SERVICE_BUSPRO_ATTR_ADDRESS = "address"
SERVICE_BUSPRO_ATTR_PAYLOAD = "payload"
SERVICE_BUSPRO_ATTR_SCENE_ADDRESS = "scene_address"
SERVICE_BUSPRO_ATTR_SWITCH_NUMBER = "switch_number"
SERVICE_BUSPRO_ATTR_STATUS = "status"
SERVICE_BUSPRO_ATTR_ROUNDS = "rounds"
SERVICE_BUSPRO_ATTR_INTERVAL = "interval"
SERVICE_BUSPRO_ATTR_READ_NAMES = "read_names"
SERVICE_BUSPRO_ATTR_READ_MAC = "read_mac"
SERVICE_BUSPRO_ATTR_CHANNEL = "channel"
SERVICE_BUSPRO_ATTR_TARGET = "target"
SERVICE_BUSPRO_ATTR_ACTION = "action"
SERVICE_BUSPRO_ATTR_LEVEL = "level"
SERVICE_BUSPRO_ATTR_DURATION = "duration"

TEST_TARGET_ACTIONS = {
    "output": ("on", "off", "level", "pulse"),
    "curtain": ("open", "close", "stop"),
    "universal_switch": ("on", "off"),
}

"""{ "address": [1,74], "scene_address": [3,5] }"""
SERVICE_BUSPRO_ACTIVATE_SCENE_SCHEMA = vol.Schema({
    vol.Required(SERVICE_BUSPRO_ATTR_ADDRESS): vol.Any([cv.positive_int]),
    vol.Required(SERVICE_BUSPRO_ATTR_SCENE_ADDRESS): vol.Any([cv.positive_int]),
})

"""{ "address": [1,74], "operate_code": [4,12], "payload": [1,75,0,3] }"""
SERVICE_BUSPRO_SEND_MESSAGE_SCHEMA = vol.Schema({
    vol.Required(SERVICE_BUSPRO_ATTR_ADDRESS): vol.Any([cv.positive_int]),
    vol.Required(SERVICE_BUSPRO_ATTR_OPERATE_CODE): vol.Any([cv.positive_int]),
    vol.Required(SERVICE_BUSPRO_ATTR_PAYLOAD): vol.Any([cv.positive_int]),
})

"""{ "address": [1,100], "switch_number": 100, "status": 1 }"""
SERVICE_BUSPRO_UNIVERSAL_SWITCH_SCHEMA = vol.Schema({
    vol.Required(SERVICE_BUSPRO_ATTR_ADDRESS): vol.Any([cv.positive_int]),
    vol.Required(SERVICE_BUSPRO_ATTR_SWITCH_NUMBER): vol.Any(cv.positive_int),
    vol.Required(SERVICE_BUSPRO_ATTR_STATUS): vol.Any(cv.positive_int),
})

"""{ "rounds": 4, "interval": 10, "read_names": true, "read_mac": true }"""
SERVICE_BUSPRO_SCAN_SCHEMA = vol.Schema({
    vol.Optional(SERVICE_BUSPRO_ATTR_ROUNDS, default=4): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
    vol.Optional(SERVICE_BUSPRO_ATTR_INTERVAL, default=10): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=60)),
    vol.Optional(SERVICE_BUSPRO_ATTR_READ_NAMES, default=True): cv.boolean,
    vol.Optional(SERVICE_BUSPRO_ATTR_READ_MAC, default=True): cv.boolean,
})


def _device_address(value):
    """'1.89' -> (1, 89)"""
    parts = validate_buspro_address_str(value).split(".")
    if len(parts) != 2:
        raise vol.Invalid("address must be '<subnet ID>.<device ID>', e.g. '1.89'")
    return int(parts[0]), int(parts[1])


"""{ "address": "1.89", "channel": 3, "action": "pulse", "duration": 2 }"""
SERVICE_BUSPRO_TEST_CHANNEL_SCHEMA = vol.Schema({
    vol.Required(SERVICE_BUSPRO_ATTR_ADDRESS): vol.All(cv.string, _device_address),
    vol.Required(SERVICE_BUSPRO_ATTR_CHANNEL): vol.All(vol.Coerce(int), vol.Range(min=1, max=255)),
    vol.Optional(SERVICE_BUSPRO_ATTR_TARGET, default="output"): vol.In(list(TEST_TARGET_ACTIONS)),
    vol.Required(SERVICE_BUSPRO_ATTR_ACTION): vol.In(["on", "off", "level", "pulse", "open", "close", "stop"]),
    vol.Optional(SERVICE_BUSPRO_ATTR_LEVEL): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    vol.Optional(SERVICE_BUSPRO_ATTR_DURATION, default=2): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=30)),
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Optional(CONF_NAME, default=DEFAULT_CONF_NAME): cv.string
    })
}, extra=vol.ALLOW_EXTRA)

async def async_setup(hass: HomeAssistant, config: dict):
    """Setup the Buspro component. """
    if DOMAIN not in config:
        return True

    host = config[DOMAIN][CONF_HOST]
    port = config[DOMAIN][CONF_PORT]

    hass.data[DATA_BUSPRO] = BusproModule(hass, host, port)
    await hass.data[DATA_BUSPRO].start()

    hass.data[DATA_BUSPRO].register_services()

    return True

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Setup the Buspro component. """
    hass.data.setdefault(DOMAIN, {})

    host = config_entry.data.get(CONF_HOST, "")
    port = config_entry.data.get(CONF_PORT, 1)

    hass.data[DOMAIN] = BusproModule(hass, host, port)
    await hass.data[DOMAIN].start()

    hass.data[DOMAIN].register_services()

    return True

class BusproModule:
    """Representation of Buspro Object."""

    def __init__(self, hass, host, port):
        """Initialize of Buspro module."""
        self.hass = hass
        self.connected = False
        self.hdl = None
        self.gateway_address_send_receive = ((host, port), ('', port))
        self.scanner = None
        self.controller = None
        self.state_monitor = None
        self.last_scan = None
        self.init_hdl()

    def init_hdl(self):
        """Initialize of Buspro object."""
        # noinspection PyUnresolvedReferences
        from .pybuspro.buspro import Buspro
        from .pybuspro.scanner import BusController, BusScanner, StateMonitor
        self.hdl = Buspro(self.gateway_address_send_receive, self.hass.loop)
        self.scanner = BusScanner(self.hdl)
        self.controller = BusController(self.hdl)
        self.state_monitor = StateMonitor(self.hdl)
        # self.hdl.register_telegram_received_all_messages_cb(self.telegram_received_cb)

    async def start(self):
        """Start Buspro object. Connect to tunneling device."""
        await self.hdl.start(state_updater=False)
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.stop)
        self.connected = True

    # noinspection PyUnusedLocal
    async def stop(self, event):
        """Stop Buspro object. Disconnect from tunneling device."""
        # Channels still in a test pulse go back to their previous level first.
        await self.controller.restore_pending()
        await self.hdl.stop()

    async def service_activate_scene(self, call):
        """Service for activatign a __scene"""
        # noinspection PyUnresolvedReferences
        from .pybuspro.devices.scene import Scene

        attr_address = call.data.get(SERVICE_BUSPRO_ATTR_ADDRESS)
        attr_scene_address = call.data.get(SERVICE_BUSPRO_ATTR_SCENE_ADDRESS)
        scene = Scene(self.hdl, attr_address, attr_scene_address, DEFAULT_SCENE_NAME)
        await scene.run()

    async def service_send_message(self, call):
        """Service for send an arbitrary message"""
        # noinspection PyUnresolvedReferences
        from .pybuspro.devices.generic import Generic

        attr_address = call.data.get(SERVICE_BUSPRO_ATTR_ADDRESS)
        attr_payload = call.data.get(SERVICE_BUSPRO_ATTR_PAYLOAD)
        attr_operate_code = call.data.get(SERVICE_BUSPRO_ATTR_OPERATE_CODE)
        generic = Generic(self.hdl, attr_address, attr_payload, attr_operate_code, DEFAULT_SEND_MESSAGE_NAME)
        await generic.run()

    async def service_set_universal_switch(self, call):
        # noinspection PyUnresolvedReferences
        from .pybuspro.devices.universal_switch import UniversalSwitch

        attr_address = call.data.get(SERVICE_BUSPRO_ATTR_ADDRESS)
        attr_switch_number = call.data.get(SERVICE_BUSPRO_ATTR_SWITCH_NUMBER)
        universal_switch = UniversalSwitch(self.hdl, attr_address, attr_switch_number)

        status = call.data.get(SERVICE_BUSPRO_ATTR_STATUS)
        if status == 1:
            await universal_switch.set_on()
        else:
            await universal_switch.set_off()

    async def service_scan(self, call: ServiceCall) -> ServiceResponse:
        """Service for scanning the bus; returns what was found"""
        # noinspection PyUnresolvedReferences
        from .pybuspro.scanner import ScanOptions

        if self.scanner.running:
            raise HomeAssistantError("An HDL bus scan is already running")

        interval = call.data[SERVICE_BUSPRO_ATTR_INTERVAL]
        options = ScanOptions(
            search_rounds=call.data[SERVICE_BUSPRO_ATTR_ROUNDS],
            search_interval=interval,
            settle_time=interval / 2,
            read_channel_names=call.data[SERVICE_BUSPRO_ATTR_READ_NAMES],
            read_mac=call.data[SERVICE_BUSPRO_ATTR_READ_MAC],
        )
        _LOGGER.info("Starting HDL bus scan")
        result = await self.scanner.scan(options)
        self.last_scan = result

        _LOGGER.info("HDL bus scan found %d devices in %.0f s", len(result.devices), result.duration)
        for device in result.devices:
            _LOGGER.debug("Found %s %s '%s' with %d channels", device.address, device.category,
                          device.remark, len(device.channels))
        return result.to_dict()

    async def service_test_channel(self, call: ServiceCall) -> ServiceResponse:
        """Service for switching a channel directly on the bus, confirmed by the device"""
        # noinspection PyUnresolvedReferences
        from .pybuspro.scanner import BusControlError, CURTAIN_CLOSE, CURTAIN_OPEN, CURTAIN_STOP

        address = call.data[SERVICE_BUSPRO_ATTR_ADDRESS]
        number = call.data[SERVICE_BUSPRO_ATTR_CHANNEL]
        target = call.data[SERVICE_BUSPRO_ATTR_TARGET]
        action = call.data[SERVICE_BUSPRO_ATTR_ACTION]
        level = call.data.get(SERVICE_BUSPRO_ATTR_LEVEL)
        if action not in TEST_TARGET_ACTIONS[target]:
            raise HomeAssistantError(f"Action '{action}' is not available for {target}")
        if action == "level" and level is None:
            raise HomeAssistantError("Action 'level' needs a level")

        try:
            if target == "curtain":
                status = {"open": CURTAIN_OPEN, "close": CURTAIN_CLOSE, "stop": CURTAIN_STOP}[action]
                result = await self.controller.set_curtain(address, number, status)
            elif target == "universal_switch":
                result = await self.controller.set_universal_switch(address, number, action == "on")
            elif action == "pulse":
                result = await self.controller.pulse_channel(
                    address, number, 100 if level is None else level, call.data[SERVICE_BUSPRO_ATTR_DURATION])
            else:
                result = await self.controller.set_channel(
                    address, number, {"on": 100, "off": 0}.get(action, level))
        except BusControlError as err:
            raise HomeAssistantError(str(err)) from err
        return result.to_dict()

    def register_services(self):

        """ activate_scene """
        self.hass.services.async_register(
            DOMAIN, SERVICE_BUSPRO_ACTIVATE_SCENE,
            self.service_activate_scene,
            schema=SERVICE_BUSPRO_ACTIVATE_SCENE_SCHEMA)

        """ send_message """
        self.hass.services.async_register(
            DOMAIN, SERVICE_BUSPRO_SEND_MESSAGE,
            self.service_send_message,
            schema=SERVICE_BUSPRO_SEND_MESSAGE_SCHEMA)

        """ universal_switch """
        self.hass.services.async_register(
            DOMAIN, SERVICE_BUSPRO_UNIVERSAL_SWITCH,
            self.service_set_universal_switch,
            schema=SERVICE_BUSPRO_UNIVERSAL_SWITCH_SCHEMA)

        """ scan """
        async_register_admin_service(
            self.hass, DOMAIN, SERVICE_BUSPRO_SCAN,
            self.service_scan,
            schema=SERVICE_BUSPRO_SCAN_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL)

        """ test_channel: switches real loads, so admins only """
        async_register_admin_service(
            self.hass, DOMAIN, SERVICE_BUSPRO_TEST_CHANNEL,
            self.service_test_channel,
            schema=SERVICE_BUSPRO_TEST_CHANNEL_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL)

    '''
    def telegram_received_cb(self, telegram):
        #     """Call invoked after a KNX telegram was received."""
        #     self.hass.bus.fire('knx_event', {
        #         'address': str(telegram.group_address),
        #         'data': telegram.payload.value
        #     })
        # _LOGGER.info(f"Callback: '{telegram}'")
        return False
    '''
