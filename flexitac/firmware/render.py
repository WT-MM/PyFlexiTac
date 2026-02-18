"""Render and validate generated Arduino sketch files."""

from __future__ import annotations

import re
from pathlib import Path

from flexitac.firmware.profiles import FirmwareProfile

DEFINE_RE = re.compile(r"^(\s*#define\s+)([A-Z0-9_]+)(\s+)([^\s].*)$")
MACRO_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
PIN_TOKEN_RE = re.compile(r"^(A\d+|\d+)$")

COMMON_OVERRIDE_MACROS: dict[str, str] = {
    "rows": "ROW_COUNT",
    "cols": "COLUMN_COUNT",
    "baud": "BAUD_RATE",
    "pin_adc_input": "PIN_ADC_INPUT",
    "pin_shift_register_data": "PIN_SHIFT_REGISTER_DATA",
    "pin_shift_register_clock": "PIN_SHIFT_REGISTER_CLOCK",
    "pin_mux_channel_0": "PIN_MUX_CHANNEL_0",
    "pin_mux_channel_1": "PIN_MUX_CHANNEL_1",
    "pin_mux_channel_2": "PIN_MUX_CHANNEL_2",
    "pin_mux_channel_3": "PIN_MUX_CHANNEL_3",
    "pin_mux_inhibit_0": "PIN_MUX_INHIBIT_0",
    "pin_mux_inhibit_1": "PIN_MUX_INHIBIT_1",
}

ALLOWLISTED_SET_MACROS: set[str] = {
    "BAUD_RATE",
    "ROW_COUNT",
    "COLUMN_COUNT",
    "PIN_ADC_INPUT",
    "PIN_SHIFT_REGISTER_DATA",
    "PIN_SHIFT_REGISTER_CLOCK",
    "PIN_MUX_CHANNEL_0",
    "PIN_MUX_CHANNEL_1",
    "PIN_MUX_CHANNEL_2",
    "PIN_MUX_CHANNEL_3",
    "PIN_MUX_INHIBIT_0",
    "PIN_MUX_INHIBIT_1",
    "ROWS_PER_MUX",
    "MUX_COUNT",
    "CHANNEL_PINS_PER_MUX",
    "START_MARKER_0",
    "START_MARKER_1",
}


class FirmwareRenderError(RuntimeError):
    """Raised when firmware configuration or rendering fails."""


def parse_set_overrides(overrides: list[str]) -> dict[str, str]:
    """Parse repeated NAME=VALUE --set arguments into a dictionary."""
    parsed: dict[str, str] = {}
    for item in overrides:
        if "=" not in item:
            msg = f"invalid --set '{item}'. Expected NAME=VALUE"
            raise FirmwareRenderError(msg)
        macro_name, value = item.split("=", 1)
        macro_name = macro_name.strip()
        value = value.strip()
        if not macro_name or not value:
            msg = f"invalid --set '{item}'. Expected NAME=VALUE"
            raise FirmwareRenderError(msg)
        if not MACRO_NAME_RE.fullmatch(macro_name):
            msg = f"invalid macro name '{macro_name}'. Use uppercase letters, numbers, and underscores"
            raise FirmwareRenderError(msg)
        parsed[macro_name] = value
    return parsed


def resolve_macros(
    *,
    profile: FirmwareProfile,
    common_overrides: dict[str, str],
    set_overrides: dict[str, str],
    expert: bool,
) -> dict[str, str]:
    """Layer profile defaults and user overrides into final macro values."""
    macros = dict(profile.macros)

    for key, value in common_overrides.items():
        macro_name = COMMON_OVERRIDE_MACROS[key]
        macros[macro_name] = value

    if not expert:
        for macro_name in set_overrides:
            if macro_name not in ALLOWLISTED_SET_MACROS:
                msg = (
                    f"macro '{macro_name}' is not allowed without --expert. "
                    "Use one of the first-class flags or add --expert."
                )
                raise FirmwareRenderError(msg)

    macros.update(set_overrides)
    validate_macros(macros)
    return macros


