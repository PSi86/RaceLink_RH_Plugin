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
MANIFEST_PATH = REPO_ROOT / "custom_plugins" / "racelink_rh_plugin" / "manifest.json"
README_PATH = REPO_ROOT / "README.md"
DOCS_PATH = REPO_ROOT / "docs" / "manifest-dependency-format.md"

PYPROJECT_PATTERN = re.compile(r'^dependencies = \["[^"]*"\]$', re.MULTILINE)
README_SCOPE_PATTERN = re.compile(
    r"- `uv` dependency on the immutable `racelink-host` GitHub release wheel for .*"
)
README_INSTALL_PATTERN = re.compile(
    r"installs the .* `racelink-host` wheel from the matching "
    r"`RaceLink_Host` GitHub release\."
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
    github_repository: str
    version: str

    @property
    def manifest_dependency(self) -> str:
        """Return the manifest dependency string for the selected host version."""
        return f"{self.package_name}=={self.version}"

    @property
    def pyproject_dependency(self) -> str:
        """Return the editable development dependency entry for pyproject."""
        return f"{self.package_name} @ {self.host_wheel_url}"

    @property
    def host_release_tag(self) -> str:
        """Return the Git tag name for the selected host version."""
        return f"v{self.version}"

    @property
    def host_wheel_filename(self) -> str:
        """Return the wheel filename for the selected host version."""
        return f"racelink_host-{self.version}-py3-none-any.whl"

    @property
    def host_wheel_url(self) -> str:
        """Return the immutable GitHub release wheel URL for the host version."""
        return (
            f"https://github.com/{self.github_repository}/releases/download/"
            f"{self.host_release_tag}/{self.host_wheel_filename}"
        )


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
        "--host-version",
        default="",
        help=(
            "Optional explicit host version override "
            "used for rendering generated files."
        ),
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
        github_repository=str(host["github_repository"]),
        version=str(host.get("development_version", host.get("version", ""))),
    )


def _with_version(host: HostDependency, version: str) -> HostDependency:
    return HostDependency(
        package_name=host.package_name,
        github_repository=host.github_repository,
        version=str(version),
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
        "- `uv` dependency on the immutable `racelink-host` GitHub release wheel "
        f"for the repo-pinned development baseline `{host.version}`",
        readme,
        count=1,
    )
    return README_INSTALL_PATTERN.sub(
        f"installs the repo-pinned `racelink-host` wheel from the matching "
        "`RaceLink_Host` GitHub release for development baseline "
        f"`{host.version}`.",
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
        f"`{host.manifest_dependency}` | pass | accepted and chosen "
        "for online installations",
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
    if args.host_version.strip():
        host = _with_version(host, args.host_version.strip().removeprefix("v"))

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
