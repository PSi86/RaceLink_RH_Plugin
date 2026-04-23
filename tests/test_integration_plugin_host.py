# ruff: noqa: S101
"""Integration tests for plugin bootstrap against the real Host package."""

from __future__ import annotations

import importlib
import pathlib
import sys
import types
from contextlib import contextmanager
from typing import Any
from unittest.mock import Mock

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[1]
HOST_ROOT = PLUGIN_ROOT.parent / "RaceLink_Host"

type EventHandler = Any
type HandlerMap = dict[str, list[EventHandler]]


class _FakeDb:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def option(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def option_set(self, key: str, value: Any) -> None:
        self._store[key] = value


class _FakeUi:
    def __init__(self) -> None:
        self.messages: list[Any] = []
        self.panels: list[Any] = []
        self.blueprints: list[Any] = []

    def message_notify(self, message: Any) -> None:
        self.messages.append(message)

    def broadcast_ui(self, panel: Any) -> None:
        self.panels.append(panel)

    def blueprint_add(self, blueprint: Any) -> None:
        self.blueprints.append(blueprint)

    def register_panel(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs

    def register_quickbutton(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs


class _FakeEvents:
    def __init__(self) -> None:
        self.handlers: HandlerMap = {}

    def on(self, event: str, handler: EventHandler) -> None:
        self.handlers.setdefault(event, []).append(handler)

    def emit(self, event: str, args: Any = None) -> None:
        for handler in list(self.handlers.get(event, [])):
            handler(args)

    def handlers_for(self, event: str) -> list[EventHandler]:
        return list(self.handlers.get(event, []))


class _FakeFields:
    def register_option(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs


class _FakeRhApi:
    """Duck-typed rhapi that satisfies the Host bootstrap at runtime."""

    def __init__(self) -> None:
        self.db = _FakeDb()
        self.ui = _FakeUi()
        self.events = _FakeEvents()
        self.fields = _FakeFields()

    def __(self, text: str) -> str:
        return text


def _ensure_host_import_path() -> None:
    if str(HOST_ROOT) not in sys.path:
        sys.path.insert(0, str(HOST_ROOT))


@contextmanager
def _bootstrap_module_with_stubs() -> Any:
    saved_modules = dict(sys.modules)
    _ensure_host_import_path()

    eventmanager = types.ModuleType("eventmanager")
    eventmanager.Evt = types.SimpleNamespace(
        DATA_IMPORT_INITIALIZE="data_import_initialize",
        DATA_EXPORT_INITIALIZE="data_export_initialize",
        ACTIONS_INITIALIZE="actions_initialize",
        STARTUP="startup",
        RACE_START="race_start",
        RACE_FINISH="race_finish",
        RACE_STOP="race_stop",
    )
    sys.modules["eventmanager"] = eventmanager

    ui_mod = types.ModuleType("custom_plugins.racelink_rh_plugin.plugin.ui")

    class _UiAdapter:
        def __init__(self, controller: Any, rhapi: Any) -> None:
            self.controller = controller
            self.rhapi = rhapi
            self.source = object()
            self.apply_presets_options = Mock()
            self.register_rl_dataimporter = Mock()
            self.register_rl_dataexporter = Mock()
            self.registerActions = Mock()
            self.sync_rotorhazard_ui = Mock()
            self.apply_scoped_update = Mock()

    ui_mod.RotorHazardUIAdapter = _UiAdapter
    sys.modules["custom_plugins.racelink_rh_plugin.plugin.ui"] = ui_mod
    sys.modules.pop("custom_plugins.racelink_rh_plugin.plugin.bootstrap", None)

    try:
        yield importlib.import_module(
            "custom_plugins.racelink_rh_plugin.plugin.bootstrap"
        )
    finally:
        sys.modules.clear()
        sys.modules.update(saved_modules)


def test_initialize_wires_events_callbacks_and_lifecycle() -> None:
    """Bootstrap should wire lifecycle hooks and expose the live plugin state."""
    with _bootstrap_module_with_stubs() as bootstrap:
        rhapi = _FakeRhApi()
        plugin = bootstrap.initialize(rhapi)

        assert plugin is not None
        assert plugin.controller is not None
        assert getattr(rhapi, "racelink", None) is plugin
        assert getattr(rhapi, "event_source", None) is not None

        for event_name in ("startup", "race_start", "race_finish", "race_stop"):
            assert rhapi.events.handlers_for(event_name), f"no handler for {event_name}"

        assert callable(plugin.controller.on_persistence_changed)
        assert hasattr(plugin.controller, "on_gateway_status_changed")

        rhapi.events.emit("race_start", {})

        plugin.shutdown()
        plugin.shutdown()


def test_bootstrap_propagates_host_api_contract() -> None:
    """Bootstrap should still initialize with an optional UI placeholder."""
    with _bootstrap_module_with_stubs() as bootstrap:
        rhapi_no_ui = _FakeRhApi()
        rhapi_no_ui.ui = types.SimpleNamespace(blueprint_add=lambda _blueprint: None)

        plugin = bootstrap.initialize(rhapi_no_ui)

        assert plugin.controller is not None
        plugin.shutdown()
