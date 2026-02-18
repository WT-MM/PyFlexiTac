"""Tests for firmware macro validation and rendering."""

from __future__ import annotations

import pytest

from flexitac.firmware.profiles import get_profile
from flexitac.firmware.render import FirmwareRenderError, parse_set_overrides, render_template, resolve_macros


def test_parse_set_overrides_valid() -> None:
    parsed = parse_set_overrides(["ROW_COUNT=16", "COLUMN_COUNT=32"])
    assert parsed == {"ROW_COUNT": "16", "COLUMN_COUNT": "32"}


def test_parse_set_overrides_rejects_invalid_format() -> None:
    with pytest.raises(FirmwareRenderError):
        parse_set_overrides(["ROW_COUNT:16"])


def test_resolve_macros_profile_and_common_flags() -> None:
    profile = get_profile("16x32")
    macros = resolve_macros(
        profile=profile,
        common_overrides={"rows": "12", "cols": "24", "baud": "1000000"},
        set_overrides={},
        expert=False,
    )

    assert macros["ROW_COUNT"] == "12"
    assert macros["COLUMN_COUNT"] == "24"
    assert macros["BAUD_RATE"] == "1000000"


def test_resolve_macros_rejects_unallowlisted_set_without_expert() -> None:
    profile = get_profile("16x16")
    with pytest.raises(FirmwareRenderError):
        resolve_macros(
            profile=profile,
            common_overrides={},
            set_overrides={"UNSAFE_MACRO": "1"},
            expert=False,
        )


def test_resolve_macros_allows_custom_set_with_expert() -> None:
    profile = get_profile("16x16")
    macros = resolve_macros(
        profile=profile,
        common_overrides={},
        set_overrides={"UNSAFE_MACRO": "1"},
        expert=True,
    )
    assert macros["UNSAFE_MACRO"] == "1"


def test_validate_pin_token_rejects_invalid_value() -> None:
    profile = get_profile("16x16")
    with pytest.raises(FirmwareRenderError):
        resolve_macros(
            profile=profile,
            common_overrides={"pin_adc_input": "GPIO-2"},
            set_overrides={},
            expert=False,
        )


def test_render_template_replaces_macros() -> None:
    template = "#define ROW_COUNT 16\n#define COLUMN_COUNT 32\n"
    rendered = render_template(template, {"ROW_COUNT": "8", "COLUMN_COUNT": "64"})
    assert "#define ROW_COUNT 8" in rendered
    assert "#define COLUMN_COUNT 64" in rendered
