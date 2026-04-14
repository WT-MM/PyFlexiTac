"""Tests for FlexiTacSensor frame parsing and normalization."""

from __future__ import annotations

from collections import deque

import numpy as np
import pytest

import flexitac.sensor as sensor_mod
from flexitac import FlexiTacSensor


class FakeSerial:
    def __init__(self, *_: object, **__: object) -> None:
        self.is_open = True
        self._chunks: deque[bytes] = deque()

    def queue(self, data: bytes) -> None:
        self._chunks.append(data)

    def read(self, _size: int) -> bytes:
        return self._chunks.popleft() if self._chunks else b""

    def reset_input_buffer(self) -> None: ...
    def close(self) -> None:
        self.is_open = False


def _frame(arr: np.ndarray) -> bytes:
    return b"\xaa\x55" + arr.astype(np.uint8).tobytes()


def _patch_serial(monkeypatch: pytest.MonkeyPatch, fake: FakeSerial) -> None:
    monkeypatch.setattr(sensor_mod.serial, "Serial", lambda *a, **k: fake)


def test_read_returns_normalized_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeSerial()
    fake.queue(_frame(np.full((2, 2), 100, dtype=np.uint8)))
    fake.queue(_frame(np.full((2, 2), 100, dtype=np.uint8)))
    fake.queue(_frame(np.array([[150, 130], [110, 100]], dtype=np.uint8)))
    _patch_serial(monkeypatch, fake)

    sensor = FlexiTacSensor("/dev/fake", rows=2, cols=2, threshold=10.0, noise_scale=20.0, init_frames=2)
    frame = sensor.read()

    assert frame.seq == 0
    np.testing.assert_array_equal(frame.raw, [[150, 130], [110, 100]])
    np.testing.assert_allclose(frame.normalized, [[1.0, 0.5], [0.0, 0.0]], atol=1e-5)


def test_parser_handles_split_marker_and_garbage(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeSerial()
    # Calibration frames (preceded by garbage and split markers).
    fake.queue(b"junk\xaa")
    fake.queue(b"\x55\x01\x02\x03\x04")
    fake.queue(_frame(np.array([[1, 2], [3, 4]], dtype=np.uint8)))
    fake.queue(_frame(np.array([[10, 20], [30, 40]], dtype=np.uint8)))
    _patch_serial(monkeypatch, fake)

    sensor = FlexiTacSensor("/dev/fake", rows=2, cols=2, init_frames=2, threshold=1.0, noise_scale=1.0)
    sensor.calibrate()
    frame = sensor.read()
    assert frame.raw.shape == (2, 2)


def test_iter_yields_sequential_frames(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeSerial()
    for _ in range(4):
        fake.queue(_frame(np.full((1, 2), 100, dtype=np.uint8)))
    _patch_serial(monkeypatch, fake)

    sensor = FlexiTacSensor("/dev/fake", rows=1, cols=2, init_frames=2, threshold=1.0, noise_scale=1.0)
    frames = [next(iter(sensor)) for _ in range(2)]
    assert [f.seq for f in frames] == [0, 1]
