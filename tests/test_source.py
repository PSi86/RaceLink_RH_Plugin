"""Unit tests for the RotorHazard-backed RaceLink event source."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from typing import Any


class RotorHazardSourceTests(unittest.TestCase):
    """Verify heat-slot extraction through the public RotorHazard API."""

    def setUp(self) -> None:
        """Load the source module in isolation without plugin bootstrap imports."""
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
        if spec is None or spec.loader is None:
            msg = "Failed to build import spec for plugin source module"
            raise RuntimeError(msg)
        source_mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = source_mod
        spec.loader.exec_module(source_mod)
        self.RotorHazardSource = source_mod.RotorHazardSource

    def tearDown(self) -> None:
        """Restore the pre-test module registry."""
        sys.modules.clear()
        sys.modules.update(self._saved_modules)

    def test_get_current_heat_slot_list_uses_public_rhapi(self) -> None:
        """Read heat slots via RHAPI wrappers and format channels correctly."""
        slots_by_heat_calls = []
        pilot_lookup_calls = []
        forbidden_racecontext = object()

        def slots_by_heat(heat_id: Any) -> list[types.SimpleNamespace]:
            slots_by_heat_calls.append(heat_id)
            return [
                types.SimpleNamespace(node_index=0, pilot_id=101),
                types.SimpleNamespace(node_index=2, pilot_id=None),
                types.SimpleNamespace(node_index=3, pilot_id=202),
            ]

        def pilot_by_id(pilot_id: Any) -> types.SimpleNamespace | None:
            pilot_lookup_calls.append(pilot_id)
            names = {
                101: types.SimpleNamespace(callsign="Alpha"),
                202: types.SimpleNamespace(callsign="Bravo"),
            }
            return names.get(pilot_id)

        rhapi = types.SimpleNamespace(
            race=types.SimpleNamespace(
                heat=7,
                slots=4,
                frequencyset=types.SimpleNamespace(
                    frequencies='{"b":["R","F",null,"A"],"c":[1,2,3,4]}'
                ),
            ),
            db=types.SimpleNamespace(
                slots_by_heat=slots_by_heat,
                pilot_by_id=pilot_by_id,
            ),
            _racecontext=forbidden_racecontext,
        )
        source = self.RotorHazardSource(controller=object(), rhapi=rhapi)

        result = source.get_current_heat_slot_list()

        self.assertEqual(slots_by_heat_calls, [7])  # noqa: PT009
        self.assertEqual(pilot_lookup_calls, [101, 202])  # noqa: PT009
        self.assertEqual(  # noqa: PT009
            result,
            [
                (0, "Alpha", "R1"),
                (1, "", "F2"),
                (2, "", "--"),
                (3, "Bravo", "A4"),
            ],
        )

    def test_get_current_heat_slot_list_returns_empty_in_practice_mode(self) -> None:
        """Return no slots when RotorHazard is in practice mode."""
        rhapi = types.SimpleNamespace(
            race=types.SimpleNamespace(
                heat=None,
                slots=4,
                frequencyset=types.SimpleNamespace(
                    frequencies='{"b":["R","F",null,"A"],"c":[1,2,3,4]}'
                ),
            ),
            db=types.SimpleNamespace(
                slots_by_heat=lambda _heat_id: self.fail("should not be called"),
                pilot_by_id=lambda _pilot_id: self.fail("should not be called"),
            ),
            _racecontext=object(),
        )
        source = self.RotorHazardSource(controller=object(), rhapi=rhapi)

        self.assertEqual(source.get_current_heat_slot_list(), [])  # noqa: PT009


if __name__ == "__main__":
    unittest.main()
