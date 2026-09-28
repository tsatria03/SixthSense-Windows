---
name: project_linux_release_plan
description: "PLANNED 2026-09-28. releaser.py releases the Linux build too: each system zips its own build (SixthSense-Win-<v>.zip, SixthSense-Linux-<v>.zip), and one release carries both, the second system adding its zip to the release the first made. Never replaces an asset."
metadata:
  type: project
---

**Status: planned 2026-09-28.** Asked for by tunmi13productions: "fix the releaser too", after [[project_linux_build_plan]] (finished the same day). Builds on [[project_release_tooling_plan]].

## Found first
- PyInstaller builds only for the system it runs on, so one release needs two runs: one on Windows, one in WSL. The releaser only knew Windows: the zip name `SixthSense-Win-<version>.zip`, and an upload step that stops when the GitHub release already exists.
- The dev's WSL sees the same checkout on `D:` (`/mnt/d/...`), and git there reads it as clean (`core.filemode` false, `* text=auto`), so the check step passes in WSL. No pull is needed between the two runs: it is one working copy.
- `dist/` is gitignored, and each system builds into its own folder (`dist/SixthSense-Windows`, `dist/SixthSense-Linux`).
- The GitHub CLI is not installed in WSL: `sudo apt install gh`, then `gh auth login`, once.

## The plan
- **Each system zips its own build**: `dist/SixthSense-Win-<version>.zip` as now, and `dist/SixthSense-Linux-<version>.zip`, which extracts to a `SixthSense-Linux` folder. A zip for both, so one step serves both; Python's `zipfile` keeps the Linux file modes, so `unzip` restores the executable bit. The short name per system goes in `compiler.SYSTEMS` (`zip`: `Win`, `Linux`).
- **One release, both zips.** The full release runs on whichever system goes first, as today: version, changelog, build, zip, commit, tag, upload. The upload step, finding the release already there, now adds this system's zip to it when that zip is not on it yet (`gh release upload`, never `--clobber`), instead of stopping.
- **A new menu entry for the second system**, "Add this system's build to the release": for the VERSION already released, it builds, zips and adds the zip, skipping the check's "changes waiting" rule, the prepare, the commit and the tag. It needs the tag and the GitHub release to exist, and the working copy committed and pushed.
- **Nothing is replaced or deleted**: an asset of the same name already on the release is left alone and said so, as tags and releases are now.
- The messages and docstrings name the build folder and zip of the system it runs on, not always Windows'. `GH_FALLBACK`, the Windows install path of gh, only matters on Windows; on Linux gh is found on the PATH.
- **Tests** (`release.py`): the zip names by system, the Linux zip extracting to `SixthSense-Linux`, and deciding whether this system's zip is already on a release, all without git, gh or a network. **Docs:** README, CLAUDE.md, [[project_release_tooling_plan]] pointer, [[project_linux_build_plan]] pointer. No changelog line: players see the Linux zip only once a release carries it, and the Linux build's line is already there.
