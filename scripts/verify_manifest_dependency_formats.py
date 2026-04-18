"""Verify which manifest dependency formats are accepted by RHFest."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from sync_racelink_host_dependency import _load_dependency

# Mirrors RHFest v3 dependency validation from
# https://github.com/RotorHazard/rhfest-action/blob/develop/rhfest/const.py
PYPI_PACKAGE_REGEX = re.compile(
    r"^[a-zA-Z0-9.-]+"
    r"(?:\s*(~=|==|!=|<=|>=|<|>|===)\s*\d+(?:\.\d+)*(\.\*)?)?$"
)
GIT_URL_REGEX = re.compile(r"^git\+https://[^\s]+$")

DEFAULT_MANIFEST = Path("custom_plugins/racelink_rh_plugin/manifest.json")
GIT_URL_REFERENCE = "git+https://github.com/PSi86/RaceLink_Host.git@v0.1.0"
PEP508_DIRECT_WHEEL = (
    "racelink-host @ https://example.invalid/racelink_host-1.2.3-py3-none-any.whl"
)

CASES = (
    {
        "name": "current_git_url",
        "dependency": GIT_URL_REFERENCE,
        "expected_valid": True,
        "decision": "Accepted by RHFest, but not used for online installs anymore.",
    },
    {
        "name": "exact_version_specifier",
        "dependency": None,
        "expected_valid": True,
        "decision": "Chosen format for online host installation.",
    },
    {
        "name": "pep508_direct_wheel",
        "dependency": PEP508_DIRECT_WHEEL,
        "expected_valid": False,
        "decision": (
            "Rejected because RHFest does not accept PEP-508 direct references here."
        ),
    },
)


def rhfest_accepts_dependency(dependency: str) -> bool:
    """Return whether the given dependency matches RHFest's current schema."""
    return bool(
        PYPI_PACKAGE_REGEX.fullmatch(dependency) or GIT_URL_REGEX.fullmatch(dependency)
    )


def load_manifest(manifest_path: Path) -> dict:
    """Load the current plugin manifest."""
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _write_line(message: str) -> None:
    """Write one report line to stdout."""
    sys.stdout.write(f"{message}\n")


def main() -> int:
    """Run the spike check and print a compact report."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to the manifest.json file to inspect.",
    )
    args = parser.parse_args()

    current_host = _load_dependency()
    manifest = load_manifest(args.manifest)
    current_dependencies = manifest.get("dependencies", [])
    current_dependency = (
        current_dependencies[0] if current_dependencies else "<missing>"
    )

    _write_line(f"Manifest: {args.manifest}")
    _write_line(f"Current dependency[0]: {current_dependency}")
    _write_line("RHFest dependency format spike:")

    failed = False
    for case in CASES:
        dependency = (
            current_host.manifest_dependency
            if case["name"] == "exact_version_specifier"
            else case["dependency"]
        )
        accepted = rhfest_accepts_dependency(dependency)
        status = "PASS" if accepted == case["expected_valid"] else "FAIL"
        _write_line(
            f"- {status} {case['name']}: accepted={accepted} "
            f"expected={case['expected_valid']} value={dependency}"
        )
        _write_line(f"  {case['decision']}")
        if status == "FAIL":
            failed = True

    _write_line(
        f"Decision: use `{current_host.manifest_dependency}` for online installations."
    )
    _write_line(
        "Direct wheel references stay unsupported until RHFest accepts PEP-508 URLs."
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
