from .enums import DeviceType, OperateCode


class Generics:

    @staticmethod
    def calculate_minutes_seconds(seconds):
        return divmod(seconds, 60)  # (minutes, seconds)

    @staticmethod
    def integer_list_to_hex(list_):
        hex_ = bytearray(list_)
        return hex_

    @staticmethod
    def hex_to_integer_list(hex_value):
        list_of_integer = []
        for string in hex_value:
            list_of_integer.append(string)
        return list_of_integer

    @staticmethod
    def operate_code_to_bytes(operate_code):
        """Return a 2-byte operate code from an OperateCode, bytes, [hi, lo] list or int."""
        if isinstance(operate_code, OperateCode):
            operate_code = operate_code.value
        if isinstance(operate_code, int):
            if not 0 <= operate_code <= 0xFFFF:
                raise ValueError(f"operate code out of range: {operate_code}")
            return operate_code.to_bytes(2, "big")
        operate_code = bytes(operate_code)
        if len(operate_code) != 2:
            raise ValueError(f"operate code must be 2 bytes, got {list(operate_code)}")
        return operate_code

    @staticmethod
    def enum_has_value(enum, value):
        return any(value == item.value for item in enum)

    def get_enum_value(self, enum, value):
        if enum == DeviceType:
            if self.enum_has_value(enum, value):
                return DeviceType(value)
            else:
                return None
        elif enum == OperateCode:
            if self.enum_has_value(enum, value):
                return OperateCode(value)
            else:
                return None
