"""Build a self-contained offline release ZIP for RaceLink_RH_Plugin."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import types
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

PLUGIN_NAME = "racelink_rh_plugin"
PLUGIN_RELATIVE_PATH = Path("custom_plugins") / PLUGIN_NAME
OFFLINE_WHEELS_RELATIVE_PATH = Path("offline_wheels")
REPO_ROOT_FILES = ("README.md", "LICENSE")
PLUGIN_IGNORED_DIRS = {".git", ".github", ".ruff_cache", ".venv", "__pycache__"}
PLUGIN_IGNORED_SUFFIXES = {".pyc", ".pyo"}
INSTALL_TARGET_ENV = "RACELINK_RH_PLUGIN_INSTALL_TARGET"
FORCE_INSTALL_ENV = "RACELINK_RH_PLUGIN_FORCE_BUNDLED_INSTALL"


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


def _stage_offline_wheels(host_wheel_path: Path, stage_plugin_dir: Path) -> Path:
    """Populate the offline wheel staging directory for the bundle."""
    if host_wheel_path.suffix != ".whl":
        message = f"Host artifact is not a wheel: {host_wheel_path}"
        raise RuntimeError(message)

    offline_wheels_dir = stage_plugin_dir / OFFLINE_WHEELS_RELATIVE_PATH
    offline_wheels_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(host_wheel_path, offline_wheels_dir / host_wheel_path.name)
    return offline_wheels_dir


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
    configured_name = str(manifest.get("zip_filename", "")).strip()
    if configured_name:
        return configured_name

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


def _validate_offline_wheels(offline_wheels_dir: Path) -> None:
    """Assert that the offline bundle contains only the expected host wheel."""
    wheel_names = sorted(path.name for path in offline_wheels_dir.glob("*.whl"))
    host_wheels = [name for name in wheel_names if name.startswith("racelink_host-")]
    if len(host_wheels) != 1:
        message = (
            "Offline artifact must contain exactly one RaceLink_Host wheel under "
            f"offline_wheels/: {wheel_names}"
        )
        raise RuntimeError(message)

    if len(wheel_names) != 1:
        message = (
            "Offline artifact should only contain the RaceLink_Host wheel because "
            "RotorHazard already provides the shared runtime dependencies: "
            f"{wheel_names}"
        )
        raise RuntimeError(message)


def _assert_import_under_root(module_name: str, root: Path) -> None:
    """Ensure one imported module resolves from the simulated install target."""
    module = importlib.import_module(module_name)
    module_file = getattr(module, "__file__", None)
    if module_file is None:
        message = f"Imported module {module_name!r} has no __file__ for validation"
        raise RuntimeError(message)

    resolved_module_path = Path(module_file).resolve()
    resolved_root = root.resolve()
    if not resolved_module_path.is_relative_to(resolved_root):
        message = (
            f"Imported module {module_name!r} did not load from the simulated "
            f"offline install target: {resolved_module_path}"
        )
        raise RuntimeError(message)


def _load_staged_plugin_module(
    stage_plugin_dir: Path,
    custom_plugins_root: Path,
) -> types.ModuleType:
    """Load the staged plugin package for offline validation."""
    plugins_parent = types.ModuleType("plugins")
    plugins_parent.__path__ = [str(custom_plugins_root)]
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
    return module


def _validate_offline_runtime_install(
    *,
    archive_root: Path,
    stage_plugin_dir: Path,
) -> None:
    """Simulate the first offline start and verify host-wheel installation."""
    custom_plugins_root = archive_root / "custom_plugins"
    temp_root = Path(tempfile.mkdtemp(prefix="racelink-rh-plugin-offline-"))
    install_target = temp_root / "site-packages"
    install_target.mkdir(parents=True, exist_ok=True)
    previous_target_env = os.environ.get(INSTALL_TARGET_ENV)
    previous_force_env = os.environ.get(FORCE_INSTALL_ENV)
    sys.path.insert(0, str(custom_plugins_root))
    created_stub_modules = _install_rotorhazard_stubs()
    imported_modules = ["controller", "racelink", "racelink.app", "racelink.web"]
    try:
        os.environ[INSTALL_TARGET_ENV] = str(install_target)
        os.environ[FORCE_INSTALL_ENV] = "1"
        module = _load_staged_plugin_module(stage_plugin_dir, custom_plugins_root)
        module._ensure_host_runtime_available()  # noqa: SLF001
        importlib.import_module("controller")
        importlib.import_module("racelink.app")
        importlib.import_module("racelink.web")
        _assert_import_under_root("controller", install_target)
        _assert_import_under_root("racelink.app", install_target)
        _assert_import_under_root("racelink.web", install_target)
    finally:
        if previous_target_env is None:
            os.environ.pop(INSTALL_TARGET_ENV, None)
        else:
            os.environ[INSTALL_TARGET_ENV] = previous_target_env
        if previous_force_env is None:
            os.environ.pop(FORCE_INSTALL_ENV, None)
        else:
            os.environ[FORCE_INSTALL_ENV] = previous_force_env

        if sys.path and sys.path[0] == str(custom_plugins_root):
            sys.path.pop(0)
        for module_name in (
            "plugins.racelink_rh_plugin",
            "plugins",
            *created_stub_modules,
            *imported_modules,
        ):
            sys.modules.pop(module_name, None)
        shutil.rmtree(temp_root, ignore_errors=True)


def _validate_stage(stage_root: Path) -> None:
    archive_root = next(path for path in stage_root.iterdir() if path.is_dir())
    stage_plugin_dir = archive_root / PLUGIN_RELATIVE_PATH
    manifest = json.loads((stage_plugin_dir / "manifest.json").read_text("utf-8"))
    dependencies = manifest.get("dependencies", [])
    if dependencies:
        message = f"Offline manifest still declares dependencies: {dependencies}"
        raise RuntimeError(message)

    offline_wheels_dir = stage_plugin_dir / OFFLINE_WHEELS_RELATIVE_PATH
    _validate_offline_wheels(offline_wheels_dir)
    _validate_offline_runtime_install(
        archive_root=archive_root,
        stage_plugin_dir=stage_plugin_dir,
    )


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


class _StubBlueprint:
    """Minimal Blueprint stub for host import validation."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.args = args
        self.kwargs = kwargs

    def route(self, *_args: object, **_kwargs: object) -> object:
        def _decorator(func: object) -> object:
            return func

        return _decorator

    def app_template_filter(self, *_args: object, **_kwargs: object) -> object:
        def _decorator(func: object) -> object:
            return func

        return _decorator


