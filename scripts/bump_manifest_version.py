"""Update the RaceLink plugin manifest version for a release."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update custom_plugins/racelink/manifest.json with a new version.",
    )
    parser.add_argument(
        "--manifest",
        default=Path("custom_plugins/racelink/manifest.json"),
        type=Path,
        help="Path to the plugin manifest JSON file.",
    )
    parser.add_argument(
        "--version",
        required=True,
        help="New plugin version to write into the manifest.",
    )
    return parser.parse_args()


def _validate_version(version: str) -> str:
    normalized = str(version).strip()
    if not VERSION_PATTERN.fullmatch(normalized):
        message = (
            "Version must look like semantic versioning, for example 0.1.3 or 0.1.3-rc1"
        )
        raise ValueError(message)
    return normalized


def bump_manifest_version(*, manifest_path: Path, version: str) -> str:
    """Write a new version string into the RaceLink plugin manifest."""
    normalized_version = _validate_version(version)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["version"] = normalized_version
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return normalized_version


def main() -> int:
    """Run the manifest version updater from the command line."""
    args = _parse_args()
    version = bump_manifest_version(
        manifest_path=args.manifest.resolve(),
        version=args.version,
    )
    sys.stdout.write(f"{version}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
