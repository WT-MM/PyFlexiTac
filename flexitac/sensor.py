"""High-level runtime API for reading data from a FlexiTac sensor."""

from __future__ import annotations

import time
from collections.abc import Iterator

import numpy as np
import serial

from flexitac.processing import FrameProcessor
from flexitac.protocol import FrameParser
from flexitac.types import FlexiTacFrame, ProcessingConfig, SensorGeometry


class FlexiTacSensor:
    """Blocking serial interface for reading structured FlexiTac frames."""

    def __init__(
        self,
        *,
        port: str,
        baud: int = 2_000_000,
        rows: int = 16,
        cols: int = 32,
        marker: bytes = b"\xaa\x55",
        timeout_s: float = 0.05,
        read_timeout_s: float = 5.0,
        processing: ProcessingConfig | None = None,
    ) -> None:
        self.port = port
        self.baud = baud
        self.timeout_s = timeout_s
        self.read_timeout_s = read_timeout_s
        self.geometry = SensorGeometry(rows=rows, cols=cols)
        self.processing = processing or ProcessingConfig()
        self._parser = FrameParser(geometry=self.geometry, marker=marker)
        self._processor = FrameProcessor(geometry=self.geometry, config=self.processing)
        self._serial: serial.Serial | None = None
        self._seq = 0

    def open(self) -> FlexiTacSensor:
        """Open the serial port if it is not already open."""
        if self._serial is not None and self._serial.is_open:
            return self

        self._serial = serial.Serial(self.port, self.baud, timeout=self.timeout_s)
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()
        self._parser.reset()
        return self

    def close(self) -> None:
        """Close the serial port if it is open."""
        if self._serial is None:
            return
        if self._serial.is_open:
            self._serial.close()
        self._serial = None

    def __enter__(self) -> FlexiTacSensor:
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        del exc_type, exc, traceback
        self.close()

    def calibrate(self, frames: int | None = None) -> None:
        """Read initialization frames and compute the baseline median."""
        self.open()
        target = frames if frames is not None else self.processing.init_frames

        calibration_frames: list[np.ndarray] = []
        for _ in range(target):
            calibration_frames.append(self._read_raw_frame(timeout_s=self.read_timeout_s))

        self._processor.calibrate(calibration_frames)

    def read_frame(self) -> FlexiTacFrame:
        """Read one frame and return raw and processed arrays."""
        self.open()
        if self._processor.baseline is None:
            self.calibrate()

        raw = self._read_raw_frame(timeout_s=self.read_timeout_s)
        calibrated, normalized = self._processor.process(raw)

        frame = FlexiTacFrame(
            seq=self._seq,
            timestamp_s=time.time(),
            raw=raw,
            calibrated=calibrated,
            normalized=normalized,
            rows=self.geometry.rows,
            cols=self.geometry.cols,
        )
        self._seq += 1
        return frame

    def iter_frames(self, limit: int | None = None) -> Iterator[FlexiTacFrame]:
        """Yield frames continuously or up to a fixed limit."""
        count = 0
        while limit is None or count < limit:
            yield self.read_frame()
            count += 1

    def _read_raw_frame(self, timeout_s: float) -> np.ndarray:
        serial_dev = self._serial
        if serial_dev is None or not serial_dev.is_open:
            msg = "serial port is not open"
            raise RuntimeError(msg)

        deadline = time.monotonic() + timeout_s
        read_size = max(1024, self.geometry.frame_bytes * 2)

        while time.monotonic() < deadline:
            chunk = serial_dev.read(read_size)
            frames = self._parser.feed(chunk)
            if frames:
                return frames[-1]

        msg = f"timed out after {timeout_s:.2f}s waiting for a complete frame"
        raise TimeoutError(msg)
