"""RotorHazard bootstrap for the RaceLink plugin package."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from controller import RaceLink_Host
from eventmanager import Evt
from racelink.app import create_runtime
from racelink.core import NullSink
from racelink.domain import RL_DeviceGroup
from racelink.state import get_runtime_state_repository
from racelink.web import register_rl_blueprint

from .ui import RotorHazardUIAdapter

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _BootstrapState:
    """Keep the latest bootstrap runtime references."""

    rl_app: Any = None
    rl_instance: Any = None


_STATE = _BootstrapState()


def initialize(rhapi: Any) -> None:
    """Initialize the RaceLink host runtime inside RotorHazard."""
    state_repository = get_runtime_state_repository()
    controller = RaceLink_Host(
        rhapi,
        "RaceLink_Host",
        "RaceLink",
        state_repository=state_repository,
    )
    rh_adapter = RotorHazardUIAdapter(controller, rhapi)
    controller.rh_adapter = rh_adapter
    controller.rh_source = rh_adapter.source

    rl_app = create_runtime(
        rhapi,
        state_repository=state_repository,
        controller=controller,
        presets_apply_options=rh_adapter.apply_presets_options,
        integrations={
            "rotorhazard": rhapi,
            "rotorhazard_ui": rh_adapter,
            "rotorhazard_source": rh_adapter.source,
        },
        event_source=rh_adapter.source,
        data_sink=NullSink(),
    )
    _STATE.rl_app = rl_app
    _STATE.rl_instance = rl_app.rl_instance

    register_rl_blueprint(
        rhapi,
        rl_instance=rl_app.rl_instance,
        state_repository=state_repository,
        services=rl_app.services,
        RL_DeviceGroup=RL_DeviceGroup,
        logger=logger,
    )

    rhapi.events.on(Evt.DATA_IMPORT_INITIALIZE, rh_adapter.register_rl_dataimporter)
    rhapi.events.on(Evt.DATA_EXPORT_INITIALIZE, rh_adapter.register_rl_dataexporter)
    rhapi.events.on(Evt.ACTIONS_INITIALIZE, rh_adapter.registerActions)
    rhapi.events.on(Evt.STARTUP, rl_app.rl_instance.onStartup)
    rhapi.events.on(Evt.RACE_START, rl_app.rl_instance.onRaceStart)
    rhapi.events.on(Evt.RACE_FINISH, rl_app.rl_instance.onRaceFinish)
    rhapi.events.on(Evt.RACE_STOP, rl_app.rl_instance.onRaceStop)
