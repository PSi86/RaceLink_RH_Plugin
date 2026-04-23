"""Bootstrap integration tests for the RaceLink RotorHazard plugin."""

from __future__ import annotations

import importlib
import sys
import types
import unittest
from typing import Any
from unittest.mock import Mock


class BootstrapTests(unittest.TestCase):
    """Verify bootstrap wiring against the expected host/plugin contract."""

    def setUp(self) -> None:
        """Prepare isolated module stubs for bootstrap imports."""
        self._saved_modules = dict(sys.modules)

        eventmanager_mod = types.ModuleType("eventmanager")
        eventmanager_mod.Evt = types.SimpleNamespace(
            DATA_IMPORT_INITIALIZE="data_import_initialize",
            DATA_EXPORT_INITIALIZE="data_export_initialize",
            ACTIONS_INITIALIZE="actions_initialize",
            STARTUP="startup",
            RACE_START="race_start",
            RACE_FINISH="race_finish",
            RACE_STOP="race_stop",
        )
        sys.modules["eventmanager"] = eventmanager_mod

        controller_mod = types.ModuleType("controller")

        class FakeRaceLinkHost:
            def __init__(
                self,
                rhapi: Any,
                name: str,
                label: str,
                state_repository: Any = None,
            ) -> None:
                self._rhapi = rhapi
                self.name = name
                self.label = label
                self.state_repository = state_repository
                self.load_from_db = Mock(name="load_from_db")
                self.save_to_db = Mock(name="save_to_db")
                self.onRaceStart = Mock(name="onRaceStart")
                self.onRaceFinish = Mock(name="onRaceFinish")
                self.onRaceStop = Mock(name="onRaceStop")

            def onStartup(self, args: Any) -> Any:  # noqa: N802
                return args

        controller_mod.RaceLink_Host = FakeRaceLinkHost
        sys.modules["controller"] = controller_mod

        racelink_app_mod = types.ModuleType("racelink.app")
        self.create_runtime = Mock(
            return_value=types.SimpleNamespace(
                rl_instance=types.SimpleNamespace(
                    onStartup=Mock(name="onStartup"),
                    onRaceStart=Mock(name="onRaceStart"),
                    onRaceFinish=Mock(name="onRaceFinish"),
                    onRaceStop=Mock(name="onRaceStop"),
                ),
                services={"startblock": object()},
            )
        )
        racelink_app_mod.create_runtime = self.create_runtime
        sys.modules["racelink.app"] = racelink_app_mod

        racelink_core_mod = types.ModuleType("racelink.core")

        class NullSink:
            pass

        racelink_core_mod.NullSink = NullSink
        sys.modules["racelink.core"] = racelink_core_mod

        racelink_domain_mod = types.ModuleType("racelink.domain")
        racelink_domain_mod.RL_DeviceGroup = object
        sys.modules["racelink.domain"] = racelink_domain_mod

        racelink_state_mod = types.ModuleType("racelink.state")
        racelink_state_mod.get_runtime_state_repository = Mock(
            return_value=types.SimpleNamespace()
        )
        sys.modules["racelink.state"] = racelink_state_mod

        racelink_web_mod = types.ModuleType("racelink.web")
        self.register_rl_blueprint = Mock(name="register_rl_blueprint")
        racelink_web_mod.register_rl_blueprint = self.register_rl_blueprint
        sys.modules["racelink.web"] = racelink_web_mod

        ui_mod = types.ModuleType("custom_plugins.racelink_rh_plugin.plugin.ui")

        class FakeRotorHazardUIAdapter:
            def __init__(self, controller: Any, rhapi: Any) -> None:
                self.controller = controller
                self.rhapi = rhapi
                self.source = object()
                self.apply_presets_options = Mock(name="apply_presets_options")
                self.register_rl_dataimporter = Mock(name="register_rl_dataimporter")
                self.register_rl_dataexporter = Mock(name="register_rl_dataexporter")
                self.registerActions = Mock(name="registerActions")
                self.sync_rotorhazard_ui = Mock(name="sync_rotorhazard_ui")
                self.apply_scoped_update = Mock(name="apply_scoped_update")

        ui_mod.RotorHazardUIAdapter = FakeRotorHazardUIAdapter
        sys.modules["custom_plugins.racelink_rh_plugin.plugin.ui"] = ui_mod

        sys.modules.pop("custom_plugins.racelink_rh_plugin.plugin.bootstrap", None)
        self.bootstrap = importlib.import_module(
            "custom_plugins.racelink_rh_plugin.plugin.bootstrap"
        )

    def tearDown(self) -> None:
        """Restore the original module state after each test."""
        sys.modules.clear()
        sys.modules.update(self._saved_modules)

    def test_initialize_registers_event_source_on_rhapi(self) -> None:
        """Expose the adapter source through the host API event-source slot."""
        events = types.SimpleNamespace(on=Mock(name="events.on"))
        rhapi = types.SimpleNamespace(events=events)

        self.bootstrap.initialize(rhapi)

        self.assertIsNotNone(rhapi.event_source)  # noqa: PT009
        create_runtime_kwargs = self.create_runtime.call_args.kwargs
        self.assertIs(  # noqa: PT009
            create_runtime_kwargs["event_source"],
            rhapi.event_source,
        )


if __name__ == "__main__":
    unittest.main()
