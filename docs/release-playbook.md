# Release Playbook

## Purpose

This playbook is the shortest path for maintainers to publish a new `RaceLink_RH-plugin` release.

## Inputs

- Plugin release version: optional workflow input. If omitted, the workflow increments the manifest patch version.
- Host runtime version: stored in `build/deps.json` and expected to already exist as a published `RaceLink_Host` release tag and wheel.

## Release Steps

1. Confirm `build/deps.json` points to the intended `racelink-host` release.
2. Confirm that `RaceLink_Host` has already published:
   `v<host-version>`
   `racelink_host-<host-version>-py3-none-any.whl`
3. Trigger `.github/workflows/offline-release.yaml` from GitHub Actions.
4. Provide:
   `target_branch`
   optional `version`
5. Wait for the workflow to finish. It will:
   sync generated dependency files
   validate online metadata sync
   run the manifest dependency spike
   run RHFest
   bump the plugin version
   create and push the plugin tag
   download the pinned host wheel
   build the offline ZIP
   publish the GitHub release

## Expected Outputs

- Git tag `v<plugin-version>`
- GitHub release for `RaceLink_RH-plugin`
- Uploaded offline ZIP artifact containing the vendored host runtime

## Failure Hints

- If metadata sync fails, run `py scripts/sync_racelink_host_dependency.py` locally and commit the result.
- If the host wheel download fails, verify the tag and wheel filename in the `RaceLink_Host` release.
- If RHFest fails, inspect `custom_plugins/racelink/manifest.json` and the dependency-format rules in `docs/manifest-dependency-format.md`.
