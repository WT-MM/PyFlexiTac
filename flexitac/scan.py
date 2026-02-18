"""CLI for scanning FlexiTac flash prerequisites and connected boards."""

from __future__ import annotations

import argparse

from flexitac.flash import SUPPORTED_AVR_FQBNS, ensure_arduino_cli_available, list_boards, list_installed_cores
from flexitac.logging_utils import configure_logging


def build_parser() -> argparse.ArgumentParser:
    """Build the scanner CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m flexitac.scan",
        description="Scan for connected Arduino boards and flashing prerequisites.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose diagnostics output")
    parser.add_argument("--all", action="store_true", help="Show all detected boards, not just default AVR targets")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run scan diagnostics and print actionable guidance."""
    parser = build_parser()
    args = parser.parse_args(argv)
    logger = configure_logging(verbose=args.verbose)

    try:
        version = ensure_arduino_cli_available(verbose=args.verbose)
        logger.info("arduino-cli detected: %s", version)
    except Exception as exc:  # noqa: BLE001
        logger.error("arduino-cli unavailable: %s", exc)
        logger.info("Install arduino-cli and retry.")
        return 2

    try:
        boards = list_boards(verbose=args.verbose)
    except Exception as exc:  # noqa: BLE001
        logger.error("failed to list boards: %s", exc)
        return 2

    try:
        installed_cores = list_installed_cores()
    except Exception as exc:  # noqa: BLE001
        logger.warning("failed to inspect installed cores: %s", exc)
        installed_cores = set()

    logger.info("supported default AVR targets: %s", ", ".join(SUPPORTED_AVR_FQBNS))

    if installed_cores:
        logger.info("installed cores: %s", ", ".join(sorted(installed_cores)))
    else:
        logger.warning("no installed cores detected by arduino-cli")

    if not boards:
        logger.warning("no boards detected")
        logger.info("Connect your board and rerun this command.")
        logger.info("If detection still fails, try an explicit flash command:")
        logger.info("  uv run python -m flexitac.flash --profile 16x32 --fqbn arduino:avr:uno --port /dev/ttyUSB0")
        return 1

    filtered = boards if args.all else [board for board in boards if board.fqbn in SUPPORTED_AVR_FQBNS]
    if not filtered:
        logger.warning("boards were detected but none match supported AVR defaults")
        for board in boards:
            logger.info("detected: port=%s fqbn=%s name=%s", board.port, board.fqbn, board.name)
        logger.info("Use --all to list everything and --expert in flash mode if needed.")
        return 1

    logger.info("detected boards:")
    for board in filtered:
        support = "supported" if board.fqbn in SUPPORTED_AVR_FQBNS else "unsupported"
        logger.info("  port=%s fqbn=%s name=%s [%s]", board.port, board.fqbn, board.name, support)

    if len(filtered) == 1:
        candidate = filtered[0]
        logger.info("recommended flash command:")
        logger.info(
            "  uv run python -m flexitac.flash --profile 16x32 --fqbn %s --port %s",
            candidate.fqbn,
            candidate.port,
        )
    else:
        logger.warning("multiple candidate boards found; pass --port and --fqbn explicitly")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
