"""Helpers to validate and parse Buspro address strings.

Why this exists:
- In YAML, an unquoted value like 4.190 is parsed as a number (float).
- Once it becomes a float, Python loses the trailing zero (4.190 -> 4.19),
  and the integration ends up using the wrong device id (19 instead of 190).

To avoid silent misconfiguration, we require addresses to be provided as
quoted strings (e.g. "4.190").
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol


def validate_buspro_address_str(value: Any) -> str:
    """Validate a Buspro address supplied via YAML.

    The address must be a *string* containing digit segments separated by dots,
    e.g. "4.190" or "4.190.9".

    Note: We intentionally reject non-strings (int/float) because YAML numeric
    parsing irreversibly removes significant formatting like trailing zeros.
    """

    if not isinstance(value, str):
        raise vol.Invalid(
            "buspro address must be a quoted string (e.g. '4.190'); "
            "unquoted 4.190 is parsed as a number and becomes 4.19"
        )

    address = value.strip()
    if not address:
        raise vol.Invalid("buspro address cannot be empty")

    if "." not in address:
        raise vol.Invalid("buspro address must contain '.' (e.g. '4.190')")

    parts = address.split(".")
    if any(part == "" for part in parts):
        raise vol.Invalid("buspro address must not contain empty segments")
    if any(not part.isdigit() for part in parts):
        raise vol.Invalid("buspro address must contain only digits and dots")

    return address


def validate_optional_buspro_address_str(value: Any) -> str:
    """Like validate_buspro_address_str, but allows empty string."""

    if value in (None, ""):
        return ""
    return validate_buspro_address_str(value)
