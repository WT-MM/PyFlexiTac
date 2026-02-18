"""Tests for board selection and flash command behavior."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import flexitac.flash
from flexitac.flash import BoardCandidate, FlashError, flash_firmware, select_board


def test_select_board_uses_unique_detected_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    candidates = [BoardCandidate(port="/dev/ttyUSB0", fqbn="arduino:avr:uno", name="Uno")]

    def _list_boards(*, verbose: bool) -> list[BoardCandidate]:
        del verbose
        return candidates

    monkeypatch.setattr(flexitac.flash, "list_boards", _list_boards)

    port, fqbn = select_board(port=None, fqbn=None, expert=False, verbose=False)
    assert port == "/dev/ttyUSB0"
    assert fqbn == "arduino:avr:uno"


def test_select_board_rejects_ambiguous_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    candidates = [
        BoardCandidate(port="/dev/ttyUSB0", fqbn="arduino:avr:uno", name="Uno"),
        BoardCandidate(port="/dev/ttyUSB1", fqbn="arduino:avr:nano", name="Nano"),
    ]

    def _list_boards(*, verbose: bool) -> list[BoardCandidate]:
        del verbose
        return candidates

    monkeypatch.setattr(flexitac.flash, "list_boards", _list_boards)

    with pytest.raises(FlashError, match="flexitac.scan"):
        select_board(port=None, fqbn=None, expert=False, verbose=False)


def test_select_board_rejects_unsupported_fqbn_without_expert() -> None:
    with pytest.raises(FlashError):
        select_board(port="/dev/ttyUSB0", fqbn="esp32:esp32:esp32", expert=False, verbose=False)


def test_flash_firmware_dry_run_emits_rendered_sketch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    emitted = tmp_path / "generated.ino"

    def _select_board(*, port: str | None, fqbn: str | None, expert: bool, verbose: bool) -> tuple[str, str]:
        del port, fqbn, expert, verbose
        return "/dev/ttyUSB0", "arduino:avr:uno"

    monkeypatch.setattr(flexitac.flash, "select_board", _select_board)
    monkeypatch.setattr(flexitac.flash, "ensure_core_installed", lambda fqbn: None)

    calls: list[list[str]] = []

    def _run_command(
        cmd: list[str],
        *,
        verbose: bool,
        capture_output: bool = True,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        del verbose, check
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(flexitac.flash, "_run_command", _run_command)

    result = flash_firmware(
        profile_name="16x32",
        port=None,
        fqbn=None,
        board_options=["cpu=atmega328p"],
        rows=16,
        cols=24,
        baud=1_000_000,
        pin_adc_input=None,
        pin_shift_register_data=None,
        pin_shift_register_clock=None,
        pin_mux_channel_0=None,
        pin_mux_channel_1=None,
        pin_mux_channel_2=None,
        pin_mux_channel_3=None,
        pin_mux_inhibit_0=None,
        pin_mux_inhibit_1=None,
        set_overrides=["ROWS_PER_MUX=8", "MUX_COUNT=2"],
        print_config=False,
        emit_sketch=str(emitted),
        dry_run=True,
        expert=False,
        verbose=False,
    )

    assert result.dry_run is True
    assert result.port == "/dev/ttyUSB0"
    assert result.fqbn == "arduino:avr:uno"
    assert "--board-options cpu=atmega328p" in result.compile_command
    assert emitted.exists()

    content = emitted.read_text(encoding="utf-8")
    assert "#define COLUMN_COUNT              24" in content
    assert "#define BAUD_RATE                 1000000" in content
    assert "#define ROWS_PER_MUX              8" in content
    assert "#define MUX_COUNT                 2" in content
    assert calls == []


def test_flash_firmware_requires_installed_core(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flexitac.flash, "list_installed_cores", lambda: {"arduino:samd"})

    with pytest.raises(FlashError):
        flexitac.flash.ensure_core_installed("arduino:avr:uno")
