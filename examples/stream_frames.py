"""Read FlexiTac frames and print streaming statistics."""

from __future__ import annotations

import argparse
import time

from flexitac import FlexiTacSensor, ProcessingConfig


def build_parser() -> argparse.ArgumentParser:
    """Build command-line arguments for frame streaming."""
    parser = argparse.ArgumentParser(description="Read FlexiTac frames and print basic metrics.")
    parser.add_argument("--port", required=True, help="Serial port (example: /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=2_000_000, help="Serial baud rate")
    parser.add_argument("--rows", type=int, default=16, help="Frame row count")
    parser.add_argument("--cols", type=int, default=32, help="Frame column count")
    parser.add_argument("--threshold", type=float, default=25.0, help="Processing threshold")
    parser.add_argument("--noise-scale", type=float, default=30.0, help="Low-signal normalization scale")
    parser.add_argument("--init-frames", type=int, default=30, help="Calibration frame count")
    parser.add_argument("--frames", type=int, default=0, help="Number of frames to read (0 = run forever)")
    parser.add_argument("--print-every", type=int, default=10, help="Print metrics every N frames")
    parser.add_argument("--read-timeout-s", type=float, default=5.0, help="Timeout for each frame read")
    return parser


def main() -> int:
    """Run the frame streaming example."""
    args = build_parser().parse_args()

    processing = ProcessingConfig(
        threshold=args.threshold,
        noise_scale=args.noise_scale,
        init_frames=args.init_frames,
    )

    limit = args.frames if args.frames > 0 else None
    started = time.monotonic()

    with FlexiTacSensor(
        port=args.port,
        baud=args.baud,
        rows=args.rows,
        cols=args.cols,
        read_timeout_s=args.read_timeout_s,
        processing=processing,
    ) as sensor:
        sensor.calibrate()
        print("Calibration complete. Streaming frames...")

        for index, frame in enumerate(sensor.iter_frames(limit=limit), start=1):
            if index % args.print_every != 0:
                continue

            elapsed = max(time.monotonic() - started, 1e-6)
            fps = index / elapsed
            raw_max = int(frame.raw.max())
            norm_max = float(frame.normalized.max())
            norm_mean = float(frame.normalized.mean())
            print(
                f"frame={index:6d} seq={frame.seq:6d} fps={fps:7.2f} "
                f"raw_max={raw_max:3d} norm_max={norm_max:0.3f} norm_mean={norm_mean:0.3f}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
