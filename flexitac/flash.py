"""Render and upload FlexiTac firmware via ``arduino-cli``."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from flexitac.logging_utils import configure_logging

TEMPLATE_PATH = Path(__file__).resolve().parent / "firmware" / "template.ino"
DEFINE_RE = re.compile(r"^(\s*#define\s+)([A-Z0-9_]+)(\s+)([^\s].*)$")


class FlashError(RuntimeError):
    """Flashing or board-detection failure."""


def render_template(rows: int, cols: int, baud: int, mux_offset: int = 0) -> str:
    """Substitute ``ROW_COUNT``, ``COLUMN_COUNT``, ``BAUD_RATE``, ``MUX_CHANNEL_OFFSET``."""
    overrides = {
        "ROW_COUNT": str(rows),
        "COLUMN_COUNT": str(cols),
        "BAUD_RATE": str(baud),
        "MUX_CHANNEL_OFFSET": str(mux_offset),
    }
    out = []
    for line in TEMPLATE_PATH.read_text().splitlines():
        match = DEFINE_RE.match(line)
        if match and match.group(2) in overrides:
            prefix, name, spacing, _ = match.groups()
            out.append(f"{prefix}{name}{spacing}{overrides[name]}")
        else:
            out.append(line)
    return "\n".join(out) + "\n"


def detect_board() -> tuple[str, str]:
    """Return (port, fqbn) for the single connected Arduino, or raise."""
    result = _run(["arduino-cli", "board", "list"], capture=True)
    boards: list[tuple[str, str]] = []
    fqbn_re = re.compile(r"[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+")
    for line in result.stdout.splitlines():
        if not line.strip() or line.startswith(("Port", "Protocol")):
            continue
        token = line.split()[0]
        if not (token.startswith("/") or token.upper().startswith("COM")):
            continue
        fqbn_match = fqbn_re.search(line)
        if fqbn_match:
            boards.append((token, fqbn_match.group(0)))

    if len(boards) == 1:
        return boards[0]
    if not boards:
        raise FlashError("no Arduino board detected. Pass --port and --fqbn explicitly.")
    listing = "\n".join(f"  {p} {f}" for p, f in boards)
    raise FlashError(f"multiple boards detected; pass --port and --fqbn:\n{listing}")


def flash(
    *,
    port: str,
    fqbn: str,
    rows: int,
    cols: int,
    baud: int,
    mux_offset: int = 0,
    verbose: bool = False,
) -> None:
    """Render firmware and upload it to ``port``."""
    if shutil.which("arduino-cli") is None:
        raise FlashError(
            "arduino-cli not found on PATH. Install from https://arduino.github.io/arduino-cli/latest/installation/"
        )

    rendered = render_template(rows=rows, cols=cols, baud=baud, mux_offset=mux_offset)
    with tempfile.TemporaryDirectory(prefix="flexitac-") as tmp:
        sketch_dir = Path(tmp) / "flexitac_sketch"
        sketch_dir.mkdir()
        (sketch_dir / "flexitac_sketch.ino").write_text(rendered)

        _run(["arduino-cli", "compile", "--fqbn", fqbn, str(sketch_dir)], verbose=verbose)
        _run(["arduino-cli", "upload", "-p", port, "--fqbn", fqbn, str(sketch_dir)], verbose=verbose)


def _run(cmd: list[str], *, verbose: bool = False, capture: bool = False) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(cmd, text=True, capture_output=capture or not verbose, check=False)
    except FileNotFoundError as exc:
        raise FlashError(f"command not found: {cmd[0]}") from exc
    if result.returncode != 0:
        msg = (result.stderr or result.stdout or "").strip()
        raise FlashError(f"{' '.join(cmd)} failed: {msg}")
    return result


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for ``flexitac-flash``."""
    parser = argparse.ArgumentParser(description="Flash FlexiTac firmware via arduino-cli.")
    parser.add_argument("--port", help="Serial port (auto-detected if exactly one board is connected)")
    parser.add_argument("--fqbn", help="Arduino FQBN, e.g. arduino:avr:uno")
    parser.add_argument("--rows", type=int, default=12)
    parser.add_argument("--cols", type=int, default=32)
    parser.add_argument("--baud", type=int, default=2_000_000)
    parser.add_argument(
        "--mux-offset",
        type=int,
        default=4,
        help="Add this offset to the mux channel index (use if sensor row 0 is wired to mux channel N)",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logger = configure_logging(verbose=args.verbose)

    try:
        if shutil.which("arduino-cli") is None:
            raise FlashError(
                "arduino-cli not found on PATH. Install it (e.g. `brew install arduino-cli`) and run "
                "`arduino-cli core install arduino:avr`. See "
                "https://arduino.github.io/arduino-cli/latest/installation/"
            )

        port, fqbn = args.port, args.fqbn
        if port is None or fqbn is None:
            detected_port, detected_fqbn = detect_board()
            port = port or detected_port
            fqbn = fqbn or detected_fqbn

        logger.info(
            "Flashing %dx%d @ %d baud (mux_offset=%d) to %s (%s)",
            args.rows,
            args.cols,
            args.baud,
            args.mux_offset,
            port,
            fqbn,
        )
        flash(
            port=port,
            fqbn=fqbn,
            rows=args.rows,
            cols=args.cols,
            baud=args.baud,
            mux_offset=args.mux_offset,
            verbose=args.verbose,
        )
        logger.info("Flash complete.")
        return 0
    except FlashError as exc:
        logger.error("%s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
