"""Resolve the RaceLink_Host release version for plugin release workflows."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
DEPS_PATH = REPO_ROOT / "build" / "deps.json"
VERSION_PATTERN = re.compile(r"^v?(?P<version>\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)$")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve the RaceLink_Host release version to use for a plugin release."
        )
    )
    parser.add_argument(
        "--host-version",
        default="",
        help=(
            "Optional explicit host version override. "
            "Accepts forms like 0.1.0 or v0.1.0."
        ),
    )
    parser.add_argument(
        "--print",
        choices=("version", "tag", "wheel", "url"),
        default="version",
        dest="print_field",
        help="Which resolved field to print.",
    )
    return parser.parse_args()


def _load_config() -> dict[str, str]:
    raw = json.loads(DEPS_PATH.read_text(encoding="utf-8"))
    host = raw["racelink_host"]
    return {
        "package_name": str(host["package_name"]),
        "github_repository": str(host["github_repository"]),
        "release_selection": str(host.get("release_selection", "latest")),
        "development_version": str(
            host.get("development_version", host.get("version", ""))
        ),
    }


def _normalize_version(raw_version: str) -> str:
    match = VERSION_PATTERN.fullmatch(str(raw_version).strip())
    if match is None:
        message = f"Invalid host version: {raw_version}"
        raise ValueError(message)
    return match.group("version")


def _github_request(url: str) -> urllib.request.Request:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "api.github.com":
        message = f"Unsupported GitHub API URL: {url}"
        raise ValueError(message)
    request = urllib.request.Request(  # noqa: S310
        url=url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "RaceLink_RH_Plugin-release-resolver",
        },
    )
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    return request


def _read_json(url: str) -> object:
    request = _github_request(url)
    with urllib.request.urlopen(request) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _expected_wheel_name(version: str) -> str:
    return f"racelink_host-{version}-py3-none-any.whl"


def _release_has_expected_wheel(release: dict[str, object]) -> bool:
    tag_name = str(release.get("tag_name", "")).strip()
    if not tag_name:
        return False

    version = _normalize_version(tag_name)
    expected_wheel = _expected_wheel_name(version)
    assets = release.get("assets", [])
    if not isinstance(assets, list):
        return False

    for asset in assets:
        if not isinstance(asset, dict):
            continue
        if str(asset.get("name", "")).strip() == expected_wheel:
            return True
    return False


def _fetch_latest_stable_version(repository: str) -> str:
    payload = _read_json(f"https://api.github.com/repos/{repository}/releases/latest")
    if not isinstance(payload, dict):
        message = "GitHub latest-release API returned an unexpected payload."
        raise TypeError(message)
    return _normalize_version(payload["tag_name"])


def _fetch_latest_release_list_version(repository: str) -> str:
    payload = _read_json(f"https://api.github.com/repos/{repository}/releases")
    if not isinstance(payload, list):
        message = "GitHub releases API returned an unexpected payload."
        raise TypeError(message)

    stable_candidate: str | None = None
    prerelease_candidate: str | None = None
    for release in payload:
        if not isinstance(release, dict):
            continue
        if bool(release.get("draft")):
            continue
        if not _release_has_expected_wheel(release):
            continue

        version = _normalize_version(str(release["tag_name"]))
        if bool(release.get("prerelease")):
            prerelease_candidate = prerelease_candidate or version
            continue
        stable_candidate = stable_candidate or version

    if stable_candidate:
        return stable_candidate
    if prerelease_candidate:
        return prerelease_candidate

    message = (
        "No downloadable RaceLink_Host release wheel was found. "
        "Expected a GitHub release asset named like "
        "`racelink_host-X.Y.Z-py3-none-any.whl`."
    )
    raise RuntimeError(message)


def _fetch_latest_version(repository: str) -> str:
    try:
        return _fetch_latest_stable_version(repository)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
    return _fetch_latest_release_list_version(repository)


def _resolve_version(config: dict[str, str], explicit_version: str) -> str:
    if explicit_version.strip():
        return _normalize_version(explicit_version)
    if config["release_selection"] == "latest":
        return _fetch_latest_version(config["github_repository"])
    return _normalize_version(config["development_version"])


def main() -> int:
    """Resolve and print one requested host-release field."""
    args = _parse_args()
    config = _load_config()
    version = _resolve_version(config, args.host_version)
    tag = f"v{version}"
    wheel = f"racelink_host-{version}-py3-none-any.whl"
    url = f"https://github.com/{config['github_repository']}/releases/download/{tag}/{wheel}"

    mapping = {
        "version": version,
        "tag": tag,
        "wheel": wheel,
        "url": url,
    }
    sys.stdout.write(f"{mapping[args.print_field]}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
