#!/usr/bin/env python3
"""HDL Buspro probe for protocol verification (docs/device-scan-plan.md, stage 0).

Runs on any PC in the same LAN as the HDL IP gateway; Home Assistant is not needed.
"scan", "remark", "channels", "channel-remarks" and "module" are read-only; "set" and
"pulse" switch real loads (after asking), "raw" sends whatever you give it. Every received telegram is printed and, with --log, appended
to a JSON Lines file that can be attached to docs/protocol-captures/.

  python tools/hdl_probe.py --gateway 192.168.1.10 listen --seconds 30
  python tools/hdl_probe.py --gateway 192.168.1.10 remark 1.89
  python tools/hdl_probe.py --gateway 192.168.1.10 channels 1.89
  python tools/hdl_probe.py --gateway 192.168.1.10 channel-remarks 1.89
  python tools/hdl_probe.py --gateway 192.168.1.10 module            # broadcast 0xE548
  python tools/hdl_probe.py --gateway 192.168.1.10 scan --json scan.json   # what Home Assistant's scan finds
  python tools/hdl_probe.py --gateway 192.168.1.10 pulse 1.89 3 --seconds 2   # on, then back
  python tools/hdl_probe.py --gateway 192.168.1.10 set 1.89 3 off
  python tools/hdl_probe.py --gateway 192.168.1.10 set 1.40 1 open --target curtain
  python tools/hdl_probe.py --gateway 192.168.1.10 raw 1.89 0xF00E 1
  tshark -r capture.pcapng -Y "udp.port==6000" -T fields -e udp.payload | python tools/hdl_probe.py decode -

Close HDL Buspro Setup Tool while probing: both need UDP port 6000 on the same PC.
"""

import argparse
import asyncio
import json
import pathlib
import random
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "buspro"))

from pybuspro.buspro import BROADCAST_ADDRESS, Buspro  # noqa: E402
from pybuspro.helpers.enums import OperateCode  # noqa: E402
from pybuspro.helpers.generics import Generics  # noqa: E402
from pybuspro.helpers.telegram_helper import TelegramHelper  # noqa: E402
from pybuspro.scanner import (  # noqa: E402
    CURTAIN_CLOSE, CURTAIN_OPEN, CURTAIN_STOP, BusController, BusScanner, ScanOptions, build_module_read_payload,
    parse_module_reply,
)

ENCODINGS = ("utf-8", "cp1257", "gbk", "latin-1")
# Reply code -> offset of a possible 20-byte remark in its payload.
REMARK_OFFSETS = {b"\x00\x0f": 0, b"\xf0\x0f": 1, b"\xe5\x49": 2}
READ_CHANNEL_REMARK = 0xF00E
READ_CHANNEL_REMARK_RESPONSE = 0xF00F


def parse_address(text):
    subnet_id, device_id = (int(part) for part in text.split("."))
    return subnet_id, device_id


def try_decode(chunk, encoding):
    raw = bytes(chunk).split(b"\x00", 1)[0].rstrip(b"\xff")
    try:
        return raw.decode(encoding)
    except UnicodeDecodeError:
        return None


def describe(telegram):
    code = telegram.operate_code_raw
    entry = {
        "time": round(time.time(), 3),
        "source": "%d.%d" % tuple(telegram.source_address),
        "target": "%d.%d" % tuple(telegram.target_address),
        "device_type": "0x" + telegram.source_device_type_raw.hex().upper(),
        "operate_code": "0x" + code.hex().upper(),
        "operate_code_name": telegram.operate_code.name if telegram.operate_code else None,
        "payload": bytes(telegram.payload).hex(" ").upper(),
    }
    offset = REMARK_OFFSETS.get(code)
    if offset is not None:
        chunk = telegram.payload[offset:offset + 20]
        entry["remark"] = {encoding: try_decode(chunk, encoding) for encoding in ENCODINGS}
    if code == b"\xe5\x49":
        reply = parse_module_reply(telegram.payload)
        if reply is not None:
            entry["functions"] = [[f.big, f.small, f.count, f.category] for f in reply.functions]
    return entry


def print_entry(entry):
    name = entry["operate_code_name"] or "?"
    print(f"{entry['source']:>7} -> {entry['target']:<7} type {entry['device_type']}  "
          f"{entry['operate_code']} {name:<34} [{entry['payload']}]")
    for key in ("remark", "functions"):
        if key in entry:
            print(f"{'':18}{key}: {entry[key]}")


