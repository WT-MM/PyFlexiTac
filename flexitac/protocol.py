"""Binary protocol parsing utilities for FlexiTac frames."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from flexitac.types import SensorGeometry


@dataclass
class FrameParser:
    """Parse framed byte streams into fixed-shape uint8 matrices."""

    geometry: SensorGeometry
    marker: bytes = b"\xaa\x55"
    max_buffer_bytes: int = 50_000

    def __post_init__(self) -> None:
        if len(self.marker) < 2:
            msg = "marker must contain at least two bytes"
            raise ValueError(msg)
        self._ring = bytearray()

    def feed(self, chunk: bytes) -> list[NDArray[np.uint8]]:
        """Feed bytes into the parser and return all complete frames found."""
        if chunk:
            self._ring.extend(chunk)

        if len(self._ring) > self.max_buffer_bytes:
            self._ring = self._ring[-self.max_buffer_bytes :]

        frames: list[NDArray[np.uint8]] = []
        frame_bytes = self.geometry.frame_bytes
        marker_len = len(self.marker)

        while True:
            marker_idx = self._ring.find(self.marker)
            if marker_idx < 0:
                keep = marker_len - 1
                if len(self._ring) > keep:
                    self._ring = self._ring[-keep:]
                break

            if marker_idx > 0:
                del self._ring[:marker_idx]

            if len(self._ring) < marker_len + frame_bytes:
                break

            del self._ring[:marker_len]
            frame_raw = bytes(self._ring[:frame_bytes])
            del self._ring[:frame_bytes]

            frame = np.frombuffer(frame_raw, dtype=np.uint8).copy().reshape((self.geometry.rows, self.geometry.cols))
            frames.append(frame)

        return frames

    def reset(self) -> None:
        """Drop all buffered bytes and reset parser state."""
        self._ring.clear()
