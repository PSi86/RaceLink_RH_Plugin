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


def _append_host_package_path(candidate_root: Path) -> None:
    """Extend the composite racelink package path with one host package location."""
    module = sys.modules[__name__]
    package_path = candidate_root / "racelink"
    if not package_path.is_dir():
        return

    module_paths = list(getattr(module, "__path__", []))
    candidate = str(package_path)
    if candidate not in module_paths:
        module_paths.append(candidate)
        module.__path__ = module_paths  # type: ignore[attr-defined]


def _bootstrap_vendor_path() -> None:
    """Expose bundled or installed host dependencies under the shared racelink package."""
    package_dir = Path(__file__).resolve().parent
    vendor_path = package_dir / "vendor" / "site-packages"

    if vendor_path.is_dir():
        vendor_path_str = str(vendor_path)
        if vendor_path_str not in sys.path:
            sys.path.insert(0, vendor_path_str)
        _append_host_package_path(vendor_path)

    for sys_path_entry in sys.path:
        try:
            entry_path = Path(sys_path_entry).resolve()
        except OSError:
            continue
        if entry_path == package_dir:
            continue
        _append_host_package_path(entry_path)


_ensure_package_alias()
_bootstrap_vendor_path()


def initialize(*args: object, **kwargs: object) -> object:
    """Load the RotorHazard adapter bootstrap lazily for plugin initialization."""
    bootstrap_module = importlib.import_module("racelink.plugin.bootstrap")
    return bootstrap_module.initialize(*args, **kwargs)


__all__ = ["initialize"]
