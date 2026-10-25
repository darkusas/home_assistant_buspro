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
from homeassistant.exceptions import HomeAssistantError, Unauthorized, UnknownUser
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.config_entries import ConfigEntry

from .address_validation import parse_device_address
from .const import PLATFORMS, SIGNAL_ENTITIES_ADDED

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

# pybuspro Sensor "device" for types whose readings need a particular read request.
SENSOR_READ_METHODS = {0x0134: "12in1", 0x0135: "8in1", 0x014A: "sensors_in_one", 0x0018: "pir"}

TEST_TARGET_ACTIONS = {
    "output": ("on", "off", "level", "pulse"),
    "curtain": ("open", "close", "stop"),
    "universal_switch": ("on", "off"),
    "heating_zone": ("on", "off", "level"),  # level: setpoint in °C of the mode the zone uses now
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


"""{ "address": "1.89", "channel": 3, "action": "pulse", "duration": 2 }"""
SERVICE_BUSPRO_TEST_CHANNEL_SCHEMA = vol.Schema({
    vol.Required(SERVICE_BUSPRO_ATTR_ADDRESS): vol.All(cv.string, parse_device_address),
    vol.Required(SERVICE_BUSPRO_ATTR_CHANNEL): vol.All(vol.Coerce(int), vol.Range(min=1, max=255)),
    vol.Optional(SERVICE_BUSPRO_ATTR_TARGET, default="output"): vol.In(list(TEST_TARGET_ACTIONS)),
    vol.Required(SERVICE_BUSPRO_ATTR_ACTION): vol.In(["on", "off", "level", "pulse", "open", "close", "stop"]),
    vol.Optional(SERVICE_BUSPRO_ATTR_LEVEL): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    vol.Optional(SERVICE_BUSPRO_ATTR_DURATION, default=2): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=30)),
})

ISSUE_UDP_PORT = "udp_port_unavailable"


