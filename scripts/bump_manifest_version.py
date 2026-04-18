"""Update the RaceLink plugin manifest version for a release."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

VERSION_PATTERN = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?P<suffix>[-+][0-9A-Za-z.-]+)?$"
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Update custom_plugins/racelink_rh_plugin/manifest.json "
            "with a release version."
        ),
    )
    parser.add_argument(
        "--manifest",
        default=Path("custom_plugins/racelink_rh_plugin/manifest.json"),
        type=Path,
        help="Path to the plugin manifest JSON file.",
    )
    parser.add_argument(
        "--version",
        default="",
        help=(
            "Explicit plugin version. If omitted, increment the current patch version."
        ),
    )
    return parser.parse_args()


def _normalize_version(version: str) -> str:
    normalized = str(version).strip().removeprefix("v")
    if not normalized:
        return normalized
    if not VERSION_PATTERN.fullmatch(normalized):
        message = (
            "Version must look like semantic versioning, for example 0.1.3 or 0.1.3-rc1"
        )
        raise ValueError(message)
    return normalized


def _increment_version(current_version: str) -> str:
    match = VERSION_PATTERN.fullmatch(current_version)
    if match is None:
        message = f"Current manifest version is not valid semver: {current_version}"
        raise ValueError(message)

    major = int(match.group("major"))
    minor = int(match.group("minor"))
    patch = int(match.group("patch")) + 1
    suffix = match.group("suffix") or ""
    return f"{major}.{minor}.{patch}{suffix}"


def bump_manifest_version(*, manifest_path: Path, version: str) -> str:
    """Write an explicit or auto-incremented version into the plugin manifest."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    current_version = _normalize_version(str(manifest["version"]))
    target_version = _normalize_version(version) or _increment_version(current_version)
    manifest["version"] = target_version
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return target_version


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
