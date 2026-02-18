"""Tests for the high-level sensor runtime API."""

from __future__ import annotations

from collections import deque

import numpy as np
import pytest

import flexitac.sensor
from flexitac import FlexiTacSensor, ProcessingConfig


class FakeSerial:
    """Minimal fake serial class for deterministic sensor tests."""

    def __init__(self, port: str, baud: int, timeout: float) -> None:
        del port, baud, timeout
        self.is_open = True
        self._chunks: deque[bytes] = deque()

    def queue(self, chunk: bytes) -> None:
        self._chunks.append(chunk)

    def read(self, size: int) -> bytes:
        del size
        if not self._chunks:
            return b""
        return self._chunks.popleft()

    def reset_input_buffer(self) -> None:
        return None

    def reset_output_buffer(self) -> None:
        return None

    def close(self) -> None:
        self.is_open = False


def _encode_frame(frame: np.ndarray) -> bytes:
    return b"\xaa\x55" + frame.astype(np.uint8).tobytes()


def test_sensor_read_frame_returns_structured_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_serial = FakeSerial(port="/dev/fake", baud=2_000_000, timeout=0.05)

    calibration_a = np.full((2, 2), 100, dtype=np.uint8)
    calibration_b = np.full((2, 2), 100, dtype=np.uint8)
    runtime_frame = np.array([[150, 130], [110, 100]], dtype=np.uint8)

    fake_serial.queue(_encode_frame(calibration_a))
    fake_serial.queue(_encode_frame(calibration_b))
    fake_serial.queue(_encode_frame(runtime_frame))

    def _serial_ctor(port: str, baud: int, timeout: float) -> FakeSerial:
        del port, baud, timeout
        return fake_serial

    monkeypatch.setattr(flexitac.sensor.serial, "Serial", _serial_ctor)

    sensor = FlexiTacSensor(
        port="/dev/fake",
        rows=2,
        cols=2,
        processing=ProcessingConfig(threshold=10.0, noise_scale=20.0, init_frames=2),
    )

    frame = sensor.read_frame()

    assert frame.seq == 0
    assert frame.rows == 2
    assert frame.cols == 2
    np.testing.assert_array_equal(frame.raw, runtime_frame)
    np.testing.assert_array_equal(frame.calibrated, np.array([[40.0, 20.0], [0.0, 0.0]], dtype=np.float32))
    np.testing.assert_allclose(frame.normalized, np.array([[1.0, 0.5], [0.0, 0.0]], dtype=np.float32), atol=1e-5)


def test_sensor_iter_frames_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_serial = FakeSerial(port="/dev/fake", baud=2_000_000, timeout=0.05)

    for _ in range(2):
        fake_serial.queue(_encode_frame(np.full((1, 2), 100, dtype=np.uint8)))
    fake_serial.queue(_encode_frame(np.array([[150, 150]], dtype=np.uint8)))
    fake_serial.queue(_encode_frame(np.array([[160, 160]], dtype=np.uint8)))

    def _serial_ctor(port: str, baud: int, timeout: float) -> FakeSerial:
        del port, baud, timeout
        return fake_serial

    monkeypatch.setattr(flexitac.sensor.serial, "Serial", _serial_ctor)

    sensor = FlexiTacSensor(
        port="/dev/fake",
        rows=1,
        cols=2,
        processing=ProcessingConfig(threshold=10.0, noise_scale=20.0, init_frames=2),
    )

    frames = list(sensor.iter_frames(limit=2))
    assert len(frames) == 2
    assert [frame.seq for frame in frames] == [0, 1]