class Probe:
    def __init__(self, args):
        self.args = args
        self.buspro = None
        self.log = args.log.open("a", encoding="utf-8") if args.log else None
        self.quiet = False

    def write_log(self, entry):
        if self.log is not None:
            self.log.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self.log.flush()

    def on_telegram(self, telegram):
        entry = describe(telegram)
        entry["direction"] = "rx"
        if not self.quiet:
            print_entry(entry)
        self.write_log(entry)

    def log_request(self, target, operate_code, payload):
        code = Generics.operate_code_to_bytes(operate_code)
        print(f"   send -> {'%d.%d' % target:<7} 0x{code.hex().upper()} [{bytes(payload).hex(' ').upper()}]")
        self.write_log({"time": round(time.time(), 3), "direction": "tx", "target": "%d.%d" % target,
                        "operate_code": "0x" + code.hex().upper(), "payload": bytes(payload).hex(" ").upper()})

    async def start(self):
        gateway = (self.args.gateway, self.args.port)
        self.buspro = Buspro((gateway, ("", self.args.port)), asyncio.get_running_loop())
        await self.buspro.start()
        if self.buspro.network_interface.udp_client.transport is None:
            raise SystemExit(f"Could not open UDP port {self.args.port} (is HDL Setup Tool or Home Assistant using it?)")
        self.buspro.add_telegram_listener(self.on_telegram)

    async def stop(self):
        await self.buspro.stop()
        if self.log is not None:
            self.log.close()

    async def send(self, target, operate_code, payload=()):
        self.log_request(target, operate_code, payload)
        await self.buspro.network_interface.send_telegram(Buspro.build_telegram(target, operate_code, payload))

    async def request(self, target, operate_code, payload=(), response_operate_code=None, match=None):
        self.log_request(target, operate_code, payload)
        reply = await self.buspro.request(target, operate_code, payload, response_operate_code, match,
                                          timeout=self.args.timeout, retries=self.args.retries)
        if reply is None:
            print(f"   no reply from {'%d.%d' % target}")
        return reply

    async def cmd_listen(self):
        await asyncio.sleep(self.args.seconds)

    async def cmd_remark(self):
        await self.request(parse_address(self.args.address), OperateCode.ReadDeviceRemark, (),
                           OperateCode.ReadDeviceRemarkResponse)

    async def cmd_channels(self):
        return await self.request(parse_address(self.args.address), OperateCode.ReadStatusOfChannels, (),
                                  OperateCode.ReadStatusOfChannelsResponse)

    async def cmd_channel_remarks(self):
        target = parse_address(self.args.address)
        count = self.args.count
        if count is None:
            reply = await self.cmd_channels()
            if reply is None or not reply.payload:
                raise SystemExit("Channel count unknown; pass --count")
            count = reply.payload[0]
        for channel in range(1, count + 1):
            await self.request(target, READ_CHANNEL_REMARK, [channel], READ_CHANNEL_REMARK_RESPONSE,
                               match=lambda telegram, channel=channel: telegram.payload[:1] == [channel])

    async def cmd_module(self):
        target = parse_address(self.args.address) if self.args.address else BROADCAST_ADDRESS
        payload = build_module_read_payload((random.randint(1, 255), random.randint(1, 255)))
        await self.send(target, OperateCode.ReadDeviceModule, payload)
        await asyncio.sleep(self.args.seconds)

    async def cmd_scan(self):
        self.quiet = not self.args.show_telegrams
        options = ScanOptions(search_rounds=self.args.rounds, search_interval=self.args.interval,
                              settle_time=self.args.interval / 2, request_timeout=self.args.timeout,
                              request_retries=self.args.retries, read_mac=not self.args.no_mac,
                              read_channel_names=not self.args.no_names)

        def progress(p):
            print(f"\r   {p.phase:<10} devices: {p.devices:<4} {p.done}/{p.total}      ", end="", flush=True)

        result = await BusScanner(self.buspro).scan(options, progress)
        print(f"\nFound {len(result.devices)} devices in {result.duration:.0f} s "
              f"(ignored {result.ignored_sources} software sources such as Setup Tool PCs)")
        for device in result.devices:
            data = device.to_dict()
            print(f"{data['address']:>7} {data['type_code']} {data['category']:<18} {str(data['remark'] or ''):<20} "
                  f"MAC {data['mac'] or '-'}  functions {data['functions']}")
            for channel in data["channels"]:
                level = "" if channel["level"] is None else channel["level"]
                print(f"{'':10}{channel['number']:>3} {channel['kind']:<13} {level!s:>4}  {channel['name'] or ''}")
        if self.args.json:
            self.args.json.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Saved to {self.args.json}")

    def controller(self):
        return BusController(self.buspro, confirm_timeout=self.args.timeout)

    @staticmethod
    def print_result(result):
        data = result.to_dict()
        state = "CONFIRMED" if data["confirmed"] else "NOT CONFIRMED"
        print(f"   {state}: {data['address']} {data['kind']} {data['number']} requested {data['requested']}, "
              f"device reports {data['value']} via {data['confirmed_by']} in {data['latency']} s"
              + (f"; {data['error']}" if data["error"] else ""))

    async def cmd_set(self):
        address, number, value = parse_address(self.args.address), self.args.number, self.args.value
        controller = self.controller()
        if self.args.target == "curtain":
            statuses = {"open": CURTAIN_OPEN, "close": CURTAIN_CLOSE, "stop": CURTAIN_STOP}
            if value not in statuses:
                raise SystemExit("curtain value must be open, close or stop")
            result = await controller.set_curtain(address, number, statuses[value])
        elif self.args.target == "universal_switch":
            if value not in ("on", "off"):
                raise SystemExit("universal switch value must be on or off")
            result = await controller.set_universal_switch(address, number, value == "on")
        else:
            level = {"on": 100, "off": 0}.get(value)
            result = await controller.set_channel(address, number, int(value) if level is None else level)
        self.print_result(result)

    async def cmd_pulse(self):
        address, channel = parse_address(self.args.address), self.args.number
        controller = self.controller()
        result = await controller.pulse_channel(address, channel, self.args.level, self.args.seconds)
        self.print_result(result)
        print(f"   restoring level {result.previous} after {self.args.seconds} s ...")
        await asyncio.sleep(self.args.seconds + self.args.timeout + 0.5)
        print(f"   level now: {await controller.read_channel(address, channel)}")

    async def cmd_raw(self):
        payload = [int(value, 0) for value in self.args.payload]
        await self.send(parse_address(self.args.address), int(self.args.operate_code, 0), payload)
        await asyncio.sleep(self.args.seconds)


