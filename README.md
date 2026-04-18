<!-- PLUGIN BADGES -->
[![RHFest][rhfest-shield]][rhfest-url]

# RaceLink RotorHazard Plugin

This repository contains the RotorHazard adapter plugin for RaceLink.

The RaceLink web UI and the RaceLink core are provided by `RaceLink_Host`. This repository only contains the RotorHazard-specific integration layer and imports the host runtime from the installed `RaceLink_Host` package.

The dependency-format decision for `custom_plugins/racelink/manifest.json` is documented in [docs/manifest-dependency-format.md](docs/manifest-dependency-format.md).

## Scope

- RotorHazard adapter package under `custom_plugins/racelink`
- RotorHazard-specific plugin bootstrap and RH bridges under `custom_plugins/racelink/plugin`
- Plugin manifest for RotorHazard and RHFest validation
- Development tooling based on [uv] and [pre-commit]
- `uv` dependency on the released `racelink-host==0.1.0` package

## Distribution

RaceLink has two supported distribution modes:

- Online installation: RotorHazard installs this plugin and resolves the pinned `racelink-host==0.1.0` runtime dependency from package metadata.
- Offline installation: a release ZIP bundles this plugin together with the same pinned `racelink-host==0.1.0` runtime inside `custom_plugins/racelink/vendor/site-packages`.

That means both installation modes use the same host version. The difference is only whether the host package is fetched during installation or vendored into the release ZIP.

## Architecture

- This repository contains only the RotorHazard adapter layer.
- The RaceLink web UI comes from `RaceLink_Host`.
- The RaceLink core services come from `RaceLink_Host`.
- The Host runtime and Flask blueprint registration are imported from `RaceLink_Host`.
- No pages or static assets are copied into this repository.
- No separate remote-client layer is introduced here.

## Development

How to set up the development environment.

### Prerequisites

You need the following tools:

- [uv] - A python virtual environment/package manager
- [Python] 3.13 - The programming language

### Installation

1. Clone the repository
2. Install the project dependencies with `uv`. This creates a virtual environment and installs the pinned `racelink-host==0.1.0` release.

```bash
uv sync
```

3. Setup the pre-commit check, you must run this inside the virtual environment

```bash
uv run pre-commit install
```

### Run pre-commit checks

This repository uses the [pre-commit][pre-commit] framework. You can run all configured checks manually with:

```bash
uv run pre-commit run --all-files
```

To run checks only for staged files:

```bash
uv run pre-commit run
```

## Installation Modes

### Online Installation

Use the repository metadata-driven installation when the target RotorHazard system has internet access.

- `custom_plugins/racelink/manifest.json` declares `racelink-host==0.1.0`
- `pyproject.toml` uses the same pinned host version for local development
- RHFest validates the manifest format used for the online dependency

### Offline Installation

Use the release ZIP when the target RotorHazard system must install without internet access.

- The ZIP contains `custom_plugins/racelink/vendor/site-packages`
- That vendored runtime contains the `racelink-host==0.1.0` wheel contents plus runtime dependencies such as `pyserial`
- The offline ZIP clears manifest dependencies so RotorHazard does not try to fetch packages during installation

## Version Mapping

- Plugin version: stored in `custom_plugins/racelink/manifest.json` and bumped per plugin release
- Host version: stored once in `build/deps.json`
- Online install uses the host version from `build/deps.json`
- Offline ZIP vendors the exact same host version from the matching `RaceLink_Host` release wheel

## Release Process

The release workflow is designed so a maintainer can cut a release from this repository without manual file editing.

1. Make sure the pinned host version in `build/deps.json` already points to a published `RaceLink_Host` release.
2. Run the normal repo checks locally if you want a preflight: `py scripts/sync_racelink_host_dependency.py --check` and `py scripts/verify_manifest_dependency_formats.py`.
3. Trigger the GitHub Actions release workflow with the target branch and optional plugin version override.
4. The workflow syncs generated metadata, runs the release validation steps, creates the plugin tag, downloads the matching host wheel, builds the offline ZIP, and publishes the GitHub release.

The short maintainer playbook lives in [docs/release-playbook.md](docs/release-playbook.md).

## License

Distributed under the **MIT** License. See [`LICENSE`](LICENSE) for more information.

<!-- LINK -->
[uv]: https://docs.astral.sh/uv/
[Python]: https://www.python.org/
[pre-commit]: https://pre-commit.com/

[rhfest-shield]: https://github.com/PSi86/RaceLink_RH-plugin/actions/workflows/rhfest.yaml/badge.svg
[rhfest-url]: https://github.com/PSi86/RaceLink_RH-plugin/actions/workflows/rhfest.yaml
