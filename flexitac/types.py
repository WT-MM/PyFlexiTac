"""Typed data structures used by the flexitac package."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

RawFrame = NDArray[np.uint8]
FloatFrame = NDArray[np.float32]


@dataclass(frozen=True)
class SensorGeometry:
    """Geometry of a tactile frame in rows and columns."""

    rows: int
    cols: int

    def __post_init__(self) -> None:
        if self.rows <= 0 or self.cols <= 0:
            msg = "rows and cols must both be positive"
            raise ValueError(msg)

    @property
    def frame_bytes(self) -> int:
        """Return the number of bytes expected for one raw frame."""
        return self.rows * self.cols


@dataclass(frozen=True)
class ProcessingConfig:
    """Signal processing parameters for incoming frames."""

    threshold: float = 25.0
    noise_scale: float = 30.0
    init_frames: int = 30

    def __post_init__(self) -> None:
        if self.noise_scale <= 0:
            msg = "noise_scale must be > 0"
            raise ValueError(msg)
        if self.init_frames <= 0:
            msg = "init_frames must be > 0"
            raise ValueError(msg)


@dataclass(frozen=True)
class FlexiTacFrame:
    """A structured output frame returned by the sensor runtime API."""

    seq: int
    timestamp_s: float
    raw: RawFrame
    calibrated: FloatFrame
    normalized: FloatFrame
    rows: int
    cols: int
