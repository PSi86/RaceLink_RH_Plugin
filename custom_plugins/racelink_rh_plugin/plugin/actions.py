"""RotorHazard-specific action and quickset adapter methods."""

from __future__ import annotations

import logging
from typing import Any

from EventActions import ActionEffect
from racelink.domain import get_specials_config
from RHUI import UIField, UIFieldSelectOption, UIFieldType

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
        self._register_scene_action()
        self._register_special_actions()

    def _register_default_group_action(self) -> None:
        """Register the default group control action.

        Phase C: the preset dropdown is backed by ``RLPresetsService`` (stable
        int ids), not by the legacy WLED ``presets_*.json`` list. WLED-presets
        live only in the RaceLink WebUI now.
        """
        if not getattr(self.controller, "uiGroupList", None):
            logger.debug("Skipping default RaceLink action registration: no groups")
            return
        if not getattr(self.controller, "action_reg_fn", None):
            # RotorHazard has not injected the action register fn yet. The
            # initial Evt.ACTIONS_INITIALIZE call does that; scope-limited
            # refreshes before then are intentionally skipped.
            return

        preset_options = self._rl_preset_options_for_action()
        default_preset = preset_options[0].value if preset_options else "0"
        fields = [
            UIField(
                "rl_action_group",
                "Node Group",
                UIFieldType.SELECT,
                options=self.controller.uiGroupList,
                value=self.controller.uiGroupList[0].value,
            ),
            UIField(
                "rl_action_preset",
                "RL Preset",
                UIFieldType.SELECT,
                options=preset_options,
                value=default_preset,
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

    def _rl_preset_options_for_action(self) -> list[UIFieldSelectOption]:
        """Build select-options for the group ActionEffect from the RL preset store.

        Mirrors :meth:`RotorHazardUIAdapter._rl_preset_options` but stays local to the
        actions mixin to keep import graphs simple.
        """
        rl_service = getattr(self.controller, "rl_presets_service", None)
        if rl_service is None:
            return [UIFieldSelectOption("0", "— no RL presets —")]
        try:
            presets = rl_service.list()
        except Exception:
            # swallow-ok: never block action registration on preset-load issues
            logger.exception("RL: failed to load RL preset list for action")
            return [UIFieldSelectOption("0", "— no RL presets —")]
        if not presets:
            return [UIFieldSelectOption("0", "— no RL presets —")]
        return [UIFieldSelectOption(str(p["id"]), p["label"]) for p in presets]

    # ------------------------------------------------------------------
    # Scene action — pattern-identical to gcaction above. One ActionEffect
    # with one scene-picker SELECT field; the operator binds RH events to
    # ``RaceLink Scene`` instances using RotorHazard's standard action UI.
    # ------------------------------------------------------------------

    def _register_scene_action(self) -> None:
        """Register the ``RaceLink Scene`` ActionEffect.

        Single ActionEffect with one SELECT field (``rl_action_scene``). The
        RH operator binds events to scenes through RotorHazard's standard
        action-binding UI; this plugin does not maintain its own
        event→scene table.
        """
        if not getattr(self.controller, "action_reg_fn", None):
            # See note in _register_default_group_action.
            return

        scene_options = self._scene_options_for_action()
        default_scene = scene_options[0].value if scene_options else "0"
        fields = [
            UIField(
                "rl_action_scene",
                "RaceLink Scene",
                UIFieldType.SELECT,
                options=scene_options,
                value=default_scene,
            ),
        ]
        effect = ActionEffect(
            "RaceLink Scene",
            self.applyScene,
            fields,
            name="rl_scene_action",
        )
        self.controller.action_reg_fn(effect)

    def _scene_options_for_action(self) -> list[UIFieldSelectOption]:
        """Pull the scene list for the action's scene-picker SELECT.

        The option ``value`` is the scene's slug ``key`` (stable across
        renames). Falls back to a single placeholder when no scenes exist
        yet so RotorHazard still renders a valid SELECT field.
        """
        scenes_service = getattr(self.controller, "scenes_service", None)
        if scenes_service is None:
            return [UIFieldSelectOption("", "— no scenes —")]
        try:
            scenes = scenes_service.list()
        except Exception:
            # swallow-ok: never block action registration on scene-load issues
            logger.exception("RL: failed to load scene list for action")
            return [UIFieldSelectOption("", "— no scenes —")]
        if not scenes:
            return [UIFieldSelectOption("", "— no scenes —")]
        return [UIFieldSelectOption(str(s["key"]), str(s["label"])) for s in scenes]

    def applyScene(self, action: ActionPayload, _args: Any = None) -> None:  # noqa: N802
        """Run a scene by key when invoked by RotorHazard at event time."""
        scene_key = str(action.get("rl_action_scene") or "").strip()
        if not scene_key:
            logger.debug("applyScene: no scene selected; skipping")
            return
        runner = getattr(self.controller, "runScene", None)
        if not callable(runner):
            logger.warning("applyScene: controller.runScene not wired")
            return
        try:
            result = runner(scene_key)
        except Exception:
            logger.exception("applyScene: runScene(%r) raised", scene_key)
            return
        ok = bool(getattr(result, "ok", False))
        if ok:
            logger.debug("applyScene: scene %r ran ok", scene_key)
        else:
            err = getattr(result, "error", None) or "scene_failed"
            logger.warning("applyScene: scene %r failed: %s", scene_key, err)

    # Phase D rename: ``wled_preset`` (pre-rename ``wled_control``) uses the
    # legacy WLED ``presets_*.json`` list and therefore only makes sense inside
    # the RaceLink WebUI. Skipping it here keeps the RotorHazard action panel
    # free of WLED preset ids.
    _RH_SKIPPED_SPECIAL_FUNCTIONS = frozenset({"wled_preset"})

    def _register_special_actions(self, *, presets_only: bool = False) -> None:
        """Register capability-driven special actions.

        ``presets_only=True`` is a no-op fast path: after Phase C the only
        preset-dependent RH UI (the ``rl_quickset_preset`` select and the
        default group-action preset select) is rebuilt directly in
        ``_register_quickset_preset_only`` / ``_register_default_group_action``
        from ``RLPresetsService``. The remaining special actions
        (``wled_control_advanced``, ``startblock_control``) are unaffected by
        RL-preset mutations, so a ``presets_only`` refresh skips them.
        """
        if not getattr(self.controller, "action_reg_fn", None):
            # See note in _register_default_group_action.
            return
        if presets_only:
            return
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
            # Phase C: some functions are WebUI-only (see _RH_SKIPPED_...).
            if fn_info.get("key") in self._RH_SKIPPED_SPECIAL_FUNCTIONS:
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
            self._register_special_action(
                action_meta=action_meta,
                cap_key=cap_key,
                options_by_key=options_by_key,
                mode="device",
            )

        if bool(fn_info.get("broadcast")):
            self._register_special_action(
                action_meta=action_meta,
                cap_key=cap_key,
                options_by_key=options_by_key,
                mode="group",
            )

    def _register_special_action(
        self,
        *,
        action_meta: OptionMeta,
        cap_key: str,
        options_by_key: dict[str, OptionMeta],
        mode: str,
    ) -> None:
        """Register a single special-action handler.

        Builds an RH ``ActionEffect`` (RotorHazard's API class) — the ``effect`` local
        below is RH terminology, not a WLED effect.
        """
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
        """Apply a direct device action or quickset action.

        Phase C: ``rl_action_preset`` is a stable int preset id from
        ``RLPresetsService``. The host-side ``sendRlPresetById`` resolves it
        and sends ``OPC_CONTROL_ADV`` with the persisted parameter snapshot.
        """
        if "rl_action_device" in action:
            self._apply_device_action(
                device_addr=str(action["rl_action_device"]),
                brightness=int(action["rl_action_brightness"]),
                preset_id=int(action["rl_action_preset"]),
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
        """Apply a RL preset to a specific device by id."""
        logger.debug("Action triggered")
        target_device = self.controller.getDeviceFromAddress(device_addr)
        if target_device is None:
            logger.warning("nodeSwitch: device not found: %r", device_addr)
            return

        ok = self.controller.sendRlPresetById(
            preset_id,
            targetDevice=target_device,
            brightness_override=brightness,
        )
        if not ok:
            logger.warning("nodeSwitch: preset id=%r could not be applied", preset_id)

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
        preset_id = int(self.rhapi.db.option("rl_quickset_preset", None))
        ok = self.controller.sendRlPresetById(
            preset_id,
            targetDevice=target_device,
            brightness_override=brightness,
        )
        if not ok:
            logger.warning(
                "nodeSwitch(manual): preset id=%d could not be applied", preset_id
            )

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
                preset_id=int(action["rl_action_preset"]),
            )

        if "manual" in action:
            logger.debug("Manual triggered")
            self._send_group_action(
                group_id=int(self.rhapi.db.option("rl_quickset_group", None)),
                brightness=int(self.rhapi.db.option("rl_quickset_brightness", None)),
                preset_id=int(self.rhapi.db.option("rl_quickset_preset", None)),
            )

    def _send_group_action(
        self,
        *,
        group_id: int,
        brightness: int,
        preset_id: int,
    ) -> None:
        """Apply a RL preset to a group (broadcast) by id."""
        ok = self.controller.sendRlPresetById(
            preset_id,
            targetGroup=group_id,
            brightness_override=brightness,
        )
        if not ok:
            logger.warning("groupSwitch: preset id=%r could not be applied", preset_id)