def decode_lines(source):
    """Decode hex UDP payloads, one per line (the last tab-separated field), e.g. from tshark."""
    helper = TelegramHelper()
    for line in source:
        fields = line.strip().split("\t")
        if not fields[-1]:
            continue
        try:
            data = bytes.fromhex(fields[-1].replace(":", ""))
        except ValueError:
            continue
        telegram = helper.build_telegram_from_udp_data(data, None)
        if telegram is None:
            print(f"   (not an HDL telegram or bad CRC: {fields[-1][:40]}...)")
            continue
        print_entry(describe(telegram))


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gateway", help="IP address of the HDL IP gateway")
    parser.add_argument("--port", type=int, default=6000)
    parser.add_argument("--timeout", type=float, default=1.5, help="seconds to wait for each reply")
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--log", type=pathlib.Path, help="append every telegram to this JSON Lines file")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("listen", help="print all bus traffic").add_argument("--seconds", type=float, default=30)
    commands.add_parser("remark", help="read device name (0x000E)").add_argument("address")
    commands.add_parser("channels", help="read channel count and levels (0x0033)").add_argument("address")
    channel_remarks = commands.add_parser("channel-remarks", help="read channel names (0xF00E)")
    channel_remarks.add_argument("address")
    channel_remarks.add_argument("--count", type=int, help="number of channels (default: read with 0x0033)")
    module = commands.add_parser("module", help="read device module description (0xE548)")
    module.add_argument("address", nargs="?", help="device address; broadcast when omitted")
    module.add_argument("--seconds", type=float, default=5, help="how long to collect replies")
    raw = commands.add_parser("raw", help="send any operate code")
    raw.add_argument("address")
    raw.add_argument("operate_code", help="e.g. 0xF00E")
    raw.add_argument("payload", nargs="*", help="payload bytes, e.g. 1 0x64")
    raw.add_argument("--seconds", type=float, default=3, help="how long to listen afterwards")
    commands.add_parser("decode", help="decode hex payloads from a file or - for stdin").add_argument("file")
    set_ = commands.add_parser("set", help="switch a channel, curtain or universal switch (real load!)")
    set_.add_argument("address")
    set_.add_argument("number", type=int, help="channel, curtain or switch number")
    set_.add_argument("value", help="on, off or 0-100; curtains: open, close, stop")
    set_.add_argument("--target", choices=["output", "curtain", "universal_switch"], default="output")
    set_.add_argument("--yes", action="store_true", help="do not ask before switching")
    pulse = commands.add_parser("pulse", help="turn a channel on for a moment, then restore it (real load!)")
    pulse.add_argument("address")
    pulse.add_argument("number", type=int, help="channel number")
    pulse.add_argument("--level", type=int, default=100)
    pulse.add_argument("--seconds", type=float, default=2)
    pulse.add_argument("--yes", action="store_true", help="do not ask before switching")
    scan = commands.add_parser("scan", help="run the full bus scan (read-only)")
    scan.add_argument("--rounds", type=int, default=4, help="search rounds (one finds ~87%% of devices)")
    scan.add_argument("--interval", type=float, default=10, help="seconds per search round")
    scan.add_argument("--no-mac", action="store_true", help="do not read MAC addresses")
    scan.add_argument("--no-names", action="store_true", help="do not read channel names")
    scan.add_argument("--json", type=pathlib.Path, help="save the result as JSON")
    scan.add_argument("--show-telegrams", action="store_true", help="print every telegram during the scan")
    return parser


async def run(args):
    probe = Probe(args)
    await probe.start()
    try:
        await getattr(probe, "cmd_" + args.command.replace("-", "_"))()
        # Give late replies a moment to arrive.
        await asyncio.sleep(0.5)
    finally:
        await probe.stop()


def main():
    args = build_parser().parse_args()
    if args.command == "decode":
        if args.file == "-":
            decode_lines(sys.stdin)
        else:
            with open(args.file, encoding="utf-8") as source:
                decode_lines(source)
        return
    if not args.gateway:
        raise SystemExit("--gateway is required")
    if args.command in ("set", "pulse") and not args.yes:
        answer = input(f"This switches a real load on {args.address}, {args.command} {args.number}. Continue? [y/N] ")
        if answer.strip().lower() not in ("y", "yes", "t", "taip"):
            raise SystemExit("Cancelled")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
