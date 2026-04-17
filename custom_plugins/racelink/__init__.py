"""RaceLink RotorHazard adapter plugin and shared package root."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


def _ensure_package_alias() -> None:
    """Expose this module under the canonical ``racelink`` package name."""
    module = sys.modules[__name__]
    package_dir = Path(__file__).resolve().parent

    if not hasattr(module, "__path__"):
        module.__path__ = [str(package_dir)]  # type: ignore[attr-defined]
    module.__package__ = "racelink"
    sys.modules.setdefault("racelink", module)


def _bootstrap_vendor_path() -> None:
    """Expose bundled host dependencies when the offline release is installed."""
    vendor_path = Path(__file__).resolve().parent / "vendor" / "site-packages"
    if not vendor_path.is_dir():
        return

    vendor_path_str = str(vendor_path)
    if vendor_path_str not in sys.path:
        sys.path.insert(0, vendor_path_str)


_ensure_package_alias()
_bootstrap_vendor_path()


def initialize(*args: object, **kwargs: object) -> object:
    """Load the RotorHazard adapter bootstrap lazily for plugin initialization."""
    bootstrap_module = importlib.import_module("racelink.plugin.bootstrap")
    return bootstrap_module.initialize(*args, **kwargs)


__all__ = ["initialize"]
