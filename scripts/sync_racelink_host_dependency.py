"""Sync RaceLink_Host dependency metadata into generated project files."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEPS_PATH = REPO_ROOT / "build" / "deps.json"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
MANIFEST_PATH = REPO_ROOT / "custom_plugins" / "racelink" / "manifest.json"
README_PATH = REPO_ROOT / "README.md"
DOCS_PATH = REPO_ROOT / "docs" / "manifest-dependency-format.md"

PYPROJECT_PATTERN = re.compile(r'^dependencies = \["[^"]*"\]$', re.MULTILINE)
README_SCOPE_PATTERN = re.compile(
    r"- `uv` dependency on the released `racelink-host==[^`]+` package"
)
README_INSTALL_PATTERN = re.compile(
    r"installs the pinned `racelink-host==[^`]+` release\."
)
DOCS_DECISION_PATTERN = re.compile(r"`racelink-host==[^`]+`")
DOCS_GIT_ROW_PATTERN = re.compile(
    r"`git\+https://github\.com/PSi86/RaceLink_Host\.git@v[^`]+`"
)
DOCS_SPECIFIER_ROW_PATTERN = re.compile(
    r"`racelink-host==[^`]+` \| pass \| accepted and chosen for online installations"
)


@dataclass(frozen=True)
class HostDependency:
    """Single-source metadata for the host dependency."""

    package_name: str
    version: str

    @property
    def manifest_dependency(self) -> str:
        return f"{self.package_name}=={self.version}"

    @property
    def pyproject_dependency(self) -> str:
        return self.manifest_dependency

    @property
    def host_release_tag(self) -> str:
        return f"v{self.version}"

    @property
    def host_wheel_filename(self) -> str:
        return f"racelink_host-{self.version}-py3-none-any.whl"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sync RaceLink_Host dependency metadata into pyproject.toml, "
            "manifest.json, and related docs."
        )
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail instead of writing when generated files are out of sync.",
    )
    parser.add_argument(
        "--print",
        choices=(
            "checkout-ref",
            "host-wheel-filename",
            "manifest-dependency",
            "pyproject-dependency",
        ),
        dest="print_field",
        help="Print one derived value from build/deps.json and exit.",
    )
    return parser.parse_args()


def _load_dependency(deps_path: Path = DEPS_PATH) -> HostDependency:
    raw = json.loads(deps_path.read_text(encoding="utf-8"))
    host = raw["racelink_host"]
    return HostDependency(
        package_name=str(host["package_name"]),
        version=str(host["version"]),
    )


def _render_pyproject(host: HostDependency) -> str:
    pyproject = PYPROJECT_PATH.read_text(encoding="utf-8")
    replacement = f'dependencies = ["{host.pyproject_dependency}"]'
    return PYPROJECT_PATTERN.sub(replacement, pyproject, count=1)


def _render_manifest(host: HostDependency) -> str:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["dependencies"] = [host.manifest_dependency]
    return json.dumps(manifest, indent=2) + "\n"


def _render_readme(host: HostDependency) -> str:
    readme = README_PATH.read_text(encoding="utf-8")
    updated = README_SCOPE_PATTERN.sub(
        f"- `uv` dependency on the released `racelink-host=={host.version}` package",
        readme,
        count=1,
    )
    return README_INSTALL_PATTERN.sub(
        f"installs the pinned `racelink-host=={host.version}` release.",
        updated,
        count=1,
    )


def _render_docs(host: HostDependency) -> str:
    docs = DOCS_PATH.read_text(encoding="utf-8")
    updated = DOCS_DECISION_PATTERN.sub(
        f"`{host.manifest_dependency}`",
        docs,
        count=1,
    )
    updated = DOCS_GIT_ROW_PATTERN.sub(
        f"`git+https://github.com/PSi86/RaceLink_Host.git@{host.host_release_tag}`",
        updated,
        count=1,
    )
    return DOCS_SPECIFIER_ROW_PATTERN.sub(
        f"`{host.manifest_dependency}` | pass | accepted and chosen for online installations",
        updated,
        count=1,
    )


def sync_generated_files(host: HostDependency, *, write: bool) -> list[str]:
    """Sync all generated files and return the changed file paths."""
    changed: list[str] = []
    sync_steps = (
        (PYPROJECT_PATH, _render_pyproject),
        (MANIFEST_PATH, _render_manifest),
        (README_PATH, _render_readme),
        (DOCS_PATH, _render_docs),
    )
    for path, render_func in sync_steps:
        current = path.read_text(encoding="utf-8")
        rendered = render_func(host)
        if rendered != current:
            changed.append(str(path.relative_to(REPO_ROOT)))
            if write:
                path.write_text(rendered, encoding="utf-8")
    return changed


def main() -> int:
    """Run the dependency sync or print one derived field."""
    args = _parse_args()
    host = _load_dependency()

    if args.print_field == "checkout-ref":
        sys.stdout.write(f"{host.host_release_tag}\n")
        return 0
    if args.print_field == "host-wheel-filename":
        sys.stdout.write(f"{host.host_wheel_filename}\n")
        return 0
    if args.print_field == "manifest-dependency":
        sys.stdout.write(f"{host.manifest_dependency}\n")
        return 0
    if args.print_field == "pyproject-dependency":
        sys.stdout.write(f"{host.pyproject_dependency}\n")
        return 0

    changed = sync_generated_files(host, write=not args.check)
    if args.check and changed:
        sys.stderr.write(
            "RaceLink_Host dependency metadata is out of sync. "
            "Run `py scripts/sync_racelink_host_dependency.py`.\n"
        )
        for path in changed:
            sys.stderr.write(f"- {path}\n")
        return 1

    for path in changed:
        sys.stdout.write(f"updated {path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
