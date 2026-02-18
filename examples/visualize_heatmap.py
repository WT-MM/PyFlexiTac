"""Visualize live FlexiTac normalized data as a heatmap."""

from __future__ import annotations

import argparse
import importlib
import time
from typing import Any

import numpy as np

from flexitac import FlexiTacSensor, ProcessingConfig


def build_parser() -> argparse.ArgumentParser:
    """Build command-line arguments for heatmap visualization."""
    parser = argparse.ArgumentParser(description="Live FlexiTac heatmap visualization.")
    parser.add_argument("--port", required=True, help="Serial port (example: /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=2_000_000, help="Serial baud rate")
    parser.add_argument("--rows", type=int, default=16, help="Frame row count")
    parser.add_argument("--cols", type=int, default=32, help="Frame column count")
    parser.add_argument("--threshold", type=float, default=25.0, help="Processing threshold")
    parser.add_argument("--noise-scale", type=float, default=30.0, help="Low-signal normalization scale")
    parser.add_argument("--init-frames", type=int, default=30, help="Calibration frame count")
    parser.add_argument("--read-timeout-s", type=float, default=5.0, help="Timeout for each frame read")
    parser.add_argument("--interval-ms", type=int, default=30, help="Animation update interval in milliseconds")
    parser.add_argument("--cmap", default="viridis", help="Matplotlib colormap name")
    return parser


def main() -> int:
    """Run live heatmap visualization."""
    args = build_parser().parse_args()

    try:
        matplotlib = importlib.import_module("matplotlib")
        # Prefer an interactive backend so plt.show() opens a window (required before pyplot)
        for backend in ("TkAgg", "Qt5Agg", "GTK4Agg", "GTK3Agg", "WXAgg"):
            try:
                matplotlib.use(backend)
                break
            except Exception:
                pass
        pyplot = importlib.import_module("matplotlib.pyplot")
        animation_mod = importlib.import_module("matplotlib.animation")
    except ImportError as exc:
        msg = (
            "This example requires matplotlib. Install with:\n"
            "  pip install matplotlib\n"
            "or\n"
            "  pip install 'flexitac[examples]'"
        )
        raise SystemExit(msg) from exc

    if matplotlib.get_backend().lower() == "agg":
        print(
            "No interactive display available (matplotlib is using the Agg backend).\n"
            "This example needs a GUI. Options:\n"
            "  - Run on a machine with a display, or\n"
            "  - Use X11 forwarding: ssh -X ... then run this script, or\n"
            "  - Set DISPLAY and X authority (e.g. xauth) if using a remote display."
        )
        return 1

    processing = ProcessingConfig(
        threshold=args.threshold,
        noise_scale=args.noise_scale,
        init_frames=args.init_frames,
    )

    sensor = FlexiTacSensor(
        port=args.port,
        baud=args.baud,
        rows=args.rows,
        cols=args.cols,
        read_timeout_s=args.read_timeout_s,
        processing=processing,
    )

    sensor.open()
    sensor.calibrate()
    print("Calibration complete. Starting heatmap window...")

    figure: Any
    axis: Any
    figure, axis = pyplot.subplots(figsize=(8, 4.5))

    heatmap = axis.imshow(
        np.zeros((args.rows, args.cols), dtype=np.float32),
        cmap=args.cmap,
        vmin=0.0,
        vmax=1.0,
        aspect="auto",
        interpolation="nearest",
    )
    figure.colorbar(heatmap, ax=axis, fraction=0.046, pad=0.04)
    status_text = axis.set_title("FlexiTac live heatmap")
    axis.set_xlabel("Column")
    axis.set_ylabel("Row")

    started = time.monotonic()
    frames_seen = 0

    def update(_frame_idx: int) -> list[Any]:
        nonlocal frames_seen
        frame = sensor.read_frame()
        frames_seen += 1

        heatmap.set_data(frame.normalized)

        elapsed = max(time.monotonic() - started, 1e-6)
        fps = frames_seen / elapsed
        status_text.set_text(
            f"FlexiTac live heatmap | seq={frame.seq} fps={fps:0.1f} "
            f"raw_max={int(frame.raw.max())} norm_max={float(frame.normalized.max()):0.3f}"
        )

        return [heatmap]

    anim = animation_mod.FuncAnimation(
        figure, update, interval=args.interval_ms, blit=False, cache_frame_data=False
    )

    try:
        pyplot.show()
    finally:
        sensor.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