class _StubResponse:
    """Minimal Flask response stub for host import validation."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.args = args
        self.kwargs = kwargs


def _stub_jsonify(*args: object, **kwargs: object) -> dict[str, object]:
    """Return a dict payload that mimics Flask jsonify output for tests."""
    return {"args": args, "kwargs": kwargs}


def _stub_stream_with_context(func: object) -> object:
    """Return the wrapped callable unchanged for import-time validation."""
    return func


def _stub_request_get_json(*_args: object, **_kwargs: object) -> dict[str, object]:
    """Return an empty request payload for import-time validation."""
    return {}


def _stub_render_template(*_args: object, **_kwargs: object) -> str:
    """Return an empty template rendering for import-time validation."""
    return ""


def _build_flask_stub() -> types.ModuleType:
    """Build a lightweight Flask surface used by host import smoke tests."""
    flask = types.ModuleType("flask")
    flask.Blueprint = _StubBlueprint
    flask.Response = _StubResponse
    flask.jsonify = _stub_jsonify
    flask.request = types.SimpleNamespace(get_json=_stub_request_get_json)
    flask.stream_with_context = _stub_stream_with_context
    flask.templating = types.SimpleNamespace(render_template=_stub_render_template)
    return flask


def _build_serial_stub() -> tuple[types.ModuleType, types.ModuleType, types.ModuleType]:
    """Build lightweight pyserial stubs used by host import smoke tests."""
    serial = types.ModuleType("serial")

    class Serial:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.args = args
            self.kwargs = kwargs

        def close(self) -> None:
            return None

    serial.Serial = Serial
    serial.SerialException = Exception

    serial_tools = types.ModuleType("serial.tools")
    list_ports = types.ModuleType("serial.tools.list_ports")
    list_ports.comports = list
    serial_tools.list_ports = list_ports
    return serial, serial_tools, list_ports


def _install_rotorhazard_stubs() -> list[str]:
    """Install lightweight stub modules needed for offline smoke imports."""
    created: list[str] = []
    stub_factories = (
        ("eventmanager", _build_eventmanager_stub),
        ("EventActions", _build_eventactions_stub),
        ("RHUI", _build_rhui_stub),
        ("data_export", _build_data_export_stub),
        ("data_import", _build_data_import_stub),
        ("flask", _build_flask_stub),
    )
    for module_name, factory in stub_factories:
        installed_name = _install_stub(module_name, factory())
        if installed_name is not None:
            created.append(installed_name)

    serial_stub, serial_tools_stub, list_ports_stub = _build_serial_stub()
    for module_name, module in (
        ("serial", serial_stub),
        ("serial.tools", serial_tools_stub),
        ("serial.tools.list_ports", list_ports_stub),
    ):
        installed_name = _install_stub(module_name, module)
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
    _stage_offline_wheels(host_wheel_path, stage_plugin_dir)
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
