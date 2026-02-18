"""Tests for scan diagnostics CLI."""

from __future__ import annotations

import pytest

import flexitac.scan
from flexitac.flash import BoardCandidate


def test_scan_recommends_flash_command_for_single_board(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(flexitac.scan, "ensure_arduino_cli_available", lambda verbose: "arduino-cli Version: 1.0.0")
    monkeypatch.setattr(
        flexitac.scan,
        "list_boards",
        lambda verbose: [BoardCandidate(port="/dev/ttyUSB0", fqbn="arduino:avr:uno", name="Uno")],
    )
    monkeypatch.setattr(flexitac.scan, "list_installed_cores", lambda: {"arduino:avr"})

    exit_code = flexitac.scan.main([])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "recommended flash command" in captured.err
    assert "uv run python -m flexitac.flash" in captured.err


def test_scan_reports_no_boards(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(flexitac.scan, "ensure_arduino_cli_available", lambda verbose: "arduino-cli Version: 1.0.0")
    monkeypatch.setattr(flexitac.scan, "list_boards", lambda verbose: [])
    monkeypatch.setattr(flexitac.scan, "list_installed_cores", lambda: {"arduino:avr"})

    exit_code = flexitac.scan.main([])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "no boards detected" in captured.err
    assert "uv run python -m flexitac.flash" in captured.err
