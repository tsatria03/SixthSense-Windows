---
name: project_compiler_py
description: "compiler.py was adapted to build Sixth Sense on 2026-09-21. The dev confirmed the console build works on 2026-09-22; an earlier zip was cut off, so packaging now announces itself and writes a .part file first. What changed, what was left out on purpose, and what is still to do."
metadata:
  node_type: memory
  type: project
  originSessionId: 8a78e7c9-236d-421e-8e76-c11a2895c278
---

`compiler.py` is the PyInstaller build script, with the numbered menu, the changelog filing and the release zip. It was adapted from an earlier build script. A newer version of that script is kept for reference in the gitignored `user/` folder; read it there, but never edit it, and don't name it in writing ([[feedback_no_other_games]]). Never run `compiler.py`, not even `--dry-run`, without the dev's say-so; see [[feedback_dont_run_or_build]].

**Planned change (2026-09-23):** the changelog filing moves out to a new `releaser.py`, and the compiler gains an option to embed the game's data in one exe. See [[project_release_tooling_plan]].

## Status

Adapted to Sixth Sense on 2026-09-21, with the dev's go-ahead.
- **First builds, 2026-09-22.** The dev ran menu choice 4 (`--console`) twice, at 08:28 and at 09:19.
  - Claude checked the 09:19 build's `dist/SixthSense` against the repo. It was complete:
    - all 474 game files, byte-identical to the repo
    - all 17 license files
    - the vendor DLLs in `_internal/vendor`
    - Prism with `prism.dll` and `_prism_cffi.pyd` in `_internal/prism/_native`, plus `_cffi_backend`
    - `changelog.txt`, `VERSION` and `license.txt`, identical to the repo's
  - PyInstaller's warning "missing module named prism._prism_cffi" is a false alarm. Prism's `_native.py` adds `prism/_native` to the package path when it is imported, which static analysis can't see.
  - `prism.lib` (15 KB, an import library) gets bundled too. It is harmless.
  - **The zip was broken**: 399 of 643 files, with no central directory. The dev had closed the window during packing, because nothing said to wait.
  - `package()` was changed the same day, checked only by parsing:
    - it says "packaging the release", then a line after each quarter of the files, then "the zip is done"
    - it writes `<name>.zip.part` and renames it only once it is whole
- **Confirmed working, 2026-09-22.** The dev rebuilt with choice 4 at 09:27 and said "The exe works".
  - Claude checked the zip: `zipfile.testzip` passes, and it holds 643 files (107 MB) under `SixthSense/`.
  - Every member is byte-identical to the built folder, and every game file to the repo. No `.part` file was left behind.
  - The todo item "Test the compiler with a first build" moved to finished that day.
- Still untested: a plain release build (choice 1, which files the changelog), a windowed build, and `--onefile`.
- Its comments and docstrings describe Sixth Sense alone; the three that named the project it came from were reworded on 2026-09-21 ([[feedback_no_other_games]]).

## What changed from the earlier script
- **Names:** `NAME='SixthSense'`, `ENTRY='SixthSense.py'`, the docstring, the argparse description, the menu title, and the closing credit (now "Bitbee's"; the original is `kr.co.bitbee.sixsense`).
- **`PLAY_PACKAGES`** is just `pygame` (pip name `pygame`, not `pygame-ce`, since the two conflict). numpy and av were dropped because Sixth Sense doesn't use them.
- **`OPTIONAL_PACKAGES`** held `comtypes` (the SAPI voice), with `optional_missing()` printing a "note:" line. **All of that was removed on 2026-09-22**, when Prism replaced comtypes (see below).
- **The HRTF check is gone:** `DATA` (`assets/hrtf`) and its check in `problems_now()` were removed, because HRTF is deliberately off in this port.
- **`--collect-all av` was removed.**
- **The new `GAME_FILES` and `game_files()`**, plus a rewritten `copy_game()`:
  - It copies only `*.wav`, `*.plist`, `g_CH1_E`, `a_CH1_E.txt` and `s_CH1_E.txt` from the bundle's top folder, matched without regard to case. With the original flat bundle that was 414 files, 106.6 MB. Since the sounds moved, it also copies `sounds/used/`; see below.
  - The iOS executable `sixsense`, the nibs, the PNGs and JPGs, `iTunesArtwork`, `PkgInfo` and the unused `stage1ground`/`stage1sound` stay out, as do the `_CodeSignature` and Facebook folders.
  - The source comes from `sixthsense.paths.game()`, which honors `--game` and `SIXTHSENSE_GAME`. If the bundle is missing it catches the SystemExit and prints a message instead of crashing.
