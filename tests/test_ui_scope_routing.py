# ruff: noqa: S101
"""Tests for scope-driven UI refresh routing in the RotorHazard adapter."""

from __future__ import annotations

import importlib
import pathlib
import sys
import types
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[1]
HOST_ROOT = PLUGIN_ROOT.parent / "RaceLink_Host"


def _install_module_stubs() -> None:
    """Install minimal stand-ins for RotorHazard-side runtime modules."""
    _install_eventmanager_stub()
    _install_controller_stub()
    _install_data_export_stub()
    _install_data_import_stub()
    _install_rhui_stub()
    _install_event_actions_stub()


def _install_eventmanager_stub() -> None:
    if "eventmanager" not in sys.modules:
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


def _install_controller_stub() -> None:
    if "controller" not in sys.modules:
        controller = types.ModuleType("controller")
        controller.RaceLink_Host = object
        sys.modules["controller"] = controller


def _install_data_export_stub() -> None:
    if "data_export" not in sys.modules:
        data_export = types.ModuleType("data_export")

        class DataExporter:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                del args, kwargs

        data_export.DataExporter = DataExporter
        sys.modules["data_export"] = data_export


def _install_data_import_stub() -> None:
    if "data_import" not in sys.modules:
        data_import = types.ModuleType("data_import")

        class DataImporter:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                del args, kwargs

        data_import.DataImporter = DataImporter
        sys.modules["data_import"] = data_import


def _install_rhui_stub() -> None:
    if "RHUI" not in sys.modules:
        rhui = types.ModuleType("RHUI")

        class UIField:
            def __init__(
                self,
                name: str,
                label: str,
                field_type: str,
                **kwargs: Any,
            ) -> None:
                self.name = name
                self.label = label
                self.field_type = field_type
                self.kwargs = kwargs

        class UIFieldSelectOption:
            def __init__(self, value: Any, label: str) -> None:
                self.value = value
                self.label = label

        class UIFieldType:
            TEXT = "TEXT"
            SELECT = "SELECT"
            BASIC_INT = "BASIC_INT"

        rhui.UIField = UIField
        rhui.UIFieldSelectOption = UIFieldSelectOption
        rhui.UIFieldType = UIFieldType
        sys.modules["RHUI"] = rhui


def _install_event_actions_stub() -> None:
    if "EventActions" not in sys.modules:
        event_actions = types.ModuleType("EventActions")

        class ActionEffect:
            def __init__(
                self,
                label: str,
                callback: Any,
                fields: list[Any],
                name: str | None = None,
            ) -> None:
                self.label = label
                self.callback = callback
                self.fields = fields
                self.name = name

        event_actions.ActionEffect = ActionEffect
        sys.modules["EventActions"] = event_actions


def _import_adapter() -> Any:
    _install_module_stubs()
    if str(HOST_ROOT) not in sys.path:
        sys.path.insert(0, str(HOST_ROOT))
    if str(PLUGIN_ROOT) not in sys.path:
        sys.path.insert(0, str(PLUGIN_ROOT))
    return importlib.import_module("custom_plugins.racelink_rh_plugin.plugin.ui")


class _FakeDevice:
    def __init__(
        self,
        addr: str,
        name: str,
        dev_type: int = 10,
        group_id: int = 1,
    ) -> None:
        self.addr = addr
        self.name = name
        self.dev_type = dev_type
        self.groupId = group_id


class _FakeGroup:
    def __init__(
        self,
        name: str,
        static_group: int = 0,
        dev_type: int = 0,
    ) -> None:
        self.name = name
        self.static_group = static_group
        self.dev_type = dev_type


class _FakeRepo:
    def __init__(self, items: list[Any]) -> None:
        self._items = list(items)

    def list(self) -> list[Any]:
        return list(self._items)


class _FakeScenesService:
    """Stand-in for SceneService — exposes a static list and a settable hook.

    The ``on_changed`` hook is used by the scope-routing tests to assert that
    the SCENES scope re-registers the ``RaceLink Scene`` ActionEffect.
    """

    def __init__(self, scenes: list[dict] | None = None) -> None:
        self._scenes = list(scenes or [])
        self.on_changed: Any = None

    def list(self) -> list[dict]:
        return [dict(s) for s in self._scenes]


