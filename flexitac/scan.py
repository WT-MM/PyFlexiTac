"""Backward-compatible shim for `python -m flexitac.scan`."""

from __future__ import annotations

from flexitac.scripts.scan import main

if __name__ == "__main__":
    raise SystemExit(main())
