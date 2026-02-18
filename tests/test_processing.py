"""Tests for calibration and normalization processing."""

from __future__ import annotations

import numpy as np

from flexitac.processing import FrameProcessor
from flexitac.types import ProcessingConfig, SensorGeometry


def test_calibrate_uses_median_frame() -> None:
    geometry = SensorGeometry(rows=2, cols=2)
    config = ProcessingConfig(threshold=10.0, noise_scale=20.0, init_frames=2)
    processor = FrameProcessor(geometry=geometry, config=config)

    frames = [
        np.array([[10, 20], [30, 40]], dtype=np.uint8),
        np.array([[14, 18], [36, 38]], dtype=np.uint8),
        np.array([[12, 22], [32, 50]], dtype=np.uint8),
    ]

    baseline = processor.calibrate(frames)
    expected = np.array([[12, 20], [32, 40]], dtype=np.float32)
    np.testing.assert_array_equal(baseline, expected)


def test_process_low_signal_uses_noise_scale() -> None:
    geometry = SensorGeometry(rows=1, cols=3)
    config = ProcessingConfig(threshold=25.0, noise_scale=50.0, init_frames=1)
    processor = FrameProcessor(geometry=geometry, config=config)
    processor.baseline = np.array([[100, 100, 100]], dtype=np.float32)

    raw = np.array([[120, 118, 119]], dtype=np.uint8)
    calibrated, normalized = processor.process(raw)

    np.testing.assert_array_equal(calibrated, np.zeros((1, 3), dtype=np.float32))
    np.testing.assert_array_equal(normalized, np.zeros((1, 3), dtype=np.float32))


def test_process_high_signal_uses_peak_normalization() -> None:
    geometry = SensorGeometry(rows=1, cols=2)
    config = ProcessingConfig(threshold=10.0, noise_scale=10.0, init_frames=1)
    processor = FrameProcessor(geometry=geometry, config=config)
    processor.baseline = np.array([[100, 100]], dtype=np.float32)

    raw = np.array([[150, 130]], dtype=np.uint8)
    calibrated, normalized = processor.process(raw)

    np.testing.assert_array_equal(calibrated, np.array([[40.0, 20.0]], dtype=np.float32))
    np.testing.assert_allclose(normalized, np.array([[1.0, 0.5]], dtype=np.float32), rtol=1e-5, atol=1e-5)
