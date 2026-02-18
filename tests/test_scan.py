"""Tests for scan diagnostics CLI."""

from __future__ import annotations

import logging

import pytest

import flexitac.scan
from flexitac.flash import DetectedPort


def test_scan_recommends_flash_command_for_single_board(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(flexitac.scan, "ensure_arduino_cli_available", lambda verbose: "arduino-cli Version: 1.0.0")
    monkeypatch.setattr(
        flexitac.scan,
        "list_detected_ports",
        lambda verbose: [DetectedPort(port="/dev/ttyUSB0", fqbn="arduino:avr:uno", name="Uno")],
    )
    monkeypatch.setattr(flexitac.scan, "list_installed_cores", lambda: {"arduino:avr"})

    with caplog.at_level(logging.INFO, logger="flexitac"):
        exit_code = flexitac.scan.main([])

    assert exit_code == 0
    assert "recommended flash command" in caplog.text
    assert "uv run python -m flexitac.flash" in caplog.text


def test_scan_reports_no_boards(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(flexitac.scan, "ensure_arduino_cli_available", lambda verbose: "arduino-cli Version: 1.0.0")
    monkeypatch.setattr(flexitac.scan, "list_detected_ports", lambda verbose: [])
    monkeypatch.setattr(flexitac.scan, "list_installed_cores", lambda: {"arduino:avr"})

    with caplog.at_level(logging.INFO, logger="flexitac"):
        exit_code = flexitac.scan.main([])

    assert exit_code == 1
    assert "no serial ports detected" in caplog.text
    assert "uv run python -m flexitac.flash" in caplog.text


def test_scan_reports_unknown_ports(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(flexitac.scan, "ensure_arduino_cli_available", lambda verbose: "arduino-cli Version: 1.0.0")
    monkeypatch.setattr(
        flexitac.scan,
        "list_detected_ports",
        lambda verbose: [
            DetectedPort(port="/dev/ttyUSB0", fqbn=None, name="Unknown"),
            DetectedPort(port="/dev/ttyACM0", fqbn=None, name="Unknown"),
        ],
    )
    monkeypatch.setattr(flexitac.scan, "list_installed_cores", lambda: set())

    with caplog.at_level(logging.INFO, logger="flexitac"):
        exit_code = flexitac.scan.main([])

    assert exit_code == 1
    assert "serial ports were detected" in caplog.text
    assert "/dev/ttyUSB0" in caplog.text
    assert "core install arduino:avr" in caplog.text
