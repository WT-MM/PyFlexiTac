"""Firmware profile defaults and supported board metadata."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FirmwareProfile:
    """A named configuration profile for firmware macro defaults."""

    name: str
    description: str
    macros: dict[str, str]


SUPPORTED_AVR_FQBNS: tuple[str, ...] = (
    "arduino:avr:uno",
    "arduino:avr:nano",
    "arduino:avr:mega",
    "arduino:avr:leonardo",
    "arduino:avr:micro",
)


FIRMWARE_PROFILES: dict[str, FirmwareProfile] = {
    "16x16": FirmwareProfile(
        name="16x16",
        description="16 rows x 16 columns tactile grid using binary framed output",
        macros={
            "BAUD_RATE": "2000000",
            "ROW_COUNT": "16",
            "COLUMN_COUNT": "16",
            "PIN_ADC_INPUT": "A0",
            "PIN_SHIFT_REGISTER_DATA": "2",
            "PIN_SHIFT_REGISTER_CLOCK": "3",
            "PIN_MUX_CHANNEL_0": "4",
            "PIN_MUX_CHANNEL_1": "5",
            "PIN_MUX_CHANNEL_2": "6",
            "PIN_MUX_CHANNEL_3": "7",
            "PIN_MUX_INHIBIT_0": "8",
            "PIN_MUX_INHIBIT_1": "9",
            "ROWS_PER_MUX": "16",
            "MUX_COUNT": "1",
            "CHANNEL_PINS_PER_MUX": "4",
            "START_MARKER_0": "0xAA",
            "START_MARKER_1": "0x55",
        },
    ),
    "16x32": FirmwareProfile(
        name="16x32",
        description="16 rows x 32 columns tactile grid using binary framed output",
        macros={
            "BAUD_RATE": "2000000",
            "ROW_COUNT": "16",
            "COLUMN_COUNT": "32",
            "PIN_ADC_INPUT": "A0",
            "PIN_SHIFT_REGISTER_DATA": "2",
            "PIN_SHIFT_REGISTER_CLOCK": "3",
            "PIN_MUX_CHANNEL_0": "4",
            "PIN_MUX_CHANNEL_1": "5",
            "PIN_MUX_CHANNEL_2": "6",
            "PIN_MUX_CHANNEL_3": "7",
            "PIN_MUX_INHIBIT_0": "8",
            "PIN_MUX_INHIBIT_1": "9",
            "ROWS_PER_MUX": "16",
            "MUX_COUNT": "1",
            "CHANNEL_PINS_PER_MUX": "4",
            "START_MARKER_0": "0xAA",
            "START_MARKER_1": "0x55",
        },
    ),
}


def get_profile(name: str) -> FirmwareProfile:
    """Return a firmware profile by name."""
    try:
        return FIRMWARE_PROFILES[name]
    except KeyError as exc:
        available = ", ".join(sorted(FIRMWARE_PROFILES))
        msg = f"unknown profile '{name}'. Available profiles: {available}"
        raise ValueError(msg) from exc


def profile_names() -> list[str]:
    """Return available profile names."""
    return sorted(FIRMWARE_PROFILES)