class _FakeController:
    def __init__(self, devices: list[Any], groups: list[Any]) -> None:
        self.device_repository = _FakeRepo(devices)
        self.group_repository = _FakeRepo(groups)
        self.action_reg_fn = MagicMock(name="action_reg_fn")
        self.uiPresetList: list[Any] = []
        self.scenes_service = _FakeScenesService(
            scenes=[
                {"id": 0, "key": "start", "label": "Start"},
                {"id": 1, "key": "finish", "label": "Finish"},
            ]
        )
        self.runScene = MagicMock(name="runScene")

    def save_to_db(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def forceGroups(self, *_args: Any, **_kwargs: Any) -> None:  # noqa: N802
        return None

    def discoverPort(self, *_args: Any, **_kwargs: Any) -> None:  # noqa: N802
        return None


class _FakeFields:
    def __init__(self) -> None:
        self.registered: list[tuple[str, str]] = []

    def register_option(self, field: Any, panel: str) -> None:
        self.registered.append((field.name, panel))


class _FakeUi:
    def __init__(self) -> None:
        self.panels: list[str] = []
        self.quickbuttons: list[tuple[str, str]] = []
        self.broadcasts: list[str] = []

    def register_panel(self, key: str, label: str, context: str) -> None:
        del label, context
        self.panels.append(key)

    def register_quickbutton(
        self,
        panel: str,
        key: str,
        label: str,
        callback: Any,
        args: Any = None,
    ) -> None:
        del label, callback, args
        self.quickbuttons.append((panel, key))

    def broadcast_ui(self, panel: str) -> None:
        self.broadcasts.append(panel)


class _FakeDb:
    def option(self, key: str, default: Any = None) -> Any:
        del key
        return default


class _FakeRhApi:
    def __init__(self) -> None:
        self.db = _FakeDb()
        self.ui = _FakeUi()
        self.fields = _FakeFields()


@dataclass(slots=True)
class _ScopeHarness:
    adapter: Any
    controller: _FakeController
    rhapi: _FakeRhApi
    state_scope: Any

    def registered_field_names(self) -> list[str]:
        return [name for name, _panel in self.rhapi.fields.registered]


def _build_scope_harness() -> _ScopeHarness:
    ui_module = _import_adapter()
    state_scope = sys.modules["racelink.domain"].state_scope
    devices = [
        _FakeDevice("AA00", "Node A"),
        _FakeDevice("AA01", "Node B"),
    ]
    groups = [
        _FakeGroup("Pilots"),
        _FakeGroup("Spectators"),
        _FakeGroup("All WLED Nodes", static_group=1),
    ]
    controller = _FakeController(devices, groups)
    rhapi = _FakeRhApi()
    adapter = ui_module.RotorHazardUIAdapter(controller, rhapi)
    adapter.sync_rotorhazard_ui(broadcast_panels=False)
    rhapi.fields.registered.clear()
    rhapi.ui.quickbuttons.clear()
    rhapi.ui.broadcasts.clear()
    rhapi.ui.panels.clear()
    controller.action_reg_fn.reset_mock()
    return _ScopeHarness(
        adapter=adapter,
        controller=controller,
        rhapi=rhapi,
        state_scope=state_scope,
    )


def test_device_specials_scope_is_noop() -> None:
    """Startblock slot writes must not re-register any RH UI element."""
    harness = _build_scope_harness()
    harness.adapter.apply_scoped_update(
        {harness.state_scope.DEVICE_SPECIALS}, broadcast_panels=True
    )

    assert harness.rhapi.fields.registered == []
    assert harness.rhapi.ui.quickbuttons == []
    assert harness.rhapi.ui.panels == []
    assert harness.rhapi.ui.broadcasts == []
    harness.controller.action_reg_fn.assert_not_called()


def test_none_scope_is_noop() -> None:
    """Explicit-save under ``NONE`` scope must not re-register anything."""
    harness = _build_scope_harness()
    harness.adapter.apply_scoped_update(
        {harness.state_scope.NONE}, broadcast_panels=True
    )

    assert harness.rhapi.fields.registered == []
    assert harness.rhapi.ui.broadcasts == []


def test_groups_scope_refreshes_group_bound_fields_only() -> None:
    """``GROUPS`` scope should refresh only group-bound selects and actions."""
    harness = _build_scope_harness()
    harness.adapter.apply_scoped_update(
        {harness.state_scope.GROUPS}, broadcast_panels=True
    )

    names = harness.registered_field_names()
    assert "rl_assignToGroup" in names
    assert "rl_quickset_group" in names
    assert "rl_device_config" not in names
    assert "rl_groups_config" not in names
    assert "rl_assignToNewGroup" not in names
    assert "rl_quickset_brightness" not in names
    assert harness.rhapi.ui.quickbuttons == []
    assert harness.controller.action_reg_fn.called


def test_presets_scope_refreshes_preset_selectors_only() -> None:
    """``PRESETS`` scope should refresh only preset-backed selectors."""
    harness = _build_scope_harness()
    harness.adapter.apply_scoped_update(
        {harness.state_scope.PRESETS}, broadcast_panels=True
    )

    names = harness.registered_field_names()
    assert "rl_quickset_preset" in names
    assert "rl_quickset_group" not in names
    assert "rl_assignToGroup" not in names


def test_scenes_scope_refreshes_scene_action_only() -> None:
    """``SCENES`` scope should re-register only the RaceLink Scene action.

    Group / device / preset selectors are untouched (scenes_service CRUD has
    no impact on those lists). The action_reg_fn is invoked exactly once for
    the scene action; no field-registry mutations happen.
    """
    harness = _build_scope_harness()
    harness.adapter.apply_scoped_update(
        {harness.state_scope.SCENES}, broadcast_panels=True
    )

    # No quickset / assign-to-group fields touched
    names = harness.registered_field_names()
    assert "rl_quickset_preset" not in names
    assert "rl_quickset_group" not in names
    assert "rl_assignToGroup" not in names

    # The RaceLink Scene ActionEffect was registered (action_reg_fn called).
    assert harness.controller.action_reg_fn.called
    # Its sole field carries the scene key as the SELECT option value.
    registered_action = harness.controller.action_reg_fn.call_args.args[0]
    assert registered_action.name == "rl_scene_action"
    field_names = [f.name for f in registered_action.fields]
    assert field_names == ["rl_action_scene"]
    option_values = [opt.value for opt in registered_action.fields[0].kwargs["options"]]
    assert "start" in option_values
    assert "finish" in option_values


def test_full_scope_reregisters_only_dynamic_after_bootstrap() -> None:
    """Second ``FULL`` sync should touch only dynamic option-backed elements.

    Static fields and quickbuttons are guarded by bootstrap flags after the
    initial sync performed by the harness.
    """
    harness = _build_scope_harness()
    harness.adapter.apply_scoped_update(
        {harness.state_scope.FULL}, broadcast_panels=False
    )

    names = set(harness.registered_field_names())
    assert "rl_device_config" not in names
    assert "rl_groups_config" not in names
    assert "rl_assignToNewGroup" not in names
    assert "rl_quickset_brightness" not in names
    assert "rl_assignToGroup" in names
    assert "rl_quickset_group" in names
    assert "rl_quickset_preset" in names
    # Scenes ActionEffect is part of the dynamic re-register set on FULL.
    rl_scene_action_calls = [
        c
        for c in harness.controller.action_reg_fn.call_args_list
        if c.args and getattr(c.args[0], "name", None) == "rl_scene_action"
    ]
    assert len(rl_scene_action_calls) == 1

    quickbutton_names = [key for _panel, key in harness.rhapi.ui.quickbuttons]
    assert "rl_btn_set_defaults" not in quickbutton_names
    assert "rl_btn_force_groups" not in quickbutton_names
    assert "rl_btn_get_devices" not in quickbutton_names
    assert "rl_run_autodetect" not in quickbutton_names
    assert "run_quickset" not in quickbutton_names


def test_device_membership_scope_does_not_touch_static_ui() -> None:
    """``DEVICE_MEMBERSHIP`` should refresh special actions, not static UI.

    This protects against repeated ``RHUI Redefining ...`` log spam during
    bulk regrouping operations triggered through the WebUI.
    """
    harness = _build_scope_harness()
    harness.adapter.apply_scoped_update(
        {harness.state_scope.DEVICE_MEMBERSHIP}, broadcast_panels=True
    )

    assert harness.registered_field_names() == []
    assert harness.rhapi.ui.quickbuttons == []
    assert harness.controller.action_reg_fn.called


def test_second_sync_is_idempotent_for_static_quickbuttons() -> None:
    """Calling ``sync_rotorhazard_ui`` twice must not duplicate quickbuttons."""
    harness = _build_scope_harness()
    harness.adapter.sync_rotorhazard_ui(broadcast_panels=False)
    quickbutton_names = [key for _panel, key in harness.rhapi.ui.quickbuttons]
    assert quickbutton_names == []
