"""Identify the FlexiTac serial port by snapshotting before/after unplug."""

from __future__ import annotations

import platform
import time
from pathlib import Path

from serial.tools import list_ports

from flexitac.logging_utils import configure_logging


def list_serial_ports() -> set[str]:
    """Return currently available serial port device paths."""
    if platform.system() == "Windows":
        return {port.device for port in list_ports.comports()}
    return {str(path) for path in Path("/dev").glob("tty*")}


def find_port(*, settle_s: float = 0.5) -> str:
    """Prompt the user to unplug their sensor and return the port that vanished."""
    logger = configure_logging(verbose=False)

    before = list_serial_ports()
    logger.info("Detected %d serial ports.", len(before))
    input("Unplug the FlexiTac USB cable, then press Enter... ")

    time.sleep(settle_s)
    after = list_serial_ports()
    diff = sorted(before - after)

    if len(diff) == 1:
        port = diff[0]
        logger.info("FlexiTac port: %s", port)
        logger.info("Reconnect the USB cable.")
        return port
    if not diff:
        raise OSError("No port disappeared. Make sure you actually unplugged the device.")
    raise OSError(f"Multiple ports disappeared: {diff}. Unplug only the FlexiTac.")


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for ``flexitac-find-port``."""
    del argv
    try:
        find_port()
        return 0
    except OSError as exc:
        configure_logging(verbose=False).error("%s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
