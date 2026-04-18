"""RotorHazard-specific import/export adapter methods."""

from __future__ import annotations

import json
import logging
from typing import Any

from data_export import DataExporter
from data_import import DataImporter
from racelink.state.persistence import dump_records
from RHUI import UIField, UIFieldType

logger = logging.getLogger(__name__)

type ExportPayload = dict[str, str]
type JSONPayload = dict[str, Any]
type RegisterArgs = dict[str, Any]


class RotorHazardDataIOMixin:
    """Provide RotorHazard import/export integration helpers."""

    def register_rl_dataimporter(self, args: RegisterArgs) -> None:
        """Register the RaceLink config importer."""
        importer = DataImporter(
            "RaceLink Config JSON",
            self.rl_import_json,
            None,
            [
                UIField(
                    "rl_import_devices",
                    "Import Devices",
                    UIFieldType.CHECKBOX,
                    value=False,
                ),
                UIField(
                    "rl_import_devgroups",
                    "Import Groups",
                    UIFieldType.CHECKBOX,
                    value=False,
                ),
            ],
        )
        args["register_fn"](importer)

    def register_rl_dataexporter(self, args: RegisterArgs) -> None:
        """Register the RaceLink config exporter."""
        exporter = DataExporter(
            "RaceLink Config JSON",
            self.rl_write_json,
            self.rl_config_json_output,
        )
        args["register_fn"](exporter)

    def rl_write_json(self, data: Any) -> ExportPayload:
        """Serialize exported RaceLink data as JSON."""
        payload = json.dumps(data, indent="\t")
        return {
            "data": payload,
            "encoding": "application/json",
            "ext": "json",
        }

    def rl_config_json_output(self, _rhapi: Any = None) -> JSONPayload:
        """Build the RaceLink configuration export payload."""
        payload: JSONPayload = {
            "help": ["See help tags below current configuration elements"],
            "rl_devices": [obj.__dict__ for obj in self._devices()],
            "rl_groups": [obj.__dict__ for obj in self._groups()],
            "help/rl_devices": ["Device List of known devices"],
            "help/rl_devices/addr": ["MAC of the device without ':' as separator"],
            "help/rl_devices/dev_type": [
                "GATEWAY_REV1:1, NODE_WLED_REV1:10, NODE_WLED_REV3:11, "
                "NODE_WLED_REV4:12, NODE_WLED_REV5:13, "
                "NODE_WLED_STARTBLOCK_REV3:50"
            ],
            "help/rl_devices/name": ["UI: shown name of a device"],
            "help/rl_devices/groupId": [
                "Used to group devices for control. Valid numbers start with "
                "3 (0-2 are reserved for device type based groups)"
            ],
            "help/rl_devices/flags": [
                "bitmask: POWER_ON(0x01), ARM_ON_SYNC(0x02), "
                "HAS_BRI(0x04), FORCE_TT0(0x08), FORCE_REAPPLY(0x10)"
            ],
            "help/rl_devices/presetId": [
                "1-255: WLED preset index / mapping used by the RaceLink WLED Usermod"
            ],
            "help/rl_devices/brightness": [
                "0: off, 1-255:dimming, special function with value 1: IR "
                "Controllers will spam the 'darker' signal to set IR devices "
                "to absolute minimum brightness."
            ],
            "help/rl_groups": [
                "Lookup list for the groupId definitions in the device entries"
            ],
            "help/rl_groups/name": ["UI: shown name of a group"],
            "help/rl_groups/static_group": [
                "0: normal, changeable group, 1: predefined group that will "
                "be read only in UI"
            ],
            "help/rl_groups/dev_type": [
                "0:call all devices set to this group's id. dev_type can "
                "target a specific device type when supported."
            ],
            "help/backup": [
                "If there is an issue with configuration you can create a "
                "clean config based on the example elements. "
                "(delete '_backup' from element name)"
            ],
            "rl_devices_backup": [
                {
                    "addr": "3C84279EBFE4",
                    "dev_type": 10,
                    "name": "WLED 3C84279EBFE4",
                    "groupId": 0,
                    "flags": 1,
                    "presetId": 1,
                    "brightness": 70,
                }
            ],
            "rl_groups_backup": [
                {
                    "name": "All WLED Nodes",
                    "static_group": 1,
                    "dev_type": 0,
                }
            ],
        }
        return payload

    def rl_import_json(
        self,
        _importer_class: Any,
        rhapi: Any,
        source: str | bytes | bytearray | None,
        args: RegisterArgs,
    ) -> bool:
        """Import RaceLink configuration JSON into RotorHazard storage."""
        if not source:
            return False

        try:
            data = json.loads(source)
        except Exception:
            logger.exception("Unable to import file")
            return False

        if args.get("rl_import_devices"):
            logger.debug("Checked device import option")
            devices = data.get("rl_devices")
            if devices is not None:
                logger.debug("Importing RaceLink devices...")
                rhapi.db.option_set("rl_device_config", dump_records(devices))
            else:
                logger.error("JSON contains no RaceLink devices")

        if args.get("rl_import_devgroups"):
            logger.debug("Checked group import option")
            groups = data.get("rl_groups")
            if groups is not None:
                logger.debug("Importing RaceLink groups...")
                rhapi.db.option_set("rl_groups_config", dump_records(groups))
            else:
                logger.error("JSON contains no RaceLink device groups")

        self.controller.load_from_db()
        return True
