"""Build a self-contained offline release ZIP for RaceLink_RH_Plugin."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import shutil
import subprocess
import sys
import types
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

PLUGIN_NAME = "racelink_rh_plugin"
PLUGIN_RELATIVE_PATH = Path("custom_plugins") / PLUGIN_NAME
VENDOR_RELATIVE_PATH = Path("vendor") / "site-packages"
REPO_ROOT_FILES = ("README.md", "LICENSE")
PLUGIN_IGNORED_DIRS = {".git", ".github", ".ruff_cache", ".venv", "__pycache__"}
PLUGIN_IGNORED_SUFFIXES = {".pyc", ".pyo"}
PYTHON_RUNTIME_DEPENDENCIES = ("pyserial==3.5",)
VENDORED_DISTINFO_PREFIXES = {
    "pyserial-",
    "racelink_host-",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an offline-installable RaceLink_RH_Plugin ZIP."
    )
    parser.add_argument(
        "--host-wheel",
        required=True,
        type=Path,
        help="Path to a released RaceLink_Host wheel artifact.",
    )
    parser.add_argument(
        "--output-dir",
        default=Path("dist"),
        type=Path,
        help="Directory that will receive the staged bundle and ZIP file.",
    )
    parser.add_argument(
        "--release-tag",
        default="",
        help="Optional release label used in the ZIP filename.",
    )
    return parser.parse_args()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _plugin_source_dir() -> Path:
    return _repo_root() / PLUGIN_RELATIVE_PATH


def _ignore_plugin_copy(_directory: str, entries: list[str]) -> set[str]:
    ignored: set[str] = set()
    for entry in entries:
        entry_path = Path(entry)
        if entry in PLUGIN_IGNORED_DIRS or entry_path.suffix in PLUGIN_IGNORED_SUFFIXES:
            ignored.add(entry)
    return ignored


def _copy_plugin_tree(source_dir: Path, stage_plugin_dir: Path) -> None:
    shutil.copytree(
        source_dir,
        stage_plugin_dir,
        ignore=_ignore_plugin_copy,
        dirs_exist_ok=False,
    )


def _extract_host_wheel(host_wheel_path: Path, vendor_root: Path) -> None:
    """Extract the released host wheel into the vendored site-packages directory."""
    if host_wheel_path.suffix != ".whl":
        message = f"Host artifact is not a wheel: {host_wheel_path}"
        raise RuntimeError(message)
    with ZipFile(host_wheel_path) as archive:
        archive.extractall(vendor_root)


def _install_vendor_dependencies(vendor_root: Path) -> None:
    """Install extra runtime dependencies required by the host wheel offline bundle."""
    subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--target",
            str(vendor_root),
            *PYTHON_RUNTIME_DEPENDENCIES,
        ],
        check=True,
    )


def _prune_vendor_runtime(vendor_root: Path) -> None:
    """Keep only offline-required runtime pieces in the vendored site-packages."""
    for child in vendor_root.iterdir():
        if child.name in {"controller.py", "racelink", "serial"}:
            continue
        if any(child.name.startswith(prefix) for prefix in VENDORED_DISTINFO_PREFIXES):
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    build_backend = vendor_root / "racelink" / "_build_backend.py"
    if build_backend.is_file():
        build_backend.unlink()


def _install_host_runtime(host_wheel_path: Path, stage_plugin_dir: Path) -> None:
    vendor_root = stage_plugin_dir / VENDOR_RELATIVE_PATH
    vendor_root.mkdir(parents=True, exist_ok=True)
    _extract_host_wheel(host_wheel_path, vendor_root)
    _install_vendor_dependencies(vendor_root)
    _prune_vendor_runtime(vendor_root)


def _patch_manifest(stage_plugin_dir: Path) -> dict[str, object]:
    manifest_path = stage_plugin_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["dependencies"] = []
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def _archive_root_name(release_tag: str) -> str:
    """Build the top-level folder name used inside the release ZIP."""
    label = str(release_tag).strip()
    return f"RaceLink_RH_Plugin-{label}" if label else "RaceLink_RH_Plugin-offline"


def _bundle_name(manifest: dict[str, object], release_tag: str) -> str:
    version = str(manifest.get("version", "0.0.0"))
    label = str(release_tag).strip() or f"v{version}"
    return f"racelink_rh_plugin_offline_{label}.zip"


def _write_zip(stage_root: Path, zip_path: Path) -> None:
    archive_root = next(path for path in stage_root.iterdir() if path.is_dir())
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
        for file_path in sorted(archive_root.rglob("*")):
            if file_path.is_dir():
                continue
            if "__pycache__" in file_path.parts:
                continue
            if file_path.suffix in PLUGIN_IGNORED_SUFFIXES:
                continue
            archive.write(file_path, file_path.relative_to(stage_root))


def _validate_vendor_runtime(vendor_root: Path) -> None:
    """Validate the pruned vendored runtime contents."""
    if not (vendor_root / "controller.py").is_file():
        raise RuntimeError("Bundled controller.py is missing from offline artifact")
    if not (vendor_root / "serial").is_dir():
        raise RuntimeError("Bundled pyserial runtime is missing from offline artifact")

    racelink_package_dir = vendor_root / "racelink"
    if not racelink_package_dir.is_dir():
        raise RuntimeError("Bundled racelink package is missing from offline artifact")
    if not (racelink_package_dir / "app.py").is_file():
        raise RuntimeError("Bundled host app.py is missing from vendor artifact")
    if not (racelink_package_dir / "web" / "__init__.py").is_file():
        raise RuntimeError("Bundled host web package is missing from vendor artifact")

    unexpected_vendor_children = sorted(
        child.name
        for child in vendor_root.iterdir()
        if child.name not in {"controller.py", "racelink", "serial"}
        and not any(
            child.name.startswith(prefix) for prefix in VENDORED_DISTINFO_PREFIXES
        )
    )
    if unexpected_vendor_children:
        message = (
            "Unexpected vendored packages remain in offline artifact: "
            f"{unexpected_vendor_children}"
        )
        raise RuntimeError(message)


def _validate_stage(stage_root: Path) -> None:
    archive_root = next(path for path in stage_root.iterdir() if path.is_dir())
    stage_plugin_dir = archive_root / PLUGIN_RELATIVE_PATH
    manifest = json.loads((stage_plugin_dir / "manifest.json").read_text("utf-8"))
    dependencies = manifest.get("dependencies", [])
    if dependencies:
        message = f"Offline manifest still declares dependencies: {dependencies}"
        raise RuntimeError(message)

    vendor_root = stage_plugin_dir / VENDOR_RELATIVE_PATH
    _validate_vendor_runtime(vendor_root)

    custom_plugins_root = archive_root / "custom_plugins"
    sys.path.insert(0, str(custom_plugins_root))
    sys.path.insert(0, str(vendor_root))
    created_stub_modules = _install_rotorhazard_stubs()
    try:
        plugins_parent = types.ModuleType("plugins")
        plugins_parent.__path__ = [str(archive_root / "custom_plugins")]
        sys.modules["plugins"] = plugins_parent

        plugin_init = stage_plugin_dir / "__init__.py"
        spec = importlib.util.spec_from_file_location(
            "plugins.racelink_rh_plugin",
            plugin_init,
            submodule_search_locations=[str(stage_plugin_dir)],
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Unable to create import spec for staged plugin")
        module = importlib.util.module_from_spec(spec)
        sys.modules["plugins.racelink_rh_plugin"] = module
        spec.loader.exec_module(module)
        if not hasattr(module, "initialize"):
            raise RuntimeError("Staged plugin package does not expose initialize()")

        importlib.import_module("controller")
        importlib.import_module("racelink.app")
        importlib.import_module("racelink.web")
    finally:
        if sys.path and sys.path[0] == str(vendor_root):
            sys.path.pop(0)
        if sys.path and sys.path[0] == str(custom_plugins_root):
            sys.path.pop(0)
        for module_name in (
            "plugins.racelink_rh_plugin",
            "plugins",
            *created_stub_modules,
        ):
            sys.modules.pop(module_name, None)


def _install_stub(module_name: str, module: types.ModuleType) -> str | None:
    """Register one temporary validation stub if the module is missing."""
    if module_name in sys.modules:
        return None

    sys.modules[module_name] = module
    return module_name


def _build_eventmanager_stub() -> types.ModuleType:
    """Build a stub for the RotorHazard event manager module."""
    eventmanager = types.ModuleType("eventmanager")

    class _Evt:
        DATA_IMPORT_INITIALIZE = "DATA_IMPORT_INITIALIZE"
        DATA_EXPORT_INITIALIZE = "DATA_EXPORT_INITIALIZE"
        ACTIONS_INITIALIZE = "ACTIONS_INITIALIZE"
        STARTUP = "STARTUP"
        RACE_START = "RACE_START"
        RACE_FINISH = "RACE_FINISH"
        RACE_STOP = "RACE_STOP"

    eventmanager.Evt = _Evt
    return eventmanager


def _build_eventactions_stub() -> types.ModuleType:
    """Build a stub for the RotorHazard event actions module."""
    event_actions = types.ModuleType("EventActions")

    class ActionEffect:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.args = args
            self.kwargs = kwargs

    event_actions.ActionEffect = ActionEffect
    return event_actions


def _build_rhui_stub() -> types.ModuleType:
    """Build a stub for RotorHazard UI field classes."""
    rhui = types.ModuleType("RHUI")

    class UIField:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.args = args
            self.kwargs = kwargs

    class UIFieldSelectOption:
        def __init__(self, value: object, label: object) -> None:
            self.value = value
            self.label = label

    class UIFieldType:
        SELECT = "SELECT"
        BASIC_INT = "BASIC_INT"
        TEXT = "TEXT"
        CHECKBOX = "CHECKBOX"

    rhui.UIField = UIField
    rhui.UIFieldSelectOption = UIFieldSelectOption
    rhui.UIFieldType = UIFieldType
    return rhui


def _build_data_export_stub() -> types.ModuleType:
    """Build a stub for the RotorHazard data export module."""
    data_export = types.ModuleType("data_export")

    class DataExporter:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.args = args
            self.kwargs = kwargs

    data_export.DataExporter = DataExporter
    return data_export


def _build_data_import_stub() -> types.ModuleType:
    """Build a stub for the RotorHazard data import module."""
    data_import = types.ModuleType("data_import")

    class DataImporter:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.args = args
            self.kwargs = kwargs

    data_import.DataImporter = DataImporter
    return data_import


def _install_rotorhazard_stubs() -> list[str]:
    """Install lightweight stub modules needed for offline smoke imports."""
    created: list[str] = []
    stub_factories = (
        ("eventmanager", _build_eventmanager_stub),
        ("EventActions", _build_eventactions_stub),
        ("RHUI", _build_rhui_stub),
        ("data_export", _build_data_export_stub),
        ("data_import", _build_data_import_stub),
    )
    for module_name, factory in stub_factories:
        installed_name = _install_stub(module_name, factory())
        if installed_name is not None:
            created.append(installed_name)

    return created


def build_offline_release(
    *,
    host_wheel_path: Path,
    output_dir: Path,
    release_tag: str,
) -> Path:
    """Create a self-contained offline RotorHazard plugin bundle ZIP."""
    stage_root = output_dir / "offline-stage"
    if stage_root.exists():
        shutil.rmtree(stage_root)
    stage_root.mkdir(parents=True, exist_ok=True)

    archive_root = stage_root / _archive_root_name(release_tag)
    archive_root.mkdir(parents=True, exist_ok=True)
    stage_plugin_dir = archive_root / PLUGIN_RELATIVE_PATH
    _copy_plugin_tree(_plugin_source_dir(), stage_plugin_dir)
    manifest = _patch_manifest(stage_plugin_dir)
    for root_file in REPO_ROOT_FILES:
        source_path = _repo_root() / root_file
        if source_path.is_file():
            shutil.copy2(source_path, archive_root / root_file)
    _install_host_runtime(host_wheel_path, stage_plugin_dir)
    _validate_stage(stage_root)

    zip_path = output_dir / _bundle_name(manifest, release_tag)
    if zip_path.exists():
        zip_path.unlink()
    _write_zip(stage_root, zip_path)
    return zip_path


def main() -> int:
    """Run the offline bundle builder from the command line."""
    args = _parse_args()
    zip_path = build_offline_release(
        host_wheel_path=args.host_wheel.resolve(),
        output_dir=args.output_dir.resolve(),
        release_tag=args.release_tag,
    )
    sys.stdout.write(f"{zip_path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
