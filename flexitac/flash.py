"""Backward-compatible shim for `python -m flexitac.flash`."""

from __future__ import annotations

from flexitac.scripts.flash import main

if __name__ == "__main__":
    raise SystemExit(main())
