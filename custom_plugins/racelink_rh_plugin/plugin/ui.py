# ruff: noqa: I001
"""RotorHazard-specific UI adapter."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from RHUI import UIField, UIFieldSelectOption, UIFieldType
from racelink.domain import RL_DeviceGroup, get_dev_type_info, get_specials_config
from .actions import RotorHazardActionsMixin
from .dataio import RotorHazardDataIOMixin
from .source import RotorHazardSource

logger = logging.getLogger(__name__)

type DeviceOptionMap = dict[str, list[UIFieldSelectOption]]


class RotorHazardUIAdapter(RotorHazardActionsMixin, RotorHazardDataIOMixin):
    """Bridge RaceLink configuration and quick actions into RotorHazard UI."""

    def __init__(self, controller: Any, rhapi: Any) -> None:
        """Store controller references and create the RH source adapter."""
        self.controller = controller
        self.rhapi = rhapi
        self.source = RotorHazardSource(controller, rhapi)

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
        """Register the RaceLink settings panel and quick actions."""
        logger.debug("RL: Registering settings UI elements")
        self._ensure_ui_state()
        temp_ui_group_list = [UIFieldSelectOption(0, "New Group")]
        temp_ui_group_list += self.controller.uiDiscoveryGroupList

        self.rhapi.ui.register_panel("rl_settings", "RaceLink Plugin", "settings")
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
                "rl_assignToGroup",
                "Add discovered Devices to Group",
                UIFieldType.SELECT,
                options=temp_ui_group_list,
                value=temp_ui_group_list[0].value,
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
        self.rhapi.ui.register_quickbutton(
            "rl_settings",
            "rl_btn_set_defaults",
            "Save Configuration",
            self.controller.save_to_db,
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
        """Register the RaceLink quickset panel."""
        self._ensure_ui_state()
        if not getattr(self.controller, "uiGroupList", None):
            logger.debug("Skipping RaceLink quickset registration: no groups yet")
            return
        effect_options = self._get_select_options("wled_control", "presetId")
        default_effect = effect_options[0].value if effect_options else "01"
        self.rhapi.ui.register_panel("rl_quickset", "RaceLink Quickset", "run")
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
            self.sync_rotorhazard_ui(broadcast_panels=True)
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
        self.sync_rotorhazard_ui(broadcast_panels=True)

    def _build_new_group_name(self, configured_name: str | None) -> str:
        """Build a timestamped group name for discovery-created groups."""
        base_name = configured_name or "New Group"
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
        return f"{base_name} {timestamp}"

    def get_current_heat_slot_list(self) -> list[tuple[int, str, str]]:
        """Expose current heat slots through the UI adapter."""
        return self.source.get_current_heat_slot_list()
