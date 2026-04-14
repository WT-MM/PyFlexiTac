"""Read framed tactile data from a FlexiTac sensor over serial.

Wire protocol per frame: ``0xAA 0x55`` followed by ``rows * cols`` uint8 bytes.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np
import serial
from numpy.typing import NDArray

MARKER = b"\xaa\x55"


@dataclass(frozen=True)
class FlexiTacFrame:
    """One tactile frame in raw and processed form."""

    seq: int
    timestamp_s: float
    raw: NDArray[np.uint8]
    normalized: NDArray[np.float32]


class FlexiTacSensor:
    """Blocking serial reader for a FlexiTac sensor."""

    def __init__(
        self,
        port: str,
        *,
        rows: int = 12,
        cols: int = 32,
        baud: int = 2_000_000,
        threshold: float = 25.0,
        noise_scale: float = 30.0,
        init_frames: int = 30,
        read_timeout_s: float = 5.0,
        baseline: NDArray[np.float32] | float | None = None,
    ) -> None:
        """Initialize a FlexiTac sensor.

        Args:
            port: Serial device path (e.g. ``/dev/ttyUSB0``).
            rows: Number of tactile rows (default 12).
            cols: Number of tactile columns (default 32).
            baud: Serial baud rate matching the flashed firmware (default 2_000_000).
            threshold: Contact-detection threshold in ADC counts above baseline.
            noise_scale: Divisor used to normalize readings below ``threshold``.
            init_frames: Number of frames sampled during ``calibrate()`` (default 30).
                Higher values give a more robust baseline at the cost of startup time.
            read_timeout_s: Maximum time ``read()`` will wait for a full frame.
            baseline: If provided, skips auto-calibration on first ``read()``. Pass a
                ``(rows, cols)`` array of per-pixel baselines, or a scalar applied to
                every pixel. Typical resting ADC values land around 10-40 for an
                unloaded sensor, so a scalar like ``20.0`` is a reasonable default
                when you can't afford the startup delay of a full calibration. For
                accurate contact detection, prefer letting ``calibrate()`` run.
        """
        self.port = port
        self.rows = rows
        self.cols = cols
        self.baud = baud
        self.threshold = threshold
        self.noise_scale = noise_scale
        self.init_frames = init_frames
        self.read_timeout_s = read_timeout_s

        self._frame_bytes = rows * cols
        self._serial: serial.Serial | None = None
        self._buf = bytearray()
        self._baseline: NDArray[np.float32] | None = None
        self._seq = 0

        if baseline is not None:
            self._baseline = np.broadcast_to(np.float32(baseline), (rows, cols)).astype(np.float32).copy()

    def open(self) -> FlexiTacSensor:
        """Open the serial port if not already open."""
        if self._serial is None or not self._serial.is_open:
            self._serial = serial.Serial(self.port, self.baud, timeout=0.05)
            self._serial.reset_input_buffer()
            self._buf.clear()
        return self

    def close(self) -> None:
        if self._serial is not None and self._serial.is_open:
            self._serial.close()
        self._serial = None

    def __enter__(self) -> FlexiTacSensor:
        return self.open()

    def __exit__(self, *_: object) -> None:
        self.close()

    @property
    def baseline(self) -> NDArray[np.float32] | None:
        """Per-pixel baseline learned during calibration, or ``None``."""
        return self._baseline

    def calibrate(self, n: int | None = None) -> NDArray[np.float32]:
        """Set baseline as the median of ``n`` raw frames."""
        self.open()
        n = n if n is not None else self.init_frames
        stack = np.stack([self._read_raw() for _ in range(n)]).astype(np.float32)
        self._baseline = np.median(stack, axis=0).astype(np.float32)
        return self._baseline

    def read(self) -> FlexiTacFrame:
        """Read one frame, calibrating on first call."""
        if self._baseline is None:
            self.calibrate()
        raw = self._read_raw()
        normalized = self._normalize(raw)
        frame = FlexiTacFrame(seq=self._seq, timestamp_s=time.time(), raw=raw, normalized=normalized)
        self._seq += 1
        return frame

    def __iter__(self) -> Iterator[FlexiTacFrame]:
        while True:
            yield self.read()

    def read_latest(self) -> FlexiTacFrame:
        """Read one frame, discarding older frames already queued in the serial buffer.

        Use this for live visualizations so renders never lag behind the sensor.
        """
        if self._baseline is None:
            self.calibrate()
        if self._serial is None or not self._serial.is_open:
            raise RuntimeError("serial port is not open")

        pending = self._serial.in_waiting
        if pending:
            self._buf.extend(self._serial.read(pending))

        raw = self._latest_buffered_frame()
        if raw is None:
            raw = self._read_raw()
        normalized = self._normalize(raw)
        frame = FlexiTacFrame(seq=self._seq, timestamp_s=time.time(), raw=raw, normalized=normalized)
        self._seq += 1
        return frame

    def _latest_buffered_frame(self) -> NDArray[np.uint8] | None:
        latest: NDArray[np.uint8] | None = None
        while True:
            idx = self._buf.find(MARKER)
            if idx < 0 or len(self._buf) - idx - 2 < self._frame_bytes:
                break
            del self._buf[: idx + 2]
            payload = bytes(self._buf[: self._frame_bytes])
            del self._buf[: self._frame_bytes]
            latest = np.frombuffer(payload, dtype=np.uint8).reshape(self.rows, self.cols).copy()
        return latest

    def _normalize(self, raw: NDArray[np.uint8]) -> NDArray[np.float32]:
        assert self._baseline is not None
        signal = raw.astype(np.float32) - self._baseline - self.threshold
        signal = np.clip(signal, 0.0, 100.0)
        peak = float(signal.max())
        scale = peak + 1e-6 if peak >= self.threshold else self.noise_scale
        return np.clip(signal / scale, 0.0, 1.0).astype(np.float32)

    def _read_raw(self) -> NDArray[np.uint8]:
        if self._serial is None or not self._serial.is_open:
            raise RuntimeError("serial port is not open")

        deadline = time.monotonic() + self.read_timeout_s
        read_size = max(1024, self._frame_bytes * 2)

        while time.monotonic() < deadline:
            chunk = self._serial.read(read_size)
            if chunk:
                self._buf.extend(chunk)
                if len(self._buf) > 50_000:
                    del self._buf[: len(self._buf) - 50_000]

            idx = self._buf.find(MARKER)
            if idx < 0:
                if len(self._buf) > 1:
                    del self._buf[:-1]
                continue

            if len(self._buf) - idx - 2 < self._frame_bytes:
                continue

            del self._buf[: idx + 2]
            payload = bytes(self._buf[: self._frame_bytes])
            del self._buf[: self._frame_bytes]
            return np.frombuffer(payload, dtype=np.uint8).reshape(self.rows, self.cols).copy()

        raise TimeoutError(f"timed out after {self.read_timeout_s:.2f}s waiting for a frame")
