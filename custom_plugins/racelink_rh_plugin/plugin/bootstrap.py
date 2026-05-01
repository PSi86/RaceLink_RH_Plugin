"""RotorHazard bootstrap for the RaceLink plugin package."""

from __future__ import annotations

import atexit
import importlib
import logging
from dataclasses import dataclass
from typing import Any

from controller import RaceLink_Host
from eventmanager import Evt
from racelink.domain import state_scope

from .ui import RotorHazardUIAdapter

logger = logging.getLogger(__name__)


def _load_runtime_module(module_name: str) -> Any:
    """Import one RaceLink host module lazily during plugin initialization."""
    return importlib.import_module(module_name)


def _sync_adapter_state(
    rh_adapter: RotorHazardUIAdapter,
    *,
    broadcast_panels: bool = False,
    scopes: Any = None,
) -> None:
    """Refresh RotorHazard-facing UI bindings after controller state changes.

    ``scopes`` is the ``set[str]`` state-scope hint forwarded by the Host via
    :attr:`RaceLink_Host.on_persistence_changed`. When omitted (or ``None``) the
    adapter falls back to a full sync (startup path).
    """
    try:
        rh_adapter.apply_scoped_update(scopes, broadcast_panels=broadcast_panels)
    except Exception:
        logger.exception("Unable to synchronize RaceLink RotorHazard bindings")


@dataclass(slots=True)
class RaceLinkPlugin:
    """Owner of per-plugin runtime references.

    Replaces the module-global ``_STATE`` singleton (plan P2-3). Instances are
    produced by :func:`initialize`; tests and teardown hooks can reach the
    live references through the returned object.
    """

    controller: RaceLink_Host | None = None
    rh_adapter: RotorHazardUIAdapter | None = None
    rl_app: Any = None
    rl_instance: Any = None

    def shutdown(self) -> None:
        """Dispose the host runtime (plan P1-2)."""
        ctrl = self.controller
        if ctrl is None:
            return
        shutdown_fn = getattr(ctrl, "shutdown", None)
        if callable(shutdown_fn):
            try:
                shutdown_fn()
            except Exception:
                logger.exception("RaceLink: host shutdown raised")


def _handle_startup(
    rl_instance: Any,
    rh_adapter: RotorHazardUIAdapter,
    args: Any,
) -> None:
    """Run the RaceLink startup flow after RotorHazard is fully initialized."""
    rl_instance.onStartup(args)
    _sync_adapter_state(rh_adapter, broadcast_panels=True)  # scopes=None → FULL


def initialize(rhapi: Any) -> RaceLinkPlugin:
    """Initialize the RaceLink host runtime inside RotorHazard.

    Returns the :class:`RaceLinkPlugin` owning every instantiated runtime
    reference. The returned object is also stashed on ``rhapi.racelink`` for
    discoverability by RotorHazard's lifecycle callbacks.
    """
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
    rhapi.event_source = rh_adapter.source
    controller.action_reg_fn = None

    # Plan P2-2: use the first-class persistence callback instead of wrapping
    # ``controller.load_from_db`` / ``save_to_db`` at runtime. The callback
    # accepts an optional ``scopes`` set-of-strings so we only refresh the
    # RotorHazard panels that actually depend on the mutated state.
    def _on_persistence_changed(scopes: Any = None) -> None:
        _sync_adapter_state(rh_adapter, broadcast_panels=True, scopes=scopes)

    controller.on_persistence_changed = _on_persistence_changed

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

    # BF3: refresh RH-facing UI when RL-presets change (create / update /
    # delete / duplicate). The Host service exposes a single ``on_changed``
    # callback; the scope token ``PRESETS`` matches the one used for WLED
    # preset reloads, so the existing narrow-refresh path re-registers only
    # the preset-bound quickset field.
    rl_presets_service = rl_app.services.get("rl_presets")
    if rl_presets_service is not None:

        def _on_rl_presets_changed() -> None:
            try:
                _sync_adapter_state(
                    rh_adapter,
                    broadcast_panels=True,
                    scopes={state_scope.PRESETS},
                )
            except Exception:
                logger.exception("RL: failed to refresh RH UI after RL-presets change")

        rl_presets_service.on_changed = _on_rl_presets_changed

    # Same pattern for the scenes service — a SCENES-scoped refresh
    # re-registers the ``RaceLink Scene`` ActionEffect with the current
    # scene list (see ``RotorHazardActionsMixin._register_scene_action``).
    scenes_service = rl_app.services.get("scenes")
    if scenes_service is not None:

        def _on_scenes_changed() -> None:
            try:
                _sync_adapter_state(
                    rh_adapter,
                    broadcast_panels=True,
                    scopes={state_scope.SCENES},
                )
            except Exception:
                logger.exception("RL: failed to refresh RH UI after scenes change")

        scenes_service.on_changed = _on_scenes_changed

    plugin = RaceLinkPlugin(
        controller=controller,
        rh_adapter=rh_adapter,
        rl_app=rl_app,
        rl_instance=rl_app.rl_instance,
    )
    # Expose the live plugin on the host API so teardown hooks or tests can
    # locate it without touching a module global (plan P2-3).
    try:
        rhapi.racelink = plugin
    except Exception:
        logger.debug("RaceLink: could not attach plugin handle to rhapi", exc_info=True)

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
    shutdown_evt = getattr(Evt, "SHUTDOWN", None)
    if shutdown_evt is not None:
        rhapi.events.on(shutdown_evt, lambda _args: plugin.shutdown())

    # Hot-reload / SIGTERM / Ctrl-C do not fire Evt.SHUTDOWN, but still need
    # the serial transport to release its exclusive lock; otherwise the next
    # RH process sees ``Skip busy port ... exclusive lock failed`` on boot.
    # ``plugin.shutdown`` is idempotent, so a double-fire (atexit + event) is
    # safe.
    atexit.register(plugin.shutdown)

    return plugin
