# Release Playbook

## Purpose

This playbook is the shortest path for maintainers to publish a new `RaceLink_RH-plugin` release.

## Inputs

- Plugin release version: stored in `custom_plugins/racelink/manifest.json` before tagging.
- Host runtime version: stored in `build/deps.json` and expected to already exist as a published `RaceLink_Host` release tag and wheel.

## Release Steps

1. Confirm `build/deps.json` points to the intended `racelink-host` release.
2. Confirm that `RaceLink_Host` has already published:
   `v<host-version>`
   `racelink_host-<host-version>-py3-none-any.whl`
3. Commit the manifest version you want to ship.
4. Create a git tag `v<plugin-version>` and push it, or create a GitHub release from the web UI with that tag.
5. Wait for `.github/workflows/offline-release.yaml` to finish. It will:
   sync generated dependency files
   validate the tag against the plugin manifest version
   validate online metadata sync
   run the manifest dependency spike
   run RHFest
   download the pinned host wheel
   build the offline ZIP
   publish or update the GitHub release

## Expected Outputs

- Git tag `v<plugin-version>`
- GitHub release for `RaceLink_RH-plugin`
- Uploaded offline ZIP artifact containing the vendored host runtime

## Failure Hints

- If metadata sync fails, run `py scripts/sync_racelink_host_dependency.py` locally and commit the result.
- If the tag check fails, update `custom_plugins/racelink/manifest.json` or recreate the tag so both versions match.
- If the host wheel download fails, verify the tag and wheel filename in the `RaceLink_Host` release.
- If RHFest fails, inspect `custom_plugins/racelink/manifest.json` and the dependency-format rules in `docs/manifest-dependency-format.md`.
