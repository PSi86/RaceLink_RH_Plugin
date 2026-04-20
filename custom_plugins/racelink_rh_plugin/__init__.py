"""RaceLink RotorHazard adapter plugin entrypoint."""

from __future__ import annotations

import importlib
import importlib.metadata
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)
_PACKAGE_DIR = Path(__file__).resolve().parent
_OFFLINE_WHEELS_DIR = _PACKAGE_DIR / "offline_wheels"
_INSTALL_TARGET_ENV = "RACELINK_RH_PLUGIN_INSTALL_TARGET"
_FORCE_INSTALL_ENV = "RACELINK_RH_PLUGIN_FORCE_BUNDLED_INSTALL"
_HOST_DISTRIBUTION = "racelink-host"
_HOST_WHEEL_RE = re.compile(
    r"^racelink_host-(?P<version>[^-]+)-.+\.whl$",
    re.IGNORECASE,
)


def _find_matching_wheel(directory: Path, pattern: re.Pattern[str]) -> Path | None:
    """Return the first wheel in a directory that matches one expected pattern."""
    if not directory.is_dir():
        return None

    for wheel_path in sorted(directory.glob("*.whl")):
        if pattern.match(wheel_path.name):
            return wheel_path
    return None


def _bundled_host_wheel() -> Path | None:
    """Return the bundled RaceLink_Host wheel when this is an offline bundle."""
    return _find_matching_wheel(_OFFLINE_WHEELS_DIR, _HOST_WHEEL_RE)


def _bundled_host_version() -> str | None:
    """Extract the bundled RaceLink_Host version from the staged wheel name."""
    host_wheel = _bundled_host_wheel()
    if host_wheel is None:
        return None

    match = _HOST_WHEEL_RE.match(host_wheel.name)
    if match is None:
        return None
    return match.group("version")


def _installed_host_version() -> str | None:
    """Return the installed RaceLink_Host version when available."""
    try:
        return importlib.metadata.version(_HOST_DISTRIBUTION)
    except importlib.metadata.PackageNotFoundError:
        try:
            version_module = importlib.import_module("racelink._version")
        except ModuleNotFoundError:
            return None

        return getattr(version_module, "VERSION", None)


def _ensure_target_path(target_path: Path) -> None:
    """Expose a custom install target through the active Python path."""
    target_str = str(target_path)
    if target_str not in sys.path:
        sys.path.insert(0, target_str)


def _build_pip_install_command(
    host_wheel: Path,
    *,
    target_path: Path | None,
) -> list[str]:
    """Build the local host-wheel pip install command for offline bootstrap."""
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--no-index",
        "--no-deps",
        "--disable-pip-version-check",
        "--upgrade",
        "--force-reinstall",
        str(host_wheel),
    ]
    if target_path is not None:
        command.extend(["--target", str(target_path)])
    return command


def _install_bundled_runtime(host_wheel: Path) -> None:
    """Install the bundled host wheel into the active Python environment."""
    target_override = os.environ.get(_INSTALL_TARGET_ENV, "").strip()
    target_path = Path(target_override).resolve() if target_override else None
    if target_path is not None:
        target_path.mkdir(parents=True, exist_ok=True)
        _ensure_target_path(target_path)

    command = _build_pip_install_command(host_wheel, target_path=target_path)
    subprocess.run(command, check=True)  # noqa: S603
    importlib.invalidate_caches()
    if target_path is not None:
        _ensure_target_path(target_path)


def _ensure_host_runtime_available() -> None:
    """Ensure the RaceLink host runtime is available before bootstrap imports."""
    bundled_version = _bundled_host_version()
    force_install = os.environ.get(_FORCE_INSTALL_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    installed_version = None if force_install else _installed_host_version()
    if bundled_version is None:
        if installed_version is None:
            message = (
                "RaceLink_Host is not installed and no offline_wheels bundle was "
                "found in the plugin package."
            )
            raise RuntimeError(message)
        return

    if installed_version == bundled_version:
        return

    host_wheel = _bundled_host_wheel()
    if host_wheel is None:
        message = (
            "Offline bundle is incomplete. Expected a RaceLink_Host wheel under "
            "offline_wheels/."
        )
        raise RuntimeError(message)

    logger.info(
        "Installing bundled RaceLink_Host %s into the active Python environment",
        bundled_version,
    )
    try:
        _install_bundled_runtime(host_wheel)
    except subprocess.CalledProcessError as exc:
        message = (
            "Unable to install the bundled RaceLink_Host wheel. Check that the "
            "RotorHazard Python environment already provides RaceLink_Host base "
            "dependencies like Flask and pyserial and that the environment is writable."
        )
        raise RuntimeError(message) from exc


def initialize(*args: object, **kwargs: object) -> object:
    """Load the RotorHazard adapter bootstrap lazily for plugin initialization."""
    _ensure_host_runtime_available()
    bootstrap_module = importlib.import_module(".plugin.bootstrap", package=__package__)
    bootstrap_initialize = bootstrap_module.initialize
    return bootstrap_initialize(*args, **kwargs)


__all__ = ["initialize"]