- **`--test` was removed:** the flag, the menu entry, `test_build()` and `read_log()` are all gone. The menu now has 7 choices plus Quit, and Release build is still number 1.
- **readme.html generation was removed** (`GENERATED_PAGES` and `write_page()`). The reference script in `user/` has it, along with the `tools/md_to_html.py` converter it needs; bring both back once there's a real README.
- **`FIRST_VERSION = '1.0.0-1'` became `first_version()`**, which returns `%y.%m.%d-1` to match the repo's date-scheme VERSION.
- **The docstrings and comments** no longer mention an updater, and they explain the missing `--test` and the silent windowed failure.

## Left out on purpose
The newer reference script in `user/` bakes VERSION into the build as a module. Sixth Sense has no updater, so that stays out unless the dev asks.

**Prism was added on 2026-09-22.** `compiler.py` now:
- requires `prismatoid`
- passes `--collect-all prism --hidden-import _cffi_backend` and Prism's native `.pyd`
- fills a `licenses` folder beside the executable: OpenAL Soft and the NVDA controller client from `vendor/`, and Prism and pygame from their installed packages

`OPTIONAL_PACKAGES`, `optional_missing()` and comtypes are gone. This has been checked only by parsing, and hasn't been built yet. See [[project_prism_speech]].

## Sounds moved (2026-09-21)
The sounds now live in `game/sounds/used/`, in folders ([[project_sound_organization]]). The same day, `compiler.py` was changed to ship them. This was checked by reading the code only, not run.
- `sound_files()` walks `sounds/used/` (`paths.SOUNDS_USED`) in sorted order, and `copy_game()` recreates each file's folder under `dist/SixthSense/game/`. `game/sounds/unused/` is left out.
- `game_files()` still matches `GAME_FILES` in the top folder. `*.wav` stays in it so an untouched flat original bundle (`--game`) still builds.
- `data_summary()` words the counts for both `copy_game()` and `--dry-run`. With the repo's `game/` today that is 474 files: 329 sounds (about 121 MB), plus 142 plists and 3 map layers.

## Still to do
1. **Bring `--test` back once the game supports it.** `SixthSense.py` needs a log file in `%APPDATA%\SixthSense`, a `crash.txt` excepthook, an `--exit-after N` flag and a "game data: <path>" log line. Then restore `test_build()` and `read_log()` from the reference script in `user/`, adapted without its HRTF check. This also fixes the evaluation's "no crash path" item; see [[project_evaluation_2026_09]].
2. **Silent failures:** until item 1 lands, a `--windowed` build that fails to start is silent. Tell the dev to use the console build (menu choice 4) to diagnose.
3. **The changelog:** **the game has never been released.** On 2026-09-22 the dev removed the `26.09.20: Initial release.` entry for that reason. `changelog.txt` now holds only the `unrelease:` section, with the player-facing fixes and enhancements made so far ([[feedback_changelog]]). The first plain release build files those lines under whatever VERSION says, `26.09.21-1:` today, unless the dev changes VERSION first.

## Test builds versus release builds
Menu choice 1, the plain release build, rewrites `changelog.txt` in the repo: it moves the `unrelease:` lines under the VERSION heading, and starts VERSION if it's missing. Any flagged build leaves both alone. So for a trial build, point the dev at these:
- choice 7, `--dry-run`, first
- choice 4, `--console`, which shows start-up errors
- choice 2, `--no-package`

Keep choice 1 for the real release. The dev chose on 2026-09-22 to do the first build by hand.

## Fine as-is
- `BINARIES`: the vendor DLLs go to `_MEIPASS/vendor/...`, which is where `sixthsense/paths.py` looks when frozen.
- `SIDE_FILES`: changelog.txt, VERSION and LICENSE (shipped as license.txt).
- `.gitignore` covers `build/`, `dist/` and `*.spec`.

## Environment on 2026-09-21
- The dev installed **PyInstaller 6.22.3** into their Python 3.12 x64 (`C:\Users\tonys\AppData\Local\Programs\Python\Python312`).
- comtypes, numpy and av are not installed. Since 2026-09-22 the build needs prismatoid, and 0.18.2 is installed with cffi 2.1.1.
- PyInstaller 6 puts onedir builds' bundled files under `dist/SixthSense/_internal`, which is `sys._MEIPASS`.
- The game data goes beside the exe, in `dist/SixthSense/game`, which is `EXE_DIR/game`.

**How to apply:** Keep `compiler.py`'s structure and prose style (the menu, the flags, the spoken messages). Compare against the reference script in `user/` when bringing features across.
