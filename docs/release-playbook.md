# Release Playbook

## Purpose

This playbook is the shortest path for maintainers to publish a new `RaceLink_RH-plugin` release.

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
   create and push the plugin tag
   download the resolved host wheel
   build the offline ZIP
   publish the GitHub release
6. Alternative path: create a GitHub Release directly in the web UI. The same workflow also runs on `release.published` and builds artifacts with the latest published `RaceLink_Host` release.
7. Prefer the Actions UI path when the selected host version should also be persisted back into repository metadata. The release-page path is intended as the convenience build path for an already chosen tag.

## Expected Outputs

- Git tag `v<plugin-version>`
- GitHub release for `RaceLink_RH-plugin`
- Uploaded offline ZIP artifact containing the vendored host runtime

## Failure Hints

- If metadata sync fails, run `py scripts/sync_racelink_host_dependency.py` locally and commit the result.
- If the host wheel download fails, verify the selected or latest `RaceLink_Host` release tag and wheel filename.
- If RHFest fails, inspect `custom_plugins/racelink/manifest.json` and the dependency-format rules in `docs/manifest-dependency-format.md`.
