"""Stream FlexiTac frames and print FPS / signal stats."""

from __future__ import annotations

import argparse
import time

from flexitac import FlexiTacSensor


def main() -> int:
    parser = argparse.ArgumentParser(description="Stream FlexiTac frames.")
    parser.add_argument("--port", required=True)
    parser.add_argument("--rows", type=int, default=12)
    parser.add_argument("--cols", type=int, default=32)
    parser.add_argument("--baud", type=int, default=2_000_000)
    parser.add_argument("--frames", type=int, default=0, help="0 = run forever")
    parser.add_argument(
        "--per-row",
        action="store_true",
        help="Print per-row raw mean / baseline (useful when some rows look dead)",
    )
    args = parser.parse_args()

    with FlexiTacSensor(args.port, rows=args.rows, cols=args.cols, baud=args.baud) as sensor:
        sensor.calibrate()
        started = time.monotonic()
        if args.per_row:
            assert sensor.baseline is not None
            print("baseline per row:", [round(float(v), 1) for v in sensor.baseline.mean(axis=1)])

        for i, frame in enumerate(sensor, start=1):
            fps = i / max(time.monotonic() - started, 1e-6)
            print(
                f"frame={i:6d} fps={fps:6.1f} raw_max={int(frame.raw.max()):3d} "
                f"norm_max={float(frame.normalized.max()):.3f}"
            )
            if args.per_row and i % 20 == 0:
                row_max = frame.raw.max(axis=1)
                print("  raw_max per row:", [int(v) for v in row_max])
            if args.frames and i >= args.frames:
                break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
