# ruff: noqa: I001
"""RotorHazard-specific UI adapter."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from RHUI import UIField, UIFieldSelectOption, UIFieldType
from racelink.domain import (
    RL_DeviceGroup,
    get_dev_type_info,
    get_specials_config,
    state_scope,
)
from .actions import RotorHazardActionsMixin
from .dataio import RotorHazardDataIOMixin
from .source import RotorHazardSource

logger = logging.getLogger(__name__)

type DeviceOptionMap = dict[str, list[UIFieldSelectOption]]


class RotorHazardUIAdapter(RotorHazardActionsMixin, RotorHazardDataIOMixin):
    """Bridge RaceLink configuration and quick actions into RotorHazard UI.

    Static UI elements bootstrap once on startup:
    ``rl_settings``, ``rl_quickset``, ``rl_device_config``,
    ``rl_groups_config``, ``rl_assignToNewGroup``,
    ``rl_btn_set_defaults``, ``rl_btn_force_groups``,
    ``rl_btn_get_devices``, ``rl_run_autodetect``,
    ``rl_quickset_brightness``, and ``run_quickset``.

    Dynamic UI elements re-register only when their backing data changes:
    ``rl_assignToGroup`` for ``GROUPS``, ``rl_quickset_group`` for
    ``GROUPS``, ``rl_quickset_effect`` for ``EFFECTS``, the default-group
    ``ActionEffect`` for ``GROUPS`` or ``EFFECTS``, and special
    ``ActionEffect`` definitions for ``GROUPS``, ``DEVICES``,
    ``DEVICE_MEMBERSHIP``, or ``EFFECTS``.

    DEVICE_SPECIALS alone does not affect any RH UI element -- it only writes
    the specials dict to the device record. The WebUI re-renders from SSE.

    Implementation: the "once" rows are guarded by the ``_*_bootstrapped``
    flags so that even when ``sync_rotorhazard_ui`` (FULL scope) fires
    repeatedly we don't call ``rhapi.fields.register_option`` again for them.
    RotorHazard otherwise logs each redundant call as ``RHUI Redefining ...``
    which is a hot path on every bulk operation.
    """

    def __init__(self, controller: Any, rhapi: Any) -> None:
        """Store controller references and create the RH source adapter."""
        self.controller = controller
        self.rhapi = rhapi
        self.source = RotorHazardSource(controller, rhapi)
        # Idempotency flags for the static parts of each panel. Each flips
        # to ``True`` on first registration and is never reset while the
        # plugin lives. Dynamic elements (group/effect lists) are re-
        # registered every sync because their option sets change.
        self._settings_panel_bootstrapped = False
        self._quickset_panel_bootstrapped = False

    def _devices(self) -> list[Any]:
        """Return the current device repository contents."""
        return self.controller.device_repository.list()

    def _groups(self) -> list[Any]:
        """Return the current group repository contents."""
        return self.controller.group_repository.list()

    def refresh_ui_state(self) -> None:
        """Refresh cached controller UI lists from current repositories."""
        self.controller.uiDeviceList = self.createUiDevList()
        self.controller.uiGroupList = self.createUiGroupList()
        self.controller.uiDiscoveryGroupList = self.createUiGroupList(
            exclude_static=True
        )

    def sync_rotorhazard_ui(self, *, broadcast_panels: bool = False) -> None:
        """Refresh cached UI state and re-register dependent RotorHazard UI hooks."""
        self.refresh_ui_state()
        self.register_settings()
        self.register_quickset_ui()
        self.registerActions()
        if broadcast_panels:
            self.rhapi.ui.broadcast_ui("settings")
            self.rhapi.ui.broadcast_ui("run")

    def apply_scoped_update(
        self,
        scopes: Any = None,
        *,
        broadcast_panels: bool = False,
    ) -> None:
        """Re-register only the UI elements that depend on the mutated state.

        ``scopes`` is a set of tokens from :mod:`racelink.domain.state_scope`.
        When ``None``/falsy or containing ``FULL``, this delegates to the full
        :meth:`sync_rotorhazard_ui`. ``{NONE}`` is a no-op (pure persistence,
        no user-visible change).
        """
        resolved = (
            state_scope.normalize_scopes(scopes) if scopes else {state_scope.FULL}
        )

        if state_scope.FULL in resolved:
            self.sync_rotorhazard_ui(broadcast_panels=broadcast_panels)
            return
        if resolved == {state_scope.NONE}:
            return

        needs_groups, needs_devices, needs_effects = self._resolve_refresh_flags(
            resolved
        )
        if not any((needs_groups, needs_devices, needs_effects)):
            return

        self.refresh_ui_state()
        touched_settings, touched_run = self._apply_targeted_refreshes(
            needs_groups=needs_groups,
            needs_devices=needs_devices,
            needs_effects=needs_effects,
        )
        self._broadcast_targeted_refreshes(
            broadcast_panels=broadcast_panels,
            touched_settings=touched_settings,
            touched_run=touched_run,
        )

    def _resolve_refresh_flags(
        self,
        resolved: set[str],
    ) -> tuple[bool, bool, bool]:
        """Resolve which dynamic UI sections need rebuilding for one update."""
        needs_groups = state_scope.GROUPS in resolved
        needs_devices = bool(
            resolved & {state_scope.DEVICES, state_scope.DEVICE_MEMBERSHIP}
        )
        needs_effects = state_scope.EFFECTS in resolved
        return needs_groups, needs_devices, needs_effects

    def _apply_targeted_refreshes(
        self,
        *,
        needs_groups: bool,
        needs_devices: bool,
        needs_effects: bool,
    ) -> tuple[bool, bool]:
        """Refresh only the dynamic UI elements that depend on changed state."""
        # DEVICE_SPECIALS alone has no consumer in the RH settings UI today
        # -> intentional no-op.

        touched_settings = False
        touched_run = False
        touched_default_action = False

        if needs_groups:
            self._register_assign_to_group_only()
            self._register_quickset_group_only()
            touched_default_action = True
            touched_settings = True
            touched_run = True

        if needs_effects:
            self._register_quickset_effect_only()
            touched_default_action = True
            touched_settings = True
            touched_run = True

        # ``_register_default_group_action`` embeds both the group list and
        # the effect options, so it must run once when either changed -- but
        # exactly once per update, not twice.
        if touched_default_action:
            self._register_default_group_action()

        # Special actions embed device/group lists and preset options per
        # capability, so they must be refreshed whenever any of these lists
        # change.
        if needs_groups or needs_devices or needs_effects:
            self._register_special_actions()
            touched_settings = True

        return touched_settings, touched_run

    def _broadcast_targeted_refreshes(
        self,
        *,
        broadcast_panels: bool,
        touched_settings: bool,
        touched_run: bool,
    ) -> None:
        """Broadcast RotorHazard panels affected by a targeted refresh."""
        if not broadcast_panels:
            return
        if touched_settings:
            self.rhapi.ui.broadcast_ui("settings")
        if touched_run:
            self.rhapi.ui.broadcast_ui("run")

    def _ensure_ui_state(self) -> None:
        """Ensure controller UI list attributes exist before UI registration."""
        if not hasattr(self.controller, "uiGroupList") or not hasattr(
            self.controller, "uiDiscoveryGroupList"
        ):
            self.refresh_ui_state()

    def _get_select_options(
        self,
        fn_key: str,
        var_key: str,
    ) -> list[UIFieldSelectOption]:
        """Resolve dynamic UI options for one special-action variable."""
        context = {"rhapi": self.rhapi, "gc": self.controller}
        specials = get_specials_config(context=context)
        for cap_info in specials.values():
            for fn_info in cap_info.get("functions", []) or []:
                if fn_info.get("key") != fn_key:
                    continue
                ui_meta = (fn_info.get("ui") or {}).get(var_key, {})
                generator = ui_meta.get("generator")
                if callable(generator):
                    raw_options = generator(context=context)
                    return [
                        UIFieldSelectOption(option["value"], option["label"])
                        for option in raw_options
                    ]
        return []

    def register_settings(self) -> None:
        """Register the RaceLink settings panel, static fields and buttons.

        The panel and its static elements are bootstrapped on the first call
        (and never again). The only dynamic element on this panel,
        ``rl_assignToGroup``, is re-registered on every call because its
        options track ``uiDiscoveryGroupList``.
        """
        logger.debug("RL: Refreshing settings UI (dynamic scope)")
        self._ensure_ui_state()
        if not self._settings_panel_bootstrapped:
            logger.debug("RL: Bootstrapping settings panel (one-shot)")
            self.rhapi.ui.register_panel("rl_settings", "RaceLink Plugin", "settings")
            self._register_static_settings_fields()
            self._register_static_settings_quickbuttons()
            self._settings_panel_bootstrapped = True
        # Dynamic: depends on the current group list.
        self._register_assign_to_group_only()

    def _register_static_settings_fields(self) -> None:
        """Register settings fields that do not depend on runtime state."""
        self.rhapi.fields.register_option(
            UIField(
                "rl_device_config",
                "Device Config",
                UIFieldType.TEXT,
                private=False,
            ),
            "rl_settings",
        )
        self.rhapi.fields.register_option(
            UIField(
                "rl_groups_config",
                "Groups Config",
                UIFieldType.TEXT,
                private=False,
            ),
            "rl_settings",
        )
        self.rhapi.fields.register_option(
            UIField(
                "rl_assignToNewGroup",
                "New Group Name",
                UIFieldType.TEXT,
                private=False,
            ),
            "rl_settings",
        )

    def _register_assign_to_group_only(self) -> None:
        """Register only ``rl_assignToGroup`` (depends on uiDiscoveryGroupList)."""
        self._ensure_ui_state()
        temp_ui_group_list = [UIFieldSelectOption(0, "New Group")]
        temp_ui_group_list += self.controller.uiDiscoveryGroupList
        self.rhapi.fields.register_option(
            UIField(
                "rl_assignToGroup",
                "Add discovered Devices to Group",
                UIFieldType.SELECT,
                options=temp_ui_group_list,
                value=temp_ui_group_list[0].value,
            ),
            "rl_settings",
        )

    def _register_static_settings_quickbuttons(self) -> None:
        """Register the static quickbuttons of the settings panel."""
        self.rhapi.ui.register_quickbutton(
            "rl_settings",
            "rl_btn_set_defaults",
            "Save Configuration",
            self._save_configuration_action,
            args={"manual": True},
        )
        self.rhapi.ui.register_quickbutton(
            "rl_settings",
            "rl_btn_force_groups",
            "Set all Groups",
            self.controller.forceGroups,
            args={"manual": True},
        )
        self.rhapi.ui.register_quickbutton(
            "rl_settings",
            "rl_btn_get_devices",
            "Discover Devices",
            self.discoveryAction,
            args={"manual": True},
        )
        self.rhapi.ui.register_quickbutton(
            "rl_settings",
            "rl_run_autodetect",
            "Detect USB Communicator",
            self.controller.discoverPort,
            args={"manual": True},
        )

    def _save_configuration_action(self, args: Any = None) -> None:
        """Quickbutton handler for "Save Configuration".

        Binding ``self.controller.save_to_db`` directly would invoke it with a
        missing ``scopes`` argument, which falls back to ``{FULL}`` and
        therefore re-registers every static UI element. The Save button only
        flushes state to disk -- nothing visible changes -- so we pass
        ``scopes={NONE}`` to signal "no UI refresh needed".
        """
        self.controller.save_to_db(args or {"manual": True}, scopes={state_scope.NONE})

    def createUiDevList(self) -> list[UIFieldSelectOption]:  # noqa: N802
        """Build an unfiltered device selection list."""
        logger.debug("RL: Creating UI device select options")
        return [
            UIFieldSelectOption(device.addr, device.name) for device in self._devices()
        ]

    def rl_createUiDevList(  # noqa: N802
        self,
        dev_types: list[int] | None = None,
        capabilities: list[str] | None = None,
        outputDevices: bool = True,  # noqa: FBT001, FBT002, N803
        outputGroups: bool = True,  # noqa: FBT001, FBT002, N803
    ) -> DeviceOptionMap:
        """Build filtered device and group option lists for the UI."""
        logger.debug("RL: Creating filtered UI device/group list")
        dev_types_set = (
            {int(device_type) for device_type in dev_types} if dev_types else None
        )
        capability_set = set(capabilities) if capabilities else None
        selected_devices = [
            device
            for device in self._devices()
            if self._matches_device_filters(
                device,
                dev_types_set=dev_types_set,
                capability_set=capability_set,
            )
        ]

        output: DeviceOptionMap = {"devices": [], "groups": []}
        if outputDevices:
            output["devices"] = self._build_device_options(selected_devices)
        if outputGroups:
            output["groups"] = self._build_group_options(
                selected_devices,
                capability_set=capability_set,
            )
        return output

    def _matches_device_filters(
        self,
        device: Any,
        *,
        dev_types_set: set[int] | None,
        capability_set: set[str] | None,
    ) -> bool:
        """Return whether one device matches the requested filters."""
        if (
            dev_types_set
            and int(getattr(device, "dev_type", 0) or 0) not in dev_types_set
        ):
            return False
        if capability_set:
            caps = set(
                get_dev_type_info(getattr(device, "dev_type", 0)).get("caps", [])
            )
            if not capability_set.issubset(caps):
                return False
        return True

    def _build_device_options(
        self,
        selected_devices: list[Any],
    ) -> list[UIFieldSelectOption]:
        """Build device select options from filtered devices."""
        return [
            UIFieldSelectOption(device.addr, device.name) for device in selected_devices
        ]

    def _build_group_options(
        self,
        selected_devices: list[Any],
        *,
        capability_set: set[str] | None,
    ) -> list[UIFieldSelectOption]:
        """Build group select options from filtered devices."""
        group_ids = {
            int(getattr(device, "groupId", 0) or 0) for device in selected_devices
        }
        group_options: list[UIFieldSelectOption] = []
        for index, group in enumerate(self._groups()):
            group_name = str(getattr(group, "name", ""))
            if self._is_all_wled_group(group):
                if capability_set and "WLED" not in capability_set:
                    continue
                if selected_devices:
                    group_options.append(UIFieldSelectOption(255, group_name))
                continue
            if index in group_ids:
                group_options.append(UIFieldSelectOption(index, group_name))
        return group_options

    def _is_all_wled_group(self, group: Any) -> bool:
        """Return whether a group is the synthetic all-WLED group."""
        return bool(group.static_group) and str(getattr(group, "name", "")) == (
            "All WLED Nodes"
        )

    def createUiGroupList(  # noqa: N802
        self,
        exclude_static: bool = False,  # noqa: FBT001, FBT002
    ) -> list[UIFieldSelectOption]:
        """Build the selectable group list for the UI."""
        logger.debug("RL: Creating UI group select options")
        group_options: list[UIFieldSelectOption] = []
        for index, group in enumerate(self._groups()):
            if exclude_static and group.static_group != 0:
                continue
            value = 255 if self._is_all_wled_group(group) else index
            group_options.append(UIFieldSelectOption(value, group.name))
        return group_options

    def register_quickset_ui(self) -> None:
        """Register the quickset panel and its elements.

        Panel + static elements (brightness, Apply button) are bootstrapped
        once. The two option-list-backed fields are re-registered every call
        because their options track ``uiGroupList`` / ``uiEffectList``.
        """
        self._ensure_ui_state()
        if not getattr(self.controller, "uiGroupList", None):
            logger.debug("Skipping RaceLink quickset registration: no groups yet")
            return
        if not self._quickset_panel_bootstrapped:
            logger.debug("RL: Bootstrapping quickset panel (one-shot)")
            self.rhapi.ui.register_panel("rl_quickset", "RaceLink Quickset", "run")
            self._register_static_quickset_fields()
            self._quickset_panel_bootstrapped = True
        # Dynamic: depend on the current group / preset lists.
        self._register_quickset_group_only()
        self._register_quickset_effect_only()

    def _register_quickset_group_only(self) -> None:
        """Register only ``rl_quickset_group`` (depends on uiGroupList)."""
        self._ensure_ui_state()
        if not getattr(self.controller, "uiGroupList", None):
            return
        self.rhapi.fields.register_option(
            UIField(
                "rl_quickset_group",
                "Node Group",
                UIFieldType.SELECT,
                options=self.controller.uiGroupList,
                value=self.controller.uiGroupList[0].value,
            ),
            "rl_quickset",
        )

    def _register_quickset_effect_only(self) -> None:
        """Register only ``rl_quickset_effect`` (depends on WLED preset options)."""
        effect_options = self._get_select_options("wled_control", "presetId")
        default_effect = effect_options[0].value if effect_options else "01"
        self.rhapi.fields.register_option(
            UIField(
                "rl_quickset_effect",
                "Color",
                UIFieldType.SELECT,
                options=effect_options,
                value=default_effect,
            ),
            "rl_quickset",
        )

    def _register_static_quickset_fields(self) -> None:
        """Register the brightness field and the Apply quickbutton (no data binding)."""
        self.rhapi.fields.register_option(
            UIField(
                "rl_quickset_brightness",
                "Brightness",
                UIFieldType.BASIC_INT,
                value=70,
            ),
            "rl_quickset",
        )
        self.rhapi.ui.register_quickbutton(
            "rl_quickset",
            "run_quickset",
            "Apply",
            self.groupSwitch,
            args={"manual": True},
        )

    def apply_presets_options(self, parsed: list[tuple[int, str]] | None) -> None:
        """Apply preset metadata loaded by the host package."""
        if not parsed:
            self.controller.uiEffectList = [
                UIFieldSelectOption("0", "No presets.json found")
            ]
        else:
            self.controller.uiEffectList = [
                UIFieldSelectOption(str(preset_id), name) for preset_id, name in parsed
            ]
        try:
            self.apply_scoped_update({state_scope.EFFECTS}, broadcast_panels=True)
        except Exception:
            logger.exception("Unable to refresh RaceLink quickset UI")

    def discoveryAction(self, _args: Any = None) -> None:  # noqa: N802
        """Discover devices and optionally create a new target group."""
        group_selected = int(self.rhapi.db.option("rl_assignToGroup", None))
        new_group_name = self.rhapi.db.option("rl_assignToNewGroup", None)

        if group_selected == 0:
            new_group_name = self._build_new_group_name(new_group_name)
            group_selected = len(self._groups())

        num_found = self.controller.getDevices(
            groupFilter=0,
            addToGroup=group_selected,
        )
        if num_found <= 0 or group_selected != len(self._groups()):
            return

        self.controller.group_repository.append(RL_DeviceGroup(new_group_name))
        # Discovery affects the group list (we just added one) and, if nodes
        # responded, the device membership too. Narrower than FULL so the
        # static parts of the panels are not re-registered.
        self.apply_scoped_update(
            {state_scope.GROUPS, state_scope.DEVICE_MEMBERSHIP},
            broadcast_panels=True,
        )

    def _build_new_group_name(self, configured_name: str | None) -> str:
        """Build a timestamped group name for discovery-created groups."""
        base_name = configured_name or "New Group"
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
        return f"{base_name} {timestamp}"

    def get_current_heat_slot_list(self) -> list[tuple[int, str, str]]:
        """Expose current heat slots through the UI adapter."""
        return self.source.get_current_heat_slot_list()
