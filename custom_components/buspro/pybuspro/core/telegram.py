import json
from ..helpers.enums import DeviceType


# DTO class
class Telegram:
    def __init__(self):
        self.udp_address = None
        self.payload = None
        self.operate_code = None
        # Raw 2-byte codes as received; set even when the enums do not know the value.
        self.operate_code_raw = None
        self.source_device_type = DeviceType.PyBusPro
        self.source_device_type_raw = None
        self.udp_data = None
        self.source_address = None
        self.target_address = None
        self.crc = None

    def __str__(self):
        """Return object as readable string."""

        return json.JSONEncoder().encode([
            {"name": "source_address", "value": self.source_address},
            {"name": "source_device_type", "value": str(self.source_device_type)},
            {"name": "source_device_type_raw", "value": self._hex(self.source_device_type_raw)},
            {"name": "target_address", "value": self.target_address},
            {"name": "operate_code", "value": str(self.operate_code)},
            {"name": "operate_code_raw", "value": self._hex(self.operate_code_raw)},
            {"name": "payload", "value": self.payload},
            {"name": "udp_address", "value": self.udp_address},
            {"name": "udp_data", "value": str(self.udp_data)},
            {"name": "crc", "value": str(self.crc)},
        ])

    @staticmethod
    def _hex(value):
        return None if value is None else "0x" + bytes(value).hex().upper()

    def __eq__(self, other):
        """Equal operator."""
        return self.__dict__ == other.__dict__
