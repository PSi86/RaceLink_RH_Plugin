from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace


class RotorHazardSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_modules = dict(sys.modules)

        racelink_core_mod = types.ModuleType("racelink.core")

        class EventSource:
            pass

        racelink_core_mod.EventSource = EventSource
        sys.modules["racelink.core"] = racelink_core_mod

        source_path = Path(
            "c:/Users/psima/Dev/RaceLink_RH_Plugin/"
            "custom_plugins/racelink_rh_plugin/plugin/source.py"
        )
        module_name = "test_racelink_plugin_source"
        spec = importlib.util.spec_from_file_location(module_name, source_path)
        source_mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = source_mod
        assert spec is not None
        assert spec.loader is not None
        spec.loader.exec_module(source_mod)
        self.RotorHazardSource = source_mod.RotorHazardSource

    def tearDown(self) -> None:
        sys.modules.clear()
        sys.modules.update(self._saved_modules)

    def test_get_current_heat_slot_list_uses_public_rhapi(self) -> None:
        slots_by_heat_calls = []
        pilot_lookup_calls = []
        forbidden_racecontext = object()

        def slots_by_heat(heat_id):
            slots_by_heat_calls.append(heat_id)
            return [
                SimpleNamespace(node_index=0, pilot_id=101),
                SimpleNamespace(node_index=2, pilot_id=None),
                SimpleNamespace(node_index=3, pilot_id=202),
            ]

        def pilot_by_id(pilot_id):
            pilot_lookup_calls.append(pilot_id)
            names = {
                101: SimpleNamespace(callsign="Alpha"),
                202: SimpleNamespace(callsign="Bravo"),
            }
            return names.get(pilot_id)

        rhapi = SimpleNamespace(
            race=SimpleNamespace(
                heat=7,
                slots=4,
                frequencyset=SimpleNamespace(
                    frequencies='{"b":["R","F",null,"A"],"c":[1,2,3,4]}'
                ),
            ),
            db=SimpleNamespace(
                slots_by_heat=slots_by_heat,
                pilot_by_id=pilot_by_id,
            ),
            _racecontext=forbidden_racecontext,
        )
        source = self.RotorHazardSource(controller=object(), rhapi=rhapi)

        result = source.get_current_heat_slot_list()

        self.assertEqual(slots_by_heat_calls, [7])
        self.assertEqual(pilot_lookup_calls, [101, 202])
        self.assertEqual(
            result,
            [
                (0, "Alpha", "R1"),
                (1, "", "F2"),
                (2, "", "--"),
                (3, "Bravo", "A4"),
            ],
        )

    def test_get_current_heat_slot_list_returns_empty_in_practice_mode(self) -> None:
        rhapi = SimpleNamespace(
            race=SimpleNamespace(
                heat=None,
                slots=4,
                frequencyset=SimpleNamespace(
                    frequencies='{"b":["R","F",null,"A"],"c":[1,2,3,4]}'
                ),
            ),
            db=SimpleNamespace(
                slots_by_heat=lambda _heat_id: self.fail("should not be called"),
                pilot_by_id=lambda _pilot_id: self.fail("should not be called"),
            ),
            _racecontext=object(),
        )
        source = self.RotorHazardSource(controller=object(), rhapi=rhapi)

        self.assertEqual(source.get_current_heat_slot_list(), [])


if __name__ == "__main__":
    unittest.main()
