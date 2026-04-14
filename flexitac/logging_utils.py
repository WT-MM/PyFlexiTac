"""Logging helpers for the flexitac package."""

from __future__ import annotations

import logging


def configure_logging(*, verbose: bool) -> logging.Logger:
    """Configure and return the package logger."""
    level = logging.DEBUG if verbose else logging.INFO

    logger = logging.getLogger("flexitac")
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)-8s %(message)s"))
        logger.addHandler(handler)

    return logger
