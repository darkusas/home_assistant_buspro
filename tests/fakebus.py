"""In-memory HDL bus with simulated devices, behaving like the captured installations.

FakeBus replaces Buspro.network_interface: every sent telegram is encoded to UDP
bytes, parsed back and offered to each SimDevice, whose replies are delivered to
Buspro as received telegrams on the next loop iteration.
"""

import asyncio

from pybuspro.helpers.telegram_helper import TelegramHelper

from fakes import GATEWAY, wire_telegram

BROADCAST = (255, 255)


def remark_bytes(text):
    if text is None:
        return [0xFF] * 20
    data = list(text.encode("cp1257"))[:20]
    return data + [0] * (20 - len(data))


class SimDevice:
    def __init__(self, address, type_code, remark=None, mac=None, functions=None, levels=None,
                 channel_names=None, answers_search=True, missed_searches=0, answers_remark=True,
                 broadcasts=(), confirms=True, fails=False, curtains=None, universal_switches=None,
                 floor_heating=False, sensor_status=None, temperature=None):
        self.address = address
        self.type_code = type_code
        self.remark = remark
        self.mac = mac or [0x10, 0x20, 0x30, 0x40, 0x50, 0x60, address[0], address[1]]
        self.functions = functions  # list of (big, small, count); None = ignores 0xE548
        self.levels = levels  # list of channel levels; None = not an output module
        self.channel_names = channel_names or {}  # channel -> name; channels missing here do not answer
        self.answers_search = answers_search
        self.missed_searches = missed_searches  # broadcast 0x000E rounds to ignore, like a busy bus
        self.answers_remark = answers_remark
        self.broadcasts = broadcasts  # [(operate_code, payload)] sent once when the bus starts
        self.confirms = confirms  # broadcast 0x0032 after 0x0031
        self.fails = fails  # answer 0x0031 with 0xF5 and do not switch
        self.curtains = curtains  # curtain -> status (0 stop, 1 open, 2 close)
        self.universal_switches = universal_switches  # switch -> bool
        # DLP floor heating: [temperature type, current, status, mode, normal, day, night, away]
        self.floor_heating = [0, 22, 0, 1, 24, 21, 19, 18] if floor_heating else None
        self.sensor_status = sensor_status  # 0x1646 payload answered to 0x1645
        self.temperature = temperature  # answered to ReadTemperature (0xE3E7), like wall panels
        self.received = []

    def reply(self, operate_code, payload, target):
        return wire_telegram(self.address, target, operate_code, payload, device_type=self.type_code)

    def handle(self, telegram):
        to_me = tuple(telegram.target_address) == self.address
        broadcast = tuple(telegram.target_address) == BROADCAST
        if not (to_me or broadcast):
            return []
        self.received.append(telegram)
        code = int.from_bytes(telegram.operate_code_raw, "big")
        source = tuple(telegram.source_address)
        payload = telegram.payload

        if code == 0x000E and self.answers_remark:
            if broadcast:
                if not self.answers_search:
                    return []
                if self.missed_searches > 0:
                    self.missed_searches -= 1
                    return []
            return [self.reply(0x000F, remark_bytes(self.remark), source)]

        if code == 0xE548 and self.functions is not None:
            excluded = {tuple(payload[i:i + 2]) for i in range(2, len(payload) - 1, 2)}
            if self.address in excluded:
                return []
            triples = [value for triple in self.functions for value in triple]
            return [self.reply(0xE549, payload[:2] + remark_bytes(self.remark) + triples, source)]

        if not to_me:
            return []  # like real modules, the rest is only answered when addressed directly

        if code == 0x0033 and self.levels is not None:
            return [self.reply(0x0034, [len(self.levels)] + self.levels, source)]
        if code == 0x0031 and self.levels is not None and 1 <= payload[0] <= len(self.levels):
            if not self.fails:
                self.levels[payload[0] - 1] = payload[1]
            mask = [0] * ((len(self.levels) + 7) // 8)
            for index, level in enumerate(self.levels):
                if level:
                    mask[index // 8] |= 1 << (index % 8)
            answer = [payload[0], 0xF5 if self.fails else 0xF8, self.levels[payload[0] - 1], len(self.levels)]
            return [self.reply(0x0032, answer + mask, BROADCAST)] if self.confirms else []
        if code == 0xE3E0 and self.curtains is not None and payload[0] in self.curtains:
            self.curtains[payload[0]] = payload[1]
            return [self.reply(0xE3E1, [payload[0], payload[1]], BROADCAST)] if self.confirms else []
        if code == 0xE3E2 and self.curtains is not None and payload[0] in self.curtains:
            return [self.reply(0xE3E3, [payload[0], self.curtains[payload[0]]], source)]
        if code == 0x1944 and self.floor_heating is not None:
            return [self.reply(0x1945, self.floor_heating + [0, 0], source)]
        if code == 0x1946 and self.floor_heating is not None and len(payload) >= 7:
            self.floor_heating = [payload[0], self.floor_heating[1]] + list(payload[1:7])
            return [self.reply(0x1947, [0xF8] + list(payload[:7]), BROADCAST)]
        if code == 0xE3E7 and self.temperature is not None:
            return [self.reply(0xE3E8, [payload[0], self.temperature], source)]
        if code == 0x1645 and self.sensor_status is not None:
            return [self.reply(0x1646, self.sensor_status, source)]
        if code == 0xE01C and self.universal_switches is not None:
            self.universal_switches[payload[0]] = payload[1] == 255
            return [self.reply(0xE01D, [payload[0], 1 if payload[1] == 255 else 0], BROADCAST)]
        if code == 0xE018 and self.universal_switches is not None and payload[0] in self.universal_switches:
            return [self.reply(0xE019, [payload[0], 1 if self.universal_switches[payload[0]] else 0], source)]
        if code == 0xF003:
            return [self.reply(0xF004, list(self.mac), source)]
        if code == 0xF00E and payload and payload[0] in self.channel_names:
            return [self.reply(0xF00F, [payload[0]] + remark_bytes(self.channel_names[payload[0]]), source)]
        return []


class FakeBus:
    def __init__(self, buspro, devices, echo=True):
        self.buspro = buspro
        self.devices = devices
        self.echo = echo  # the gateway broadcasts our own telegrams back to us, like on a real LAN
        self.sent = []
        self._helper = TelegramHelper()

    def start(self):
        """Deliver each device's spontaneous broadcasts (temperature, sensor status...)."""
        for device in self.devices:
            for operate_code, payload in device.broadcasts:
                self._deliver(device.reply(operate_code, payload, BROADCAST))

    async def stop(self):
        pass

    async def send_telegram(self, telegram):
        sent = self._helper.build_telegram_from_udp_data(bytes(self._helper.build_send_buffer(telegram)), GATEWAY)
        self.sent.append(sent)
        if self.echo:
            self._deliver(sent)
        for device in self.devices:
            for reply in device.handle(sent):
                self._deliver(reply)

    def broadcast(self, device, operate_code, payload):
        """Let a device send something on its own, e.g. a sensor reporting motion."""
        self._deliver(device.reply(operate_code, payload, BROADCAST))

    def _deliver(self, telegram):
        asyncio.get_running_loop().call_soon(self.buspro._callback_all_messages, telegram)

    def sent_codes(self, target=None):
        return [int.from_bytes(t.operate_code_raw, "big") for t in self.sent
                if target is None or tuple(t.target_address) == target]
