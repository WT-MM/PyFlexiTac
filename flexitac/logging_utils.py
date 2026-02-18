"""Logging helpers with optional colorized formatting."""

from __future__ import annotations

import logging


def configure_logging(*, verbose: bool) -> logging.Logger:
    """Configure and return the package logger."""
    logger = logging.getLogger("flexitac")
    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)

    # Reset handlers to avoid duplicate lines when CLIs reconfigure in-process.
    logger.handlers.clear()
    logger.propagate = False

    handler = logging.StreamHandler()
    handler.setLevel(level)

    formatter = _build_formatter()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def _build_formatter() -> logging.Formatter:
    """Build a colored formatter if colorlog is available."""
    try:
        import colorlog

        return colorlog.ColoredFormatter(
            "%(log_color)s%(levelname)-8s%(reset)s %(message)s",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
            reset=True,
        )
    except ImportError:
        return logging.Formatter("%(levelname)-8s %(message)s")
