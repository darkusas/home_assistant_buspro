import asyncio
import logging


# from ..helpers.generics import Generics
from .control import _ReadSensorStatus, _ReadStatusOfUniversalSwitch, _ReadStatusOfChannels, _ReadFloorHeatingStatus, \
    _ReadDryContactStatus, _ReadSensorsInOneStatus, _ReadMotionSensorStatus
from .device import Device
from ..helpers.enums import *



_LOGGER = logging.getLogger(__name__)

class Sensor(Device):
    def __init__(self, buspro, device_address, universal_switch_number=None, channel_number=None, device=None,
                 switch_number=None, name="", delay_read_current_state_seconds=0):
        super().__init__(buspro, device_address, name)

        self._buspro = buspro
        self._device_address = device_address
        self._universal_switch_number = universal_switch_number
        self._channel_number = channel_number
        self._name = name
        self._device = device
        self._switch_number = switch_number
        
        self._current_temperature = None
        self._brightness = None
        self._motion_sensor = None
        self._sonic = None
        self._dry_contact_1_status = None
        self._dry_contact_2_status = None
        self._universal_switch_status = OnOffStatus.OFF
        self._channel_status = 0
        self._switch_status = 0

        self.register_telegram_received_cb(self._telegram_received_cb)
        self._call_read_current_status_of_sensor(run_from_init=True)

    def _telegram_received_cb(self, telegram):

        # išvedam į debug logą telegram duomenis ir nurodom adddress(kaip device sub ir device id), operate_code ir Device Type, kad matytume gautus telegramus, kurių dar neapdorojame
        try:
            address_high, address_low = self._device_address
            address_high &= 0xFF
            address_low &= 0xFF
            address_str = f"[{address_high}:{address_low}]"
        except Exception:
            address_str = str(self._device_address)

        #if address_str == "[1:70]" or address_str == "[4:190]" or address_str == "[5:130]" or address_str == "[5:131]" or address_str == "[5:136]":
        #    _LOGGER.debug(
        #        f"_telegram_received_cb telegram address: {address_str}, operate_code: {telegram.operate_code} for device type: {str(self._device)}"
        #    )



        if telegram.operate_code == OperateCode.ReadSensorStatusResponse:
            success_or_fail = telegram.payload[0]
            self._current_temperature = telegram.payload[1]
            brightness_high = telegram.payload[2]
            brightness_low = telegram.payload[3]
            self._motion_sensor = telegram.payload[4]
            self._sonic = telegram.payload[5]
            self._dry_contact_1_status = telegram.payload[6]
            self._dry_contact_2_status = telegram.payload[7]
            #if success_or_fail == SuccessOrFailure.Success:
            #    self._brightness = brightness_high + brightness_low
            if success_or_fail == SuccessOrFailure.Success.value[0]:
                self._brightness = (brightness_high << 8) + brightness_low                
            self._call_device_updated()

        elif telegram.operate_code == OperateCode.ReadMotionSensorStatusResponse:
            self._motion_sensor = telegram.payload[3]
            self._call_device_updated()

        elif telegram.operate_code == OperateCode.ReadSensorsInOneStatusResponse:
            self._current_temperature = telegram.payload[1]
            self._current_temperature = self._current_temperature - 20
            brightness_high = telegram.payload[2]
            brightness_low = telegram.payload[3]
            self._motion_sensor = telegram.payload[7]
            self._dry_contact_1_status = telegram.payload[8]
            self._dry_contact_2_status = telegram.payload[9]
            if brightness_high is not None and brightness_low is not None:
                self._brightness = (brightness_high << 8) + brightness_low
            self._call_device_updated()

        elif telegram.operate_code == OperateCode.BroadcastSensorStatusResponse:
            #if(len(telegram.payload>0)):
            if len(telegram.payload) > 0:
                self._current_temperature = telegram.payload[0]
                brightness_high = telegram.payload[1]
                brightness_low = telegram.payload[2]
                self._motion_sensor = telegram.payload[3]
                self._sonic = telegram.payload[4]
                self._dry_contact_1_status = telegram.payload[5]
                self._dry_contact_2_status = telegram.payload[6]
                #self._brightness = brightness_high + brightness_low
                self._brightness = (brightness_high << 8) + brightness_low
                self._call_device_updated()

        elif telegram.operate_code == OperateCode.BroadcastSensorStatusAutoResponse:
            self._current_temperature = telegram.payload[0]
            #if self._device == "12in1":
             #   self._current_temperature = self._current_temperature - 20
            
            brightness_high = telegram.payload[1]
            brightness_low = telegram.payload[2]
            self._motion_sensor = telegram.payload[3]
            self._sonic = telegram.payload[4]
            self._dry_contact_1_status = telegram.payload[5]
            self._dry_contact_2_status = telegram.payload[6]
            #self._brightness = brightness_high + brightness_low
            self._brightness = (brightness_high << 8) + brightness_low            
            self._call_device_updated()

        elif telegram.operate_code == OperateCode.ReadFloorHeatingStatusResponse:
            self._current_temperature = telegram.payload[1]
            self._call_device_updated()

        elif telegram.operate_code == OperateCode.BroadcastTemperatureResponse:
            self._current_temperature = telegram.payload[1]
            self._call_device_updated()

        elif telegram.operate_code == OperateCode.ReadStatusOfUniversalSwitchResponse:
            switch_number = telegram.payload[0]
            universal_switch_status = telegram.payload[1]

            if switch_number == self._universal_switch_number:
                self._universal_switch_status = universal_switch_status
                self._call_device_updated()

        elif telegram.operate_code == OperateCode.BroadcastStatusOfUniversalSwitch:
            if self._universal_switch_number is not None and self._universal_switch_number <= telegram.payload[0]:
                self._universal_switch_status = telegram.payload[self._universal_switch_number]
                self._call_device_updated()

        elif telegram.operate_code == OperateCode.UniversalSwitchControlResponse:
            switch_number = telegram.payload[0]
            universal_switch_status = telegram.payload[1]

            if switch_number == self._universal_switch_number:
                self._universal_switch_status = universal_switch_status
                self._call_device_updated()

        elif telegram.operate_code == OperateCode.ReadStatusOfChannelsResponse:
            if self._channel_number:
                if self._channel_number <= telegram.payload[0]:
                    self._channel_status = telegram.payload[self._channel_number]
                    self._call_device_updated()

        elif telegram.operate_code == OperateCode.SingleChannelControlResponse:
            if self._channel_number == telegram.payload[0]:
                # if telegram.payload[1] == SuccessOrFailure.Success::
                self._channel_status = telegram.payload[2]
                self._call_device_updated()

        elif telegram.operate_code == OperateCode.ReadDryContactStatusResponse:
            if self._switch_number == telegram.payload[1]:
                self._switch_status = telegram.payload[2]
                self._call_device_updated()

        elif telegram.operate_code == OperateCode.BroadcastIlluminance:
            brightness_high = telegram.payload[2]
            brightness_low = telegram.payload[3]
            self._brightness = (brightness_high << 8) + brightness_low            
            self._call_device_updated()

        #else:

            #if address_str == "[1:70]" or address_str == "[4:190]" or address_str == "[5:130]" or address_str == "[5:131]" or address_str == "[5:136]":
                #data_tail = None
                #try:
                #    data_tail = telegram.udp_data[16:]
                #except Exception:
                #    data_tail = None

                #try:
                #    hex_tail = " ".join(f"{b:02X}" for b in data_tail)
                #except Exception:
                #    hex_tail = str(data_tail)

                #_LOGGER.debug(
                #    f"Received unhandled telegram : {telegram}"
                #    f" udp_data[16:]: {hex_tail}"
                #)

    async def read_sensor_status(self):
        if self._universal_switch_number is not None:
            rsous = _ReadStatusOfUniversalSwitch(self._buspro)
            rsous.subnet_id, rsous.device_id = self._device_address
            rsous.switch_number = self._universal_switch_number
            await rsous.send()
        elif self._channel_number is not None:
            rsoc = _ReadStatusOfChannels(self._buspro)
            rsoc.subnet_id, rsoc.device_id = self._device_address
            await rsoc.send()
        elif self._device is not None and self._device == "dlp":
            rfhs = _ReadFloorHeatingStatus(self._buspro)
            rfhs.subnet_id, rfhs.device_id = self._device_address
            await rfhs.send()
        elif self._device is not None and self._device == "dry_contact":
            rdcs = _ReadDryContactStatus(self._buspro)
            rdcs.subnet_id, rdcs.device_id = self._device_address
            rdcs.switch_number = self._switch_number
            await rdcs.send()
        elif self._device is not None and self._device == "sensors_in_one":
            rsios = _ReadSensorsInOneStatus(self._buspro)
            rsios.subnet_id, rsios.device_id = self._device_address
            await rsios.send()
        elif self._device is not None and self._device == "pir":#CMS-PIR Motion Only Fetch
            rms = _ReadMotionSensorStatus(self._buspro)
            rms.subnet_id, rms.device_id = self._device_address
            await rms.send()
        else:#8 in 1
            rss = _ReadSensorStatus(self._buspro)
            rss.subnet_id, rss.device_id = self._device_address
            await rss.send()


    @property
    def temperature(self):
        if self._current_temperature is None:
            return 0
        if self._device is not None and self._device == "dlp":
            return self._current_temperature
        if self._device is not None and self._device == "12in1":
            return self._current_temperature - 20
        if self._device is not None and self._device == "8in1":
            return self._current_temperature - 20
        #return self._current_temperature - 20 #removed this offset of 20 degree
        return self._current_temperature
    @property
    def brightness(self):
        if self._brightness is None:
            return 0
        return self._brightness

    @property
    def movement(self):
        if self._motion_sensor == 1:
            return True
        if self._sonic == 1:
            return True
        if self._motion_sensor == 0:
            return False
        if self._sonic == 0:
            return False

    @property
    def dry_contact_1_is_on(self):
        if self._dry_contact_1_status == 1:
            return True
        else:
            return False

    @property
    def dry_contact_2_is_on(self):
        if self._dry_contact_2_status == 1:
            return True
        else:
            return False

    @property
    def universal_switch_is_on(self):
        if self._universal_switch_status == 1:
            return True
        else:
            return False

    @property
    def single_channel_is_on(self):
        if self._channel_status > 0:
            return True
        else:
            return False

    @property
    def switch_status(self):
        if self._switch_status == 1:
            return True
        else:
            return False

    @property
    def device_identifier(self):
        return f"{self._device_address}-{self._universal_switch_number}-{self._channel_number}-{self._switch_number}"

    def _call_read_current_status_of_sensor(self, run_from_init=False):

        async def read_current_status_of_sensor():
            if run_from_init:
                await asyncio.sleep(5)
            await self.read_sensor_status()

        asyncio.ensure_future(read_current_status_of_sensor(), loop=self._buspro.loop)
