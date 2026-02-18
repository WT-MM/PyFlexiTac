"""Logging helpers with optional colorized formatting."""

from __future__ import annotations

import logging


def configure_logging(*, verbose: bool) -> logging.Logger:
    """Configure and return the package logger."""
    level = logging.DEBUG if verbose else logging.INFO

    try:
        import colorlogging

        colorlogging.configure(level=level)
    except ImportError:
        logging.basicConfig(level=level, format="%(levelname)-8s %(message)s", force=True)

    logger = logging.getLogger("flexitac")
    logger.setLevel(level)
    return logger
