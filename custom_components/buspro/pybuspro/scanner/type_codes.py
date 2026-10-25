"""Device types that the scanner cannot classify from the bus alone.

Most devices describe themselves (0xE549) or answer ReadStatusOfChannels, so this
table only covers types that do neither. Entries come from this repository's enums
and from captures of two installations (docs/protocol-captures/2026-10-25-analysis.md).
"""

OUTPUT_MODULE = "output_module"
CURTAIN_MODULE = "curtain_module"
DRY_CONTACT_MODULE = "dry_contact_module"
FLOOR_HEATING = "floor_heating"
SENSOR = "sensor"
PANEL = "panel"
LOGIC = "logic"
GATEWAY = "gateway"
SOFTWARE = "software"
UNKNOWN = "unknown"

# PyBusPro, SmartHDLTest, Setup Tool. Logic modules also send some telegrams as 0xFFFE,
# so a device is software only if it never uses any other type.
SOFTWARE_TYPES = frozenset({0xFFFC, 0xFFFD, 0xFFFE})

# type code -> (category, description)
KNOWN_TYPES = {
    0x0018: (SENSOR, "PIR sensor (old)"),
    0x0077: (DRY_CONTACT_MODULE, "SB-DRY-4Z dry contact module"),
    0x0086: (PANEL, "DLP panel"),  # Also used by other products; devices that answer decide.
    0x0095: (PANEL, "DLP panel"),
    0x009C: (PANEL, "DLP panel v2"),
    0x012B: (PANEL, "SB-WS8M 8-key panel"),
    0x0134: (SENSOR, "CMS 12-in-1 sensor"),
    0x0135: (SENSOR, "CMS 8-in-1 sensor"),
    0x0148: (SENSOR, "sensor"),
    0x014A: (SENSOR, "sensors-in-one"),
    # These usually describe themselves, but not always within the discovery window.
    0x0149: (SENSOR, "motion and illuminance sensor with dry contacts"),
    0x0150: (SENSOR, "motion and illuminance sensor with dry contacts"),
    0x0155: (SENSOR, "motion and illuminance sensor"),
    0x0156: (SENSOR, "motion and illuminance sensor"),
    0x0185: (SENSOR, "motion and illuminance sensor"),  # reports big=16 functions
    0x0453: (LOGIC, "logic module"),
    0x0BE9: (LOGIC, "SB-DN-SEC250K security module"),
    0x2580: (GATEWAY, "IP module"),
}

# Types that never answered 0xE548 in the captures, so the scan does not ask them directly.
NO_MODULE_REPLY_TYPES = frozenset({0x0018, 0x0086, 0x0095, 0x0148, 0x014A, 0x0453, 0x2580})

# Operate codes that identify a device which neither describes itself nor is in KNOWN_TYPES.
SENSOR_OPERATE_CODES = frozenset({0x1605, 0x1630, 0x1646, 0x1647, 0xDB01})
PANEL_OPERATE_CODES = frozenset({0x1945, 0x1947, 0x1949})
LOGIC_OPERATE_CODES = frozenset({0xDA44})
