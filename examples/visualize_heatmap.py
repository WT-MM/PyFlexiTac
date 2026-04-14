"""Live heatmap of FlexiTac normalized frames using matplotlib."""

from __future__ import annotations

import argparse
import time

import matplotlib
import numpy as np

from flexitac import FlexiTacSensor

for _backend in ("TkAgg", "Qt5Agg", "MacOSX"):
    try:
        matplotlib.use(_backend)
        break
    except Exception:  # noqa: BLE001
        continue

from matplotlib import animation, pyplot as plt  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Live FlexiTac heatmap.")
    parser.add_argument("--port", required=True)
    parser.add_argument("--rows", type=int, default=12)
    parser.add_argument("--cols", type=int, default=32)
    parser.add_argument("--baud", type=int, default=2_000_000)
    parser.add_argument("--cmap", default="viridis")
    args = parser.parse_args()

    sensor = FlexiTacSensor(args.port, rows=args.rows, cols=args.cols, baud=args.baud).open()
    sensor.calibrate()

    fig, ax = plt.subplots(figsize=(8, 4.5))
    im = ax.imshow(np.zeros((args.rows, args.cols), dtype=np.float32), cmap=args.cmap, vmin=0.0, vmax=1.0)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    title = ax.set_title("FlexiTac")

    started = time.monotonic()
    count = 0

    def update(_: int) -> list:
        nonlocal count
        frame = sensor.read_latest()
        count += 1
        im.set_data(frame.normalized)
        fps = count / max(time.monotonic() - started, 1e-6)
        title.set_text(f"FlexiTac | seq={frame.seq} fps={fps:.1f}")
        return [im, title]

    _anim = animation.FuncAnimation(fig, update, interval=16, blit=True, cache_frame_data=False)
    try:
        plt.show()
    finally:
        sensor.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
