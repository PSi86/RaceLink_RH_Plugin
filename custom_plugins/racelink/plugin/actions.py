"""RotorHazard-specific action and quickset adapter methods."""

from __future__ import annotations

import logging
from typing import Any

from EventActions import ActionEffect
from RHUI import UIField, UIFieldSelectOption, UIFieldType

from racelink.domain import RL_FLAG_HAS_BRI, RL_FLAG_POWER_ON, get_specials_config

logger = logging.getLogger(__name__)

type ActionPayload = dict[str, Any]
type RegisterArgs = dict[str, Any]
type OptionMeta = dict[str, Any]
type SelectOptions = list[UIFieldSelectOption]
type UIFields = list[UIField]


class RotorHazardActionsMixin:
    """Provide RotorHazard action registration and dispatch helpers."""

    def registerActions(self, args: RegisterArgs | None = None) -> None:  # noqa: N802
        """Register RaceLink actions with RotorHazard."""
        logger.debug("Registering RaceLink actions")

        register_fn = args.get("register_fn") if args else None
        if register_fn is not None:
            self.controller.action_reg_fn = register_fn
            logger.debug("Saved action register function in RaceLink instance")

        action_reg_fn = getattr(self.controller, "action_reg_fn", None)
        if not action_reg_fn:
            return

        self._register_default_group_action()
        self._register_special_actions()

    def _register_default_group_action(self) -> None:
        """Register the default group control action."""
        if not getattr(self.controller, "uiGroupList", None):
            logger.debug("Skipping default RaceLink action registration: no groups")
            return

        effect_options = self._get_select_options("wled_control", "presetId")
        default_effect = effect_options[0].value if effect_options else "01"
        fields = [
            UIField(
                "rl_action_group",
                "Node Group",
                UIFieldType.SELECT,
                options=self.controller.uiGroupList,
                value=self.controller.uiGroupList[0].value,
            ),
            UIField(
                "rl_action_effect",
                "Color",
                UIFieldType.SELECT,
                options=effect_options,
                value=default_effect,
            ),
            UIField(
                "rl_action_brightness",
                "Brightness",
                UIFieldType.BASIC_INT,
                value=70,
            ),
        ]
        effect = ActionEffect(
            "RaceLink Action",
            self.groupSwitch,
            fields,
            name="gcaction",
        )
        self.controller.action_reg_fn(effect)

    def _register_special_actions(self) -> None:
        """Register capability-driven special actions."""
        specials = get_specials_config(
            context={"rhapi": self.rhapi, "gc": self.controller}
        )
        for cap_key, cap_info in specials.items():
            self._register_special_actions_for_capability(cap_key, cap_info)

    def _register_special_actions_for_capability(
        self,
        cap_key: str,
        cap_info: OptionMeta,
    ) -> None:
        """Register special actions for one capability entry."""
        functions = cap_info.get("functions", []) or []
        if not functions:
            return

        cap_label = cap_info.get("label", cap_key)
        options_by_key = {
            option.get("key"): option
            for option in cap_info.get("options", [])
            if option.get("key") is not None
        }

        for fn_info in functions:
            if fn_info.get("type", "control") != "control":
                continue
            self._register_special_action_variants(
                cap_key=cap_key,
                cap_label=cap_label,
                fn_info=fn_info,
                options_by_key=options_by_key,
            )

    def _register_special_action_variants(
        self,
        *,
        cap_key: str,
        cap_label: str,
        fn_info: OptionMeta,
        options_by_key: dict[str, OptionMeta],
    ) -> None:
        """Register device and/or group variants for one special action."""
        fn_key = str(fn_info.get("key", ""))
        if not fn_key:
            return

        action_meta = {
            "cap_label": cap_label,
            "fn_key": fn_key,
            "fn_label": str(fn_info.get("label") or cap_label),
            "vars_list": [str(var) for var in fn_info.get("vars", []) or []],
        }

        if bool(fn_info.get("unicast")):
            self._register_special_effect(
                action_meta=action_meta,
                cap_key=cap_key,
                options_by_key=options_by_key,
                mode="device",
            )

        if bool(fn_info.get("broadcast")):
            self._register_special_effect(
                action_meta=action_meta,
                cap_key=cap_key,
                options_by_key=options_by_key,
                mode="group",
            )

    def _register_special_effect(
        self,
        *,
        action_meta: OptionMeta,
        cap_key: str,
        options_by_key: dict[str, OptionMeta],
        mode: str,
    ) -> None:
        """Register a single special action effect."""
        fields = self._build_special_fields(
            cap_key=cap_key,
            fn_key=str(action_meta["fn_key"]),
            vars_list=list(action_meta["vars_list"]),
            options_by_key=options_by_key,
            mode=mode,
        )
        if not fields:
            return

        target_suffix = "Device" if mode == "device" else "Group"
        cap_label = str(action_meta["cap_label"])
        fn_label = str(action_meta["fn_label"])
        label_prefix = cap_label if fn_label == cap_label else fn_label
        effect = ActionEffect(
            f"{label_prefix} by {target_suffix}",
            self._make_special_action_handler(str(action_meta["fn_key"]), mode),
            fields,
            name=f"rl_special_{action_meta['fn_key']}_{mode}",
        )
        self.controller.action_reg_fn(effect)

    def _build_special_fields(
        self,
        *,
        cap_key: str,
        fn_key: str,
        vars_list: list[str],
        options_by_key: dict[str, OptionMeta],
        mode: str,
    ) -> UIFields | None:
        """Build UI fields for a special action definition."""
        target_field = self._build_special_target_field(
            cap_key=cap_key,
            fn_key=fn_key,
            mode=mode,
        )
        if target_field is None:
            return None

        fields = [target_field]
        fields.extend(
            self._build_special_variable_fields(
                fn_key=fn_key,
                vars_list=vars_list,
                options_by_key=options_by_key,
            )
        )
        return fields

    def _build_special_target_field(
        self,
        *,
        cap_key: str,
        fn_key: str,
        mode: str,
    ) -> UIField | None:
        """Build the device/group target selector field."""
        if mode == "device":
            options = self.rl_createUiDevList(
                capabilities=[cap_key],
                outputGroups=False,
            )["devices"]
            if not options:
                return None
            return UIField(
                f"rl_special_{fn_key}_device",
                "Device",
                UIFieldType.SELECT,
                options=options,
                value=options[0].value,
            )

        options = self.rl_createUiDevList(
            capabilities=[cap_key],
            outputDevices=False,
        )["groups"]
        if not options:
            return None
        return UIField(
            f"rl_special_{fn_key}_group",
            "Group",
            UIFieldType.SELECT,
            options=options,
            value=options[0].value,
        )

    def _build_special_variable_fields(
        self,
        *,
        fn_key: str,
        vars_list: list[str],
        options_by_key: dict[str, OptionMeta],
    ) -> UIFields:
        """Build per-variable input fields for a special action."""
        fields: UIFields = []
        for variable in vars_list:
            opt_meta = options_by_key.get(variable, {})
            label = str(opt_meta.get("label", variable))
            default_value = opt_meta.get("min", 0)
            select_options = self._get_select_options(fn_key, variable)
            if select_options:
                fields.append(
                    UIField(
                        f"rl_special_{fn_key}_{variable}",
                        label,
                        UIFieldType.SELECT,
                        options=select_options,
                        value=self._resolve_default_select_value(
                            select_options,
                            default_value,
                        ),
                    )
                )
                continue

            fields.append(
                UIField(
                    f"rl_special_{fn_key}_{variable}",
                    label,
                    UIFieldType.BASIC_INT,
                    value=default_value,
                )
            )
        return fields

    def _resolve_default_select_value(
        self,
        select_options: SelectOptions,
        default_value: Any,
    ) -> Any:
        """Resolve the preferred default value from a select option list."""
        default_select = select_options[0].value
        if default_value is None:
            return default_select

        for option in select_options:
            try:
                if int(option.value) == int(default_value):
                    return option.value
            except Exception:
                if str(option.value) == str(default_value):
                    return option.value
        return default_select

    def _make_special_action_handler(
        self,
        fn_key: str,
        mode: str,
    ) -> Any:
        """Create a framework callback for one special action."""

        def _handler(action: ActionPayload, _args: Any = None) -> None:
            self.specialAction(action, fn_key, mode)

        return _handler

    def specialAction(  # noqa: N802
        self,
        action: ActionPayload,
        fn_key: str,
        mode: str,
    ) -> None:
        """Dispatch a special action to the controller."""
        fn_info, cap_key = self._find_special_function(fn_key)
        if fn_info is None:
            logger.warning("specialAction: function not found: %s", fn_key)
            return

        comm_name = fn_info.get("comm")
        if not comm_name:
            logger.warning("specialAction: missing comm function for %s", fn_key)
            return

        comm_fn = getattr(self.controller, comm_name, None)
        if not callable(comm_fn):
            logger.warning("specialAction: comm function missing: %s", comm_name)
            return

        params = self._collect_special_params(action, fn_key, fn_info)
        target_device, target_group = self._resolve_special_target(
            action=action,
            fn_key=fn_key,
            mode=mode,
        )

        logger.debug("RL: specialAction %s (%s)", fn_key, cap_key or "unknown")
        try:
            comm_fn(
                targetDevice=target_device,
                targetGroup=target_group,
                params=params,
            )
        except Exception:
            logger.exception("RL: specialAction failed: %s", fn_key)

    def _find_special_function(
        self,
        fn_key: str,
    ) -> tuple[OptionMeta | None, str | None]:
        """Find a special function definition by key."""
        specials = get_specials_config()
        for cap_key, info in specials.items():
            for fn_info in info.get("functions", []) or []:
                if fn_info.get("key") == fn_key:
                    return fn_info, cap_key
        return None, None

    def _collect_special_params(
        self,
        action: ActionPayload,
        fn_key: str,
        fn_info: OptionMeta,
    ) -> dict[str, Any]:
        """Collect typed parameter values for a special action."""
        params: dict[str, Any] = {}
        for variable in fn_info.get("vars", []) or []:
            option_key = f"rl_special_{fn_key}_{variable}"
            params[str(variable)] = self._coerce_action_value(action.get(option_key, 0))
        return params

    def _resolve_special_target(
        self,
        *,
        action: ActionPayload,
        fn_key: str,
        mode: str,
    ) -> tuple[Any, int | None]:
        """Resolve the target device/group for a special action."""
        if mode == "device":
            target_addr = action.get(f"rl_special_{fn_key}_device")
            target_device = None
            if target_addr:
                target_device = self.controller.getDeviceFromAddress(target_addr)
            return target_device, None

        try:
            target_group = int(action.get(f"rl_special_{fn_key}_group"))
        except Exception:
            target_group = None
        return None, target_group

    def _coerce_action_value(self, value: Any) -> Any:
        """Coerce string-like values to integers when possible."""
        try:
            return int(value)
        except Exception:
            return value

    def nodeSwitch(  # noqa: N802
        self,
        action: ActionPayload,
        _args: Any = None,
    ) -> None:
        """Apply a direct device action or quickset action."""
        if "rl_action_device" in action:
            self._apply_device_action(
                device_addr=str(action["rl_action_device"]),
                brightness=int(action["rl_action_brightness"]),
                preset_id=int(action["rl_action_effect"]),
            )

        if "manual" in action:
            self._apply_manual_device_action()

    def _apply_device_action(
        self,
        *,
        device_addr: str,
        brightness: int,
        preset_id: int,
    ) -> None:
        """Apply control values to a specific device."""
        logger.debug("Action triggered")
        target_device = self.controller.getDeviceFromAddress(device_addr)
        if target_device is None:
            logger.warning("nodeSwitch: device not found: %r", device_addr)
            return

        target_device.brightness = brightness
        target_device.presetId = preset_id
        target_device.flags = self._build_power_flags(brightness)
        self.controller.sendRaceLink(target_device)

    def _apply_manual_device_action(self) -> None:
        """Apply the saved quickset values to a specific device."""
        logger.debug("Manual triggered")
        target_device = self.controller.getDeviceFromAddress(
            self.rhapi.db.option("rl_quickset_device", None)
        )
        if target_device is None:
            logger.warning("nodeSwitch(manual): device not found in DB option")
            return

        brightness = int(self.rhapi.db.option("rl_quickset_brightness", None))
        preset_id = int(self.rhapi.db.option("rl_quickset_effect", None))
        target_device.brightness = brightness
        target_device.presetId = preset_id
        target_device.flags = self._build_power_flags(brightness)
        self.controller.sendRaceLink(target_device)

    def groupSwitch(  # noqa: N802
        self,
        action: ActionPayload,
        _args: Any = None,
    ) -> None:
        """Apply a group action or quickset action."""
        if "rl_action_group" in action:
            logger.debug("Action triggered")
            self._send_group_action(
                group_id=int(action["rl_action_group"]),
                brightness=int(action["rl_action_brightness"]),
                preset_id=int(action["rl_action_effect"]),
            )

        if "manual" in action:
            logger.debug("Manual triggered")
            self._send_group_action(
                group_id=int(self.rhapi.db.option("rl_quickset_group", None)),
                brightness=int(self.rhapi.db.option("rl_quickset_brightness", None)),
                preset_id=int(self.rhapi.db.option("rl_quickset_effect", None)),
            )

    def _send_group_action(
        self,
        *,
        group_id: int,
        brightness: int,
        preset_id: int,
    ) -> None:
        """Send a group control action to the controller."""
        self.controller.sendGroupControl(
            group_id,
            self._build_power_flags(brightness),
            preset_id,
            brightness,
        )

    def _build_power_flags(self, brightness: int) -> int:
        """Build the standard RaceLink control flags for a brightness value."""
        return (RL_FLAG_POWER_ON if brightness > 0 else 0) | RL_FLAG_HAS_BRI
