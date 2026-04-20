# Release Playbook

## Purpose

This playbook is the shortest path for maintainers to publish a new `RaceLink_RH_Plugin` release.

## Inputs

- Plugin release version: optional workflow input. If omitted, the workflow increments the manifest patch version.
- Host development baseline: stored in `build/deps.json` for local development metadata.
- Host runtime default: latest published `RaceLink_Host` release.
- Host runtime override: optional workflow input when you need a specific `RaceLink_Host` version for the release.

## Release Steps

1. Confirm that `RaceLink_Host` has already published the wheel you want to use.
2. Open GitHub Actions and run `.github/workflows/offline-release.yaml`.
3. Provide:
   `target_branch`
   optional plugin `version`
   optional `host_version`
4. If `host_version` is empty, the workflow resolves the latest published `RaceLink_Host` release automatically.
5. Wait for the workflow to finish. It will:
   resolve the host version
   sync generated dependency files
   validate online metadata sync
   run the manifest dependency spike
   run RHFest
   bump the plugin version
   validate that `manifest.json` and the release tag match
   commit the release metadata
   create and push the plugin tag
   download the resolved host wheel
   build the offline ZIP
   publish the GitHub release
6. Do not create releases directly in the GitHub Releases UI. That path is intentionally unsupported because it cannot update `manifest.json` before GitHub generates the source archive.

## Expected Outputs

- Git tag `v<plugin-version>`
- GitHub release for `RaceLink_RH_Plugin`
- Uploaded offline ZIP artifact containing the staged `racelink-host` wheel for local installation into the RotorHazard Python environment

## Failure Hints

- If metadata sync fails, run `py scripts/sync_racelink_host_dependency.py` locally and commit the result.
- If the host wheel download fails, verify the selected or latest `RaceLink_Host` release tag and wheel filename.
- If RHFest fails, inspect `custom_plugins/racelink_rh_plugin/manifest.json` and the dependency-format rules in `docs/manifest-dependency-format.md`.
