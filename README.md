<!-- PLUGIN BADGES -->
[![RHFest][rhfest-shield]][rhfest-url]

# RaceLink RotorHazard Plugin

This repository contains the RotorHazard adapter plugin for RaceLink.

The RaceLink web UI and the RaceLink core are provided by `RaceLink_Host`. This repository only contains the RotorHazard-specific integration layer and imports the host runtime from the installed `RaceLink_Host` package.

## Scope

- RotorHazard adapter package under `custom_plugins/racelink`
- RotorHazard-specific plugin bootstrap and RH bridges under `custom_plugins/racelink/plugin`
- Plugin manifest for RotorHazard and RHFest validation
- Development tooling based on [uv] and [pre-commit]
- `uv` dependency on `RaceLink_Host` from `PSi86/RaceLink_Host@refactoring_ng_3`

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
2. Install the project dependencies with `uv`. This creates a virtual environment and installs `RaceLink_Host` directly from the `refactoring_ng_3` branch.

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

## License

Distributed under the **MIT** License. See [`LICENSE`](LICENSE) for more information.

<!-- LINK -->
[uv]: https://docs.astral.sh/uv/
[Python]: https://www.python.org/
[pre-commit]: https://pre-commit.com/

[rhfest-shield]: https://github.com/PSi86/RaceLink_RH-plugin/actions/workflows/rhfest.yaml/badge.svg
[rhfest-url]: https://github.com/PSi86/RaceLink_RH-plugin/actions/workflows/rhfest.yaml
