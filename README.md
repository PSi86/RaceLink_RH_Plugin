# RaceLink_RH_Plugin

[![RHFest][rhfest-shield]][rhfest-url]

The [RotorHazard](https://github.com/RotorHazard/RotorHazard)
adapter plugin for [RaceLink](https://github.com/PSi86/RaceLink_Docs).

This repo contains **only** the RotorHazard-specific integration
layer; the RaceLink core, the WebUI and all services come from the
[`racelink-host`](https://github.com/PSi86/RaceLink_Host) Python
package, which the plugin imports.

## Documentation

📚 **Full documentation lives at
[RaceLink_Docs](https://github.com/PSi86/RaceLink_Docs)**:

* **RotorHazard plugin operator setup** — panels, quickbuttons, race-event integration
* **Online vs. offline installation**
* **Manifest dependency format decision** (ADR-0001)
* **Release flow / playbook**

This README only covers what's specific to *this repository* —
development setup, scope, version mapping. For the operator
guide and the architecture, follow the link above.

## Scope

* RotorHazard adapter package under
  `custom_plugins/racelink_rh_plugin`
* Plugin manifest for RotorHazard + RHFest validation
* Development tooling based on [uv] and [pre-commit]
* `uv` dependency on the immutable `racelink-host` GitHub release
  wheel for the repo-pinned development baseline `0.1.2`

## Architecture (in one paragraph)

The RaceLink core services and the shared WebUI come from
`RaceLink_Host`. This repo only contains the RotorHazard adapter
edge: bootstrap, UI registration, action wiring, event bridges. No
pages or static assets are copied in. No remote-client layer.

For the full picture see
[RotorHazard plugin docs](https://psi86.github.io/RaceLink_Docs/RaceLink_RH_Plugin/).

## Development setup

```bash
git clone https://github.com/PSi86/RaceLink_RH-plugin.git
cd RaceLink_RH-plugin
uv sync                                # creates .venv and installs deps
uv run pre-commit install
uv run pre-commit run --all-files      # full check
```

## Installation modes

| Mode | What happens |
|---|---|
| **Online** | RotorHazard installs the plugin and resolves the host wheel from the immutable Git tag declared in the manifest. |
| **Offline** | The release ZIP bundles the host wheel under `custom_plugins/racelink_rh_plugin/offline_wheels/`. First plugin start installs the bundled wheel locally, then continues. |

For the full installation walkthrough see
[RotorHazard plugin (operator)](https://psi86.github.io/RaceLink_Docs/RaceLink_RH_Plugin/operator-setup/).

## Version mapping

* Plugin version: stored in
  `custom_plugins/racelink_rh_plugin/manifest.json`
* Host development baseline: stored in `build/deps.json`
* Release builds default to the latest published `RaceLink_Host`
  release; an override is available in the workflow input.

For the full release flow see the
[release playbook](https://psi86.github.io/RaceLink_Docs/RaceLink_RH_Plugin/release-playbook/).

## Licence

Distributed under the **MIT** licence. See [`LICENSE`](LICENSE).

[uv]: https://docs.astral.sh/uv/
[pre-commit]: https://pre-commit.com/
[rhfest-shield]: https://github.com/PSi86/RaceLink_RH-plugin/actions/workflows/rhfest.yaml/badge.svg
[rhfest-url]: https://github.com/PSi86/RaceLink_RH-plugin/actions/workflows/rhfest.yaml
