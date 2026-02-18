"""Frame processing pipeline for baseline correction and normalization."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from flexitac.types import FloatFrame, ProcessingConfig, RawFrame, SensorGeometry


class FrameProcessor:
    """Apply baseline correction and normalization to tactile frames."""

    def __init__(self, geometry: SensorGeometry, config: ProcessingConfig) -> None:
        self.geometry = geometry
        self.config = config
        self.baseline: FloatFrame | None = None

    def calibrate(self, frames: Sequence[RawFrame]) -> FloatFrame:
        """Calibrate using the median of a set of initialization frames."""
        if not frames:
            msg = "at least one frame is required for calibration"
            raise ValueError(msg)

        stack = np.stack([self._validate_shape(frame).astype(np.float32) for frame in frames], axis=0)
        baseline = np.median(stack, axis=0).astype(np.float32)
        self.baseline = baseline
        return baseline

    def process(self, raw: RawFrame) -> tuple[FloatFrame, FloatFrame]:
        """Convert one raw frame into calibrated and normalized signals."""
        frame = self._validate_shape(raw).astype(np.float32)
        if self.baseline is None:
            msg = "sensor is not calibrated; call calibrate() first"
            raise RuntimeError(msg)

        calibrated = frame - self.baseline - np.float32(self.config.threshold)
        calibrated = np.clip(calibrated, 0.0, 100.0).astype(np.float32)

        max_value = float(np.max(calibrated))
        if max_value < float(self.config.threshold):
            normalized = calibrated / np.float32(self.config.noise_scale)
        else:
            normalized = calibrated / np.float32(max_value + 1e-6)

        normalized = np.clip(normalized, 0.0, 1.0).astype(np.float32)
        return calibrated, normalized

    def reset(self) -> None:
        """Clear the current baseline."""
        self.baseline = None

    def _validate_shape(self, frame: RawFrame) -> RawFrame:
        if frame.shape != (self.geometry.rows, self.geometry.cols):
            msg = f"unexpected frame shape {frame.shape}; expected {(self.geometry.rows, self.geometry.cols)}"
            raise ValueError(msg)
        return frame
