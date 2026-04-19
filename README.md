<!-- PLUGIN BADGES -->
[![RHFest][rhfest-shield]][rhfest-url]

# RaceLink_RH_Plugin

This repository contains the RotorHazard adapter plugin for RaceLink.

The RaceLink web UI and the RaceLink core are provided by `RaceLink_Host`. This repository only contains the RotorHazard-specific integration layer and imports the host runtime from the installed `RaceLink_Host` package.

The dependency-format decision for `custom_plugins/racelink_rh_plugin/manifest.json` is documented in [docs/manifest-dependency-format.md](docs/manifest-dependency-format.md).

## Scope

- RotorHazard adapter package under `custom_plugins/racelink_rh_plugin`
- RotorHazard-specific plugin bootstrap and RH bridges under `custom_plugins/racelink_rh_plugin/plugin`
- Plugin manifest for RotorHazard and RHFest validation
- Development tooling based on [uv] and [pre-commit]
- `uv` dependency on the immutable `racelink-host` GitHub release wheel for the repo-pinned development baseline `0.1.0`

## Distribution

RaceLink has two supported distribution modes:

- Online installation: RotorHazard installs this plugin and resolves the exact `racelink-host==X.Y.Z` runtime dependency from plugin metadata.
- Offline installation: a release ZIP bundles this plugin together with the same resolved `racelink-host` runtime inside `custom_plugins/racelink_rh_plugin/vendor/site-packages`.

That means both installation modes use the same host version for a given release. The difference is only whether the host package is fetched during installation or vendored into the release ZIP.

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
2. Install the project dependencies with `uv`. This creates a virtual environment and installs the repo-pinned `racelink-host` wheel from the matching `RaceLink_Host` GitHub release for development baseline `0.1.0`.

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

- `custom_plugins/racelink_rh_plugin/manifest.json` declares the exact `racelink-host==X.Y.Z` version selected for that release
- `pyproject.toml` uses the same selected host version for local development, but resolves it from the immutable GitHub release wheel URL because `racelink-host` is not published on PyPI
- RHFest validates the manifest format used for the online dependency

### Offline Installation

Use the release ZIP when the target RotorHazard system must install without internet access.

- The ZIP contains `custom_plugins/racelink_rh_plugin/vendor/site-packages`
- That vendored runtime contains the selected `racelink-host` wheel contents plus runtime dependencies such as `pyserial`
- The offline ZIP clears manifest dependencies so RotorHazard does not try to fetch packages during installation

## Version Mapping

- Plugin version: stored in `custom_plugins/racelink_rh_plugin/manifest.json` and bumped per plugin release
- Host development baseline: stored once in `build/deps.json`
- Release builds default to the latest published `RaceLink_Host` release
- Release builds can optionally override the host version manually in the workflow input
- Online install and offline ZIP both use the same resolved host version for that release

## Release Process

The official release flow is the GitHub Actions workflow.

1. Recommended: trigger the release workflow from the GitHub Actions web UI.
2. Choose the target branch and optionally set:
   the plugin version override
   a manual `RaceLink_Host` version override
3. If no host version override is provided, the workflow automatically resolves the latest published `RaceLink_Host` release.
4. The workflow syncs metadata, validates the online dependency shape, runs RHFest, bumps `custom_plugins/racelink_rh_plugin/manifest.json`, validates that the manifest version and release tag match, commits the release metadata, creates the release tag, downloads the resolved host wheel, builds the offline ZIP, and publishes the GitHub release.
5. Do not create releases manually in the GitHub Releases UI. That path is intentionally unsupported because it cannot safely rewrite project files before GitHub generates the source archive.

The short maintainer playbook lives in [docs/release-playbook.md](docs/release-playbook.md).

## License

Distributed under the **MIT** License. See [`LICENSE`](LICENSE) for more information.

<!-- LINK -->
[uv]: https://docs.astral.sh/uv/
[Python]: https://www.python.org/
[pre-commit]: https://pre-commit.com/

[rhfest-shield]: https://github.com/PSi86/RaceLink_RH-plugin/actions/workflows/rhfest.yaml/badge.svg
[rhfest-url]: https://github.com/PSi86/RaceLink_RH-plugin/actions/workflows/rhfest.yaml
