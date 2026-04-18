"""RotorHazard-specific data source helpers."""

from __future__ import annotations

import json
from typing import Any

from racelink.core import EventSource

type HeatSlot = tuple[int, str, str]


class RotorHazardSource(EventSource):
    """Expose RotorHazard race state through the RaceLink event source API."""

    source_name = "rotorhazard"

    def __init__(self, controller: Any, rhapi: Any) -> None:
        """Store controller and RotorHazard API references."""
        self.controller = controller
        self.rhapi = rhapi

    def describe(self) -> dict[str, Any]:
        """Describe the currently attached source."""
        return {
            "name": self.source_name,
            "kind": "rotorhazard",
            "has_rhapi": self.rhapi is not None,
        }

    def snapshot(self) -> dict[str, list[HeatSlot]]:
        """Return a current snapshot of exposed RotorHazard state."""
        return {"current_heat_slots": self.get_current_heat_slot_list()}

    def get_current_heat_slot_list(self) -> list[HeatSlot]:
        """Build a channel/callsign list for the current heat."""
        freq = json.loads(self.rhapi.race.frequencyset.frequencies)
        bands = freq["b"]
        channels = freq["c"]
        race_channels = [
            "--" if band is None else f"{band}{channels[index]}"
            for index, band in enumerate(bands)
        ]

        ctx = self.rhapi._racecontext  # noqa: SLF001
        rhdata = ctx.rhdata
        race = ctx.race
        heat_nodes = rhdata.get_heatNodes_by_heat(race.current_heat) or []

        callsign_by_slot: dict[int, str] = {}
        for heat_node in heat_nodes:
            slot = int(heat_node.node_index)
            pilot_id = heat_node.pilot_id
            pilot = rhdata.get_pilot(pilot_id) if pilot_id else None
            callsign_by_slot[slot] = pilot.callsign if pilot else ""

        channel_count = min(len(race_channels), 8)
        return [
            (index, callsign_by_slot.get(index, ""), race_channels[index])
            for index in range(channel_count)
        ]
