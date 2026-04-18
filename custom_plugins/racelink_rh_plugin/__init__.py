"""RaceLink RotorHazard adapter plugin entrypoint."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


def _bootstrap_vendor_path() -> None:
    """Expose bundled host dependencies through the normal Python path."""
    package_dir = Path(__file__).resolve().parent
    vendor_path = package_dir / "vendor" / "site-packages"
    if not vendor_path.is_dir():
        return

    vendor_path_str = str(vendor_path)
    if vendor_path_str not in sys.path:
        sys.path.insert(0, vendor_path_str)


_bootstrap_vendor_path()


def initialize(*args: object, **kwargs: object) -> object:
    """Load the RotorHazard adapter bootstrap lazily for plugin initialization."""
    bootstrap_module = importlib.import_module(".plugin.bootstrap", package=__package__)
    bootstrap_initialize = bootstrap_module.initialize

    return bootstrap_initialize(*args, **kwargs)


__all__ = ["initialize"]