def _register_admin_service(hass, service, handler, schema, supports_response):
    """Like HA's async_register_admin_service, which takes supports_response only in newer versions."""

    async def admin_only(call: ServiceCall):
        if call.context.user_id:
            user = await hass.auth.async_get_user(call.context.user_id)
            if user is None:
                raise UnknownUser(context=call.context)
            if not user.is_admin:
                raise Unauthorized(context=call.context)
        return await handler(call)

    hass.services.async_register(DOMAIN, service, admin_only, schema=schema, supports_response=supports_response)


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
    module = hass.data.get(DOMAIN)
    if not isinstance(module, BusproModule):
        host = config_entry.data.get(CONF_HOST, "")
        port = config_entry.data.get(CONF_PORT, 1)
        module = BusproModule(hass, host, port)
        hass.data[DOMAIN] = module
        await module.start()
        module.register_services()
    # On a reload the running module (and its UDP socket) is reused.

    await module.async_setup_entry(config_entry)
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload the entities added from the bus scan; the bus connection stays for YAML platforms."""
    module = hass.data.get(DOMAIN)
    if isinstance(module, BusproModule):
        module.async_unregister_panel()
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


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
        self.config_entry = None
        self.entity_store = None
        self.type_override_store = None
        self.scan_progress = None
        self._scan_listeners = []
        self._panel_registered = False
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

    async def async_setup_entry(self, config_entry):
        """Load the entities added from the bus scan and register the panel's API."""
        from . import websocket_api
        from .storage import EntityStore, TypeOverrideStore

        self.config_entry = config_entry
        if self.entity_store is None:
            self.entity_store = EntityStore(self.hass)
            await self.entity_store.async_load()
            self.type_override_store = TypeOverrideStore(self.hass)
            await self.type_override_store.async_load()
            self.scanner.type_overrides = dict(self.type_override_store.overrides)
            websocket_api.async_register(self.hass)
        if not self._panel_registered:
            from . import panel
            self._panel_registered = await panel.async_register(self.hass)

    def async_unregister_panel(self):
        if self._panel_registered:
            from . import panel
            panel.async_unregister(self.hass)
            self._panel_registered = False

    def entity_for(self, subnet_id, device_id, kind, number):
        """The entity for a channel, sensor or switch: added from the panel, configured in YAML, or None."""
        from .storage import KIND_PLATFORMS, EntitySpec

        probe = EntitySpec(KIND_PLATFORMS[kind][0], subnet_id, device_id, number, "", kind=kind)
        entity_registry = er.async_get(self.hass)
        spec = self.entity_store.get(probe.key) if self.entity_store else None
        if spec is not None:
            entity_id = entity_registry.async_get_entity_id(spec.platform, DOMAIN, spec.unique_id)
            return {"key": spec.key, "source": "panel", "platform": spec.platform, "entity_id": entity_id,
                    "name": spec.name}
        yaml_entity_id = self._yaml_entity_for(entity_registry, probe)
        if yaml_entity_id is not None:
            return {"key": probe.key, "source": "yaml", "platform": yaml_entity_id.split(".")[0],
                    "entity_id": yaml_entity_id, "name": None}
        return None

    async def async_set_type_override(self, type_code, override):
        """Store (or with None, forget) what a device type is; applies to the last scan right away."""
        await self.type_override_store.async_set(type_code, override)
        self.scanner.type_overrides = dict(self.type_override_store.overrides)
        if self.last_scan is not None:
            for device in self.last_scan.devices:
                if device.type_code == type_code:
                    device.override = override

    def sensor_read_method(self, subnet_id, device_id, device_model, device_category=None):
        """How pybuspro's Sensor should ask this device for its readings."""
        # noinspection PyUnresolvedReferences
        from .pybuspro.scanner.type_codes import PANEL

        if device_category == PANEL:
            return "panel"
        if self.last_scan is not None:
            for device in self.last_scan.devices:
                if (device.subnet_id, device.device_id) == (subnet_id, device_id) and device.category == PANEL:
                    return "panel"
        try:
            type_code = int(device_model, 16) if device_model else None
        except ValueError:
            type_code = None
        return SENSOR_READ_METHODS.get(type_code, "")

    async def async_add_entity_specs(self, specs):
        """Store and create entities. Returns (added specs, [(spec, reason)] rejected)."""
        entity_registry = er.async_get(self.hass)
        added, rejected = [], []
        for spec in specs:
            existing = self.entity_store.get(spec.key)
            if existing is not None or spec.key in {s.key for s in added}:
                platform = existing.platform if existing else spec.platform
                rejected.append((spec, f"{spec.key} is already added as {platform}"))
                continue
            yaml_entity_id = self._yaml_entity_for(entity_registry, spec)
            if yaml_entity_id is not None:
                rejected.append((spec, f"already configured as {yaml_entity_id} (YAML)"))
                continue
            added.append(spec)

        if added:
            await self.entity_store.async_add(added)
            for platform in PLATFORMS:
                platform_specs = [spec for spec in added if spec.platform == platform]
                if platform_specs:
                    async_dispatcher_send(self.hass, SIGNAL_ENTITIES_ADDED.format(platform), platform_specs)
        return added, rejected

    def _yaml_entity_for(self, entity_registry, spec):
        """A running entity for the same thing that this config entry does not own (YAML)."""
        for platform, unique_id in spec.yaml_unique_ids():
            entity_id = entity_registry.async_get_entity_id(platform, DOMAIN, unique_id)
            entry = entity_registry.async_get(entity_id) if entity_id else None
            if (entry is not None and (self.config_entry is None or entry.config_entry_id != self.config_entry.entry_id)
                    and self.hass.states.get(entity_id) is not None):
                return entity_id
        return None

    async def async_remove_entity_specs(self, keys):
        """Remove entities added from the bus scan, and their device when it has no entities left."""
        removed = await self.entity_store.async_remove(keys)
        entity_registry = er.async_get(self.hass)
        device_registry = dr.async_get(self.hass)
        for spec in removed:
            entity_id = entity_registry.async_get_entity_id(spec.platform, DOMAIN, spec.unique_id)
            if entity_id is None:
                continue
            device_id = entity_registry.async_get(entity_id).device_id
            entity_registry.async_remove(entity_id)
            if device_id and not er.async_entries_for_device(entity_registry, device_id,
                                                             include_disabled_entities=True):
                device_registry.async_remove_device(device_id)
        return removed

    async def start(self):
        """Start Buspro object. Connect to tunneling device."""
        await self.hdl.start(state_updater=False)
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.stop)
        self.connected = True
        self._report_udp_socket()

    def _report_udp_socket(self):
        """Show a repair issue when the UDP port could not be opened; nothing reaches the bus then."""
        udp_client = self.hdl.network_interface.udp_client if self.hdl.network_interface else None
        port = self.gateway_address_send_receive[1][1]
        if udp_client is not None and udp_client.transport is None:
            ir.async_create_issue(self.hass, DOMAIN, ISSUE_UDP_PORT, is_fixable=False, severity=ir.IssueSeverity.ERROR,
                                  translation_key=ISSUE_UDP_PORT, translation_placeholders={"port": str(port)})
        else:
            ir.async_delete_issue(self.hass, DOMAIN, ISSUE_UDP_PORT)

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

    @staticmethod
    def scan_options(rounds, interval, read_names, read_mac):
        # noinspection PyUnresolvedReferences
        from .pybuspro.scanner import ScanOptions

        return ScanOptions(search_rounds=rounds, search_interval=interval, settle_time=interval / 2,
                           read_channel_names=read_names, read_mac=read_mac)

    def add_scan_listener(self, listener):
        """listener(event dict) is called with progress, done and error events. Returns a remover."""
        self._scan_listeners.append(listener)

        def remove():
            if listener in self._scan_listeners:
                self._scan_listeners.remove(listener)

        return remove

    def _notify_scan(self, event):
        for listener in list(self._scan_listeners):
            try:
                listener(event)
            except Exception:
                _LOGGER.exception("Scan listener failed")

    async def async_run_scan(self, options):
        """Scan the bus, keep the result and tell listeners how it goes."""
        if self.scanner.running:
            raise HomeAssistantError("An HDL bus scan is already running")

        def progress(scan_progress):
            self.scan_progress = scan_progress
            self._notify_scan({"event": "progress", "progress": vars(scan_progress)})

        _LOGGER.info("Starting HDL bus scan")
        try:
            result = await self.scanner.scan(options, progress)
        except Exception as err:
            self.scan_progress = None
            self._notify_scan({"event": "error", "message": str(err)})
            raise
        self.scan_progress = None
        self.last_scan = result

        _LOGGER.info("HDL bus scan found %d devices in %.0f s", len(result.devices), result.duration)
        for device in result.devices:
            _LOGGER.debug("Found %s %s '%s' with %d channels", device.address, device.category,
                          device.remark, len(device.channels))
        self._notify_scan({"event": "done", "devices": len(result.devices)})
        return result

    async def service_scan(self, call: ServiceCall) -> ServiceResponse:
        """Service for scanning the bus; returns what was found"""
        options = self.scan_options(call.data[SERVICE_BUSPRO_ATTR_ROUNDS], call.data[SERVICE_BUSPRO_ATTR_INTERVAL],
                                    call.data[SERVICE_BUSPRO_ATTR_READ_NAMES], call.data[SERVICE_BUSPRO_ATTR_READ_MAC])
        result = await self.async_run_scan(options)
        return result.to_dict()

    async def async_test_channel(self, address, number, target, action, level=None, duration=2):
        """Switch a channel directly on the bus; returns the device's confirmation as a dict."""
        # noinspection PyUnresolvedReferences
        from .pybuspro.scanner import BusControlError, CURTAIN_CLOSE, CURTAIN_OPEN, CURTAIN_STOP

        if action not in TEST_TARGET_ACTIONS[target]:
            raise HomeAssistantError(f"Action '{action}' is not available for {target}")
        if action == "level" and level is None:
            raise HomeAssistantError("Action 'level' needs a level")
        if target == "heating_zone" and action == "level" and not 5 <= level <= 35:
            raise HomeAssistantError("A floor heating setpoint must be 5-35 °C")

        try:
            if target == "curtain":
                status = {"open": CURTAIN_OPEN, "close": CURTAIN_CLOSE, "stop": CURTAIN_STOP}[action]
                result = await self.controller.set_curtain(address, number, status)
            elif target == "universal_switch":
                result = await self.controller.set_universal_switch(address, number, action == "on")
            elif target == "heating_zone":
                if action == "level":
                    result = await self.controller.set_heating_zone(address, number, temperature=level)
                else:
                    result = await self.controller.set_heating_zone(address, number, on=action == "on")
            elif action == "pulse":
                result = await self.controller.pulse_channel(address, number, 100 if level is None else level,
                                                             duration)
            else:
                result = await self.controller.set_channel(address, number, {"on": 100, "off": 0}.get(action, level))
        except BusControlError as err:
            raise HomeAssistantError(str(err)) from err
        return result.to_dict()

    async def service_test_channel(self, call: ServiceCall) -> ServiceResponse:
        """Service for switching a channel directly on the bus, confirmed by the device"""
        return await self.async_test_channel(
            call.data[SERVICE_BUSPRO_ATTR_ADDRESS], call.data[SERVICE_BUSPRO_ATTR_CHANNEL],
            call.data[SERVICE_BUSPRO_ATTR_TARGET], call.data[SERVICE_BUSPRO_ATTR_ACTION],
            call.data.get(SERVICE_BUSPRO_ATTR_LEVEL), call.data[SERVICE_BUSPRO_ATTR_DURATION])

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
        _register_admin_service(
            self.hass, SERVICE_BUSPRO_SCAN,
            self.service_scan,
            schema=SERVICE_BUSPRO_SCAN_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL)

        """ test_channel: switches real loads, so admins only """
        _register_admin_service(
            self.hass, SERVICE_BUSPRO_TEST_CHANNEL,
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
