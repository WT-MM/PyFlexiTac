"""Tests for flash CLI helpers."""

from __future__ import annotations

import subprocess

import pytest

import flexitac.flash as flash_mod
from flexitac.flash import FlashError, detect_board, render_template


def test_render_template_replaces_known_macros() -> None:
    rendered = render_template(rows=8, cols=24, baud=1_000_000)
    assert "#define ROW_COUNT                 8" in rendered
    assert "#define COLUMN_COUNT              24" in rendered
    assert "#define BAUD_RATE                 1000000" in rendered


def test_detect_board_picks_unique_match(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = (
        "Port         Protocol Type              Board Name FQBN              Core\n"
        "/dev/ttyUSB0 serial   Serial Port (USB) Arduino Uno arduino:avr:uno   arduino:avr\n"
    )
    monkeypatch.setattr(
        flash_mod,
        "_run",
        lambda cmd, **_: subprocess.CompletedProcess(cmd, 0, stdout=payload, stderr=""),
    )
    assert detect_board() == ("/dev/ttyUSB0", "arduino:avr:uno")


def test_detect_board_errors_on_no_boards(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        flash_mod,
        "_run",
        lambda cmd, **_: subprocess.CompletedProcess(cmd, 0, stdout="Port Protocol\n", stderr=""),
    )
    with pytest.raises(FlashError, match="no Arduino"):
        detect_board()


def test_detect_board_errors_on_multiple(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = (
        "Port         Protocol Type FQBN              Core\n"
        "/dev/ttyUSB0 serial   USB  arduino:avr:uno   arduino:avr\n"
        "/dev/ttyUSB1 serial   USB  arduino:avr:nano  arduino:avr\n"
    )
    monkeypatch.setattr(
        flash_mod,
        "_run",
        lambda cmd, **_: subprocess.CompletedProcess(cmd, 0, stdout=payload, stderr=""),
    )
    with pytest.raises(FlashError, match="multiple"):
        detect_board()
