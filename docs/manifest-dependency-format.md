# Manifest Dependency Format Decision

## Decision

For online installations, this repository uses:

`racelink-host==0.1.0`

Direct wheel references in PEP-508 form stay out of `manifest.json` for now.

## Why

The current RHFest v3 validator accepts dependencies only when they match one of these two shapes:

- a package name with an optional version specifier
- a `git+https://...` URL

That rule is implemented in `RotorHazard/rhfest-action` under `rhfest/const.py` and consumed by `rhfest/checks/manifest.py`.
The RHFest README also documents version specifiers as the intended dependency example for `manifest.json`.

## Spike Result

The repo contains two repeatable checks:

- Local check: `py scripts/verify_manifest_dependency_formats.py`
- CI check: `.github/workflows/manifest-dependency-format.yaml`

The spike verifies these cases:

| Candidate | Expected RHFest result | Outcome |
| --- | --- | --- |
| `git+https://github.com/PSi86/RaceLink_Host.git@v0.1.0` | pass | accepted by current RHFest regex |
| `racelink-host==0.1.0` | pass | accepted and chosen for online installations |
| `racelink-host @ https://example.invalid/racelink_host-1.2.3-py3-none-any.whl` | fail | rejected by RHFest |

## Consequence

- Online installations use an exact version specifier.
- Local and CI `uv sync` use the same pinned host version, but consume it through the immutable GitHub release wheel URL in `pyproject.toml`.
- A direct wheel URL must not be used unless RHFest broadens its dependency validation rules.
