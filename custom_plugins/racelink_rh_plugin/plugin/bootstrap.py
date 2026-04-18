"""RotorHazard bootstrap for the RaceLink plugin package."""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from typing import Any

from controller import RaceLink_Host
from eventmanager import Evt

from racelink_rh_plugin.plugin.ui import RotorHazardUIAdapter

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _BootstrapState:
    """Keep the latest bootstrap runtime references."""

    rl_app: Any = None
    rl_instance: Any = None


_STATE = _BootstrapState()


def _load_runtime_module(module_name: str) -> Any:
    """Import one RaceLink host module lazily during plugin initialization."""
    return importlib.import_module(module_name)


def _sync_adapter_state(
    rh_adapter: RotorHazardUIAdapter,
    *,
    broadcast_panels: bool = False,
) -> None:
    """Refresh RotorHazard-facing UI bindings after controller state changes."""
    try:
        rh_adapter.sync_rotorhazard_ui(broadcast_panels=broadcast_panels)
    except Exception:
        logger.exception("Unable to synchronize RaceLink RotorHazard bindings")


def _wrap_controller_state_hooks(
    controller: RaceLink_Host,
    rh_adapter: RotorHazardUIAdapter,
) -> None:
    """Augment controller persistence hooks with RotorHazard UI refreshes."""
    original_load_from_db = controller.load_from_db
    original_save_to_db = controller.save_to_db

    def _load_from_db(*args: Any, **kwargs: Any) -> Any:
        result = original_load_from_db(*args, **kwargs)
        _sync_adapter_state(rh_adapter, broadcast_panels=True)
        return result

    def _save_to_db(*args: Any, **kwargs: Any) -> Any:
        result = original_save_to_db(*args, **kwargs)
        _sync_adapter_state(rh_adapter, broadcast_panels=True)
        return result

    controller.load_from_db = _load_from_db
    controller.save_to_db = _save_to_db


def _handle_startup(
    rl_instance: Any,
    rh_adapter: RotorHazardUIAdapter,
    args: Any,
) -> None:
    """Run the RaceLink startup flow after RotorHazard is fully initialized."""
    rl_instance.onStartup(args)
    _sync_adapter_state(rh_adapter, broadcast_panels=True)


def initialize(rhapi: Any) -> None:
    """Initialize the RaceLink host runtime inside RotorHazard."""
    create_runtime = _load_runtime_module("racelink.app").create_runtime
    null_sink_factory = _load_runtime_module("racelink.core").NullSink
    rl_device_group = _load_runtime_module("racelink.domain").RL_DeviceGroup
    state_repository_factory = _load_runtime_module(
        "racelink.state"
    ).get_runtime_state_repository
    register_rl_blueprint = _load_runtime_module("racelink.web").register_rl_blueprint

    state_repository = state_repository_factory()
    controller = RaceLink_Host(
        rhapi,
        "RaceLink_Host",
        "RaceLink",
        state_repository=state_repository,
    )
    rh_adapter = RotorHazardUIAdapter(controller, rhapi)
    controller.rh_adapter = rh_adapter
    controller.rh_source = rh_adapter.source
    controller.action_reg_fn = None
    _wrap_controller_state_hooks(controller, rh_adapter)

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
        data_sink=null_sink_factory(),
    )
    _STATE.rl_app = rl_app
    _STATE.rl_instance = rl_app.rl_instance

    register_rl_blueprint(
        rhapi,
        rl_instance=rl_app.rl_instance,
        state_repository=state_repository,
        services=rl_app.services,
        RL_DeviceGroup=rl_device_group,
        logger=logger,
    )

    rhapi.events.on(Evt.DATA_IMPORT_INITIALIZE, rh_adapter.register_rl_dataimporter)
    rhapi.events.on(Evt.DATA_EXPORT_INITIALIZE, rh_adapter.register_rl_dataexporter)
    rhapi.events.on(Evt.ACTIONS_INITIALIZE, rh_adapter.registerActions)
    rhapi.events.on(
        Evt.STARTUP,
        lambda args: _handle_startup(rl_app.rl_instance, rh_adapter, args),
    )
    rhapi.events.on(Evt.RACE_START, rl_app.rl_instance.onRaceStart)
    rhapi.events.on(Evt.RACE_FINISH, rl_app.rl_instance.onRaceFinish)
    rhapi.events.on(Evt.RACE_STOP, rl_app.rl_instance.onRaceStop)
