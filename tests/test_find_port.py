"""Tests for the unplug-based port finder."""

from __future__ import annotations

import pytest

import flexitac.find_port as find_port_mod
from flexitac.find_port import find_port


def _patch_ports(monkeypatch: pytest.MonkeyPatch, snapshots: list[set[str]]) -> None:
    iterator = iter(snapshots)
    monkeypatch.setattr(find_port_mod, "list_serial_ports", lambda: next(iterator))
    monkeypatch.setattr("builtins.input", lambda _prompt="": "")
    monkeypatch.setattr(find_port_mod.time, "sleep", lambda _s: None)


def test_find_port_returns_unique_disappearance(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_ports(monkeypatch, [{"/dev/ttyUSB0", "/dev/ttyACM0"}, {"/dev/ttyACM0"}])
    assert find_port() == "/dev/ttyUSB0"


def test_find_port_errors_on_no_change(monkeypatch: pytest.MonkeyPatch) -> None:
    ports = {"/dev/ttyUSB0"}
    _patch_ports(monkeypatch, [ports, ports])
    with pytest.raises(OSError, match="No port"):
        find_port()


def test_find_port_errors_on_multiple_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_ports(monkeypatch, [{"/dev/a", "/dev/b", "/dev/c"}, {"/dev/c"}])
    with pytest.raises(OSError, match="Multiple"):
        find_port()
