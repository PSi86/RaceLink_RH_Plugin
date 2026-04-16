"""RaceLink RotorHazard adapter plugin."""

from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_vendor_path() -> None:
    """Expose bundled host dependencies when the offline release is installed."""
    vendor_path = Path(__file__).resolve().parent / "vendor" / "site-packages"
    if not vendor_path.is_dir():
        return

    vendor_path_str = str(vendor_path)
    if vendor_path_str not in sys.path:
        sys.path.insert(0, vendor_path_str)


_bootstrap_vendor_path()

from .plugin import initialize  # noqa: E402

__all__ = ["initialize"]
