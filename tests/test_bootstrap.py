from __future__ import annotations

import importlib
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import Mock


class BootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_modules = dict(sys.modules)

        eventmanager_mod = types.ModuleType("eventmanager")
        eventmanager_mod.Evt = SimpleNamespace(
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
            def __init__(self, rhapi, name, label, state_repository=None):
                self._rhapi = rhapi
                self.name = name
                self.label = label
                self.state_repository = state_repository
                self.load_from_db = Mock(name="load_from_db")
                self.save_to_db = Mock(name="save_to_db")
                self.onRaceStart = Mock(name="onRaceStart")
                self.onRaceFinish = Mock(name="onRaceFinish")
                self.onRaceStop = Mock(name="onRaceStop")

            def onStartup(self, args):
                return args

        controller_mod.RaceLink_Host = FakeRaceLinkHost
        sys.modules["controller"] = controller_mod

        racelink_app_mod = types.ModuleType("racelink.app")
        self.create_runtime = Mock(
            return_value=SimpleNamespace(
                rl_instance=SimpleNamespace(
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
            return_value=SimpleNamespace()
        )
        sys.modules["racelink.state"] = racelink_state_mod

        racelink_web_mod = types.ModuleType("racelink.web")
        self.register_rl_blueprint = Mock(name="register_rl_blueprint")
        racelink_web_mod.register_rl_blueprint = self.register_rl_blueprint
        sys.modules["racelink.web"] = racelink_web_mod

        ui_mod = types.ModuleType(
            "custom_plugins.racelink_rh_plugin.plugin.ui"
        )

        class FakeRotorHazardUIAdapter:
            def __init__(self, controller, rhapi):
                self.controller = controller
                self.rhapi = rhapi
                self.source = object()
                self.apply_presets_options = Mock(name="apply_presets_options")
                self.register_rl_dataimporter = Mock(name="register_rl_dataimporter")
                self.register_rl_dataexporter = Mock(name="register_rl_dataexporter")
                self.registerActions = Mock(name="registerActions")
                self.sync_rotorhazard_ui = Mock(name="sync_rotorhazard_ui")

        ui_mod.RotorHazardUIAdapter = FakeRotorHazardUIAdapter
        sys.modules["custom_plugins.racelink_rh_plugin.plugin.ui"] = ui_mod

        sys.modules.pop("custom_plugins.racelink_rh_plugin.plugin.bootstrap", None)
        self.bootstrap = importlib.import_module(
            "custom_plugins.racelink_rh_plugin.plugin.bootstrap"
        )

    def tearDown(self) -> None:
        sys.modules.clear()
        sys.modules.update(self._saved_modules)

    def test_initialize_registers_event_source_on_rhapi(self) -> None:
        events = SimpleNamespace(on=Mock(name="events.on"))
        rhapi = SimpleNamespace(events=events)

        self.bootstrap.initialize(rhapi)

        self.assertIsNotNone(rhapi.event_source)
        create_runtime_kwargs = self.create_runtime.call_args.kwargs
        self.assertIs(create_runtime_kwargs["event_source"], rhapi.event_source)


if __name__ == "__main__":
    unittest.main()