def validate_macros(macros: dict[str, str]) -> None:
    """Validate configured macro values before rendering firmware."""
    row_count = _require_int(macros, "ROW_COUNT")
    column_count = _require_int(macros, "COLUMN_COUNT")
    baud_rate = _require_int(macros, "BAUD_RATE")
    rows_per_mux = _require_int(macros, "ROWS_PER_MUX")
    mux_count = _require_int(macros, "MUX_COUNT")
    channel_pins = _require_int(macros, "CHANNEL_PINS_PER_MUX")
    marker_0 = _require_int(macros, "START_MARKER_0")
    marker_1 = _require_int(macros, "START_MARKER_1")

    if not 1 <= row_count <= 16:
        msg = "ROW_COUNT must be between 1 and 16"
        raise FirmwareRenderError(msg)
    if not 1 <= column_count <= 64:
        msg = "COLUMN_COUNT must be between 1 and 64"
        raise FirmwareRenderError(msg)
    if not 9_600 <= baud_rate <= 4_000_000:
        msg = "BAUD_RATE must be between 9600 and 4000000"
        raise FirmwareRenderError(msg)
    if rows_per_mux <= 0 or mux_count <= 0:
        msg = "ROWS_PER_MUX and MUX_COUNT must both be > 0"
        raise FirmwareRenderError(msg)
    if row_count > rows_per_mux * mux_count:
        msg = "ROW_COUNT exceeds ROWS_PER_MUX * MUX_COUNT"
        raise FirmwareRenderError(msg)
    if not 1 <= channel_pins <= 4:
        msg = "CHANNEL_PINS_PER_MUX must be between 1 and 4"
        raise FirmwareRenderError(msg)
    if not 0 <= marker_0 <= 255 or not 0 <= marker_1 <= 255:
        msg = "START_MARKER_0 and START_MARKER_1 must be byte values between 0 and 255"
        raise FirmwareRenderError(msg)

    pin_macros = [
        "PIN_ADC_INPUT",
        "PIN_SHIFT_REGISTER_DATA",
        "PIN_SHIFT_REGISTER_CLOCK",
        "PIN_MUX_CHANNEL_0",
        "PIN_MUX_CHANNEL_1",
        "PIN_MUX_CHANNEL_2",
        "PIN_MUX_CHANNEL_3",
        "PIN_MUX_INHIBIT_0",
        "PIN_MUX_INHIBIT_1",
    ]

    for macro_name in pin_macros:
        pin_value = macros.get(macro_name)
        if pin_value is None:
            msg = f"missing required pin macro '{macro_name}'"
            raise FirmwareRenderError(msg)
        if not PIN_TOKEN_RE.fullmatch(pin_value):
            msg = f"invalid pin token for {macro_name}: '{pin_value}'. Use values like A0 or 12"
            raise FirmwareRenderError(msg)


def render_template(template_text: str, macros: dict[str, str]) -> str:
    """Render template text by replacing configured #define values."""
    remaining = set(macros)
    rendered_lines: list[str] = []

    for line in template_text.splitlines():
        match = DEFINE_RE.match(line)
        if match is None:
            rendered_lines.append(line)
            continue

        prefix, macro_name, spacing, _existing = match.groups()
        if macro_name in macros:
            rendered_lines.append(f"{prefix}{macro_name}{spacing}{macros[macro_name]}")
            remaining.discard(macro_name)
        else:
            rendered_lines.append(line)

    if remaining:
        missing = ", ".join(sorted(remaining))
        msg = f"template is missing expected #define macros: {missing}"
        raise FirmwareRenderError(msg)

    return "\n".join(rendered_lines) + "\n"


def render_template_to_file(*, template_path: Path, output_path: Path, macros: dict[str, str]) -> str:
    """Render a template .ino file to a destination path."""
    template_text = template_path.read_text(encoding="utf-8")
    rendered_text = render_template(template_text, macros)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered_text, encoding="utf-8")
    return rendered_text


def _require_int(macros: dict[str, str], name: str) -> int:
    value = macros.get(name)
    if value is None:
        msg = f"missing required macro '{name}'"
        raise FirmwareRenderError(msg)

    parsed = _parse_int_like(value)
    if parsed is None:
        msg = f"macro {name} must be an integer-like value, got '{value}'"
        raise FirmwareRenderError(msg)
    return parsed


def _parse_int_like(value: str) -> int | None:
    try:
        return int(value, 0)
    except ValueError:
        return None
