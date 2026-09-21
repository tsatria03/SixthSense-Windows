---
name: project_compiler_py
description: "compiler.py was adapted to build Sixth Sense on 2026-09-21 (not yet built by the dev); what changed, what was left out on purpose, and what is still to do."
metadata:
  node_type: memory
  type: project
  originSessionId: 8a78e7c9-236d-421e-8e76-c11a2895c278
---

`compiler.py` is the PyInstaller build script, with the numbered menu, the changelog filing and the release zip. It was adapted from an earlier build script. A newer version of that script is kept for reference in the gitignored `user/` folder; read it there, but never edit it, and don't name it in writing ([[feedback_no_other_games]]). Never run `compiler.py`, not even `--dry-run`, without the dev's say-so; see [[feedback_dont_run_or_build]].

## Status

Adapted to Sixth Sense on 2026-09-21, with the dev's go-ahead.
- It was checked only statically: it parses, and it has no undefined names.
- **It has not been run or built yet.** The dev does that.
- The todo item "Test the compiler with a first build" (reworded on 2026-09-21 from "Make the compiler sixth sense compatible") stays unfinished until the dev's first build works.
- Its comments and docstrings describe Sixth Sense alone; the three that named the project it came from were reworded on 2026-09-21 ([[feedback_no_other_games]]).

## What changed from the earlier script
- **Names:** `NAME='SixthSense'`, `ENTRY='SixthSense.py'`, the docstring, the argparse description, the menu title, and the closing credit (now "Bitbee's"; the original is `kr.co.bitbee.sixsense`).
- **`PLAY_PACKAGES`** is just `pygame` (pip name `pygame`, not `pygame-ce`, since the two conflict). numpy and av were dropped because Sixth Sense doesn't use them.
- **The new `OPTIONAL_PACKAGES`** holds `comtypes` (the SAPI voice). `optional_missing()` prints a "note:" line but doesn't stop the build. `--collect-submodules comtypes` is passed only when comtypes is installed.
- **The HRTF check is gone:** `DATA` (`assets/hrtf`) and its check in `problems_now()` were removed, because HRTF is deliberately off in this port.
- **`--collect-all av` was removed.**
- **The new `GAME_FILES` and `game_files()`**, plus a rewritten `copy_game()`:
  - It copies only `*.wav`, `*.plist`, `g_CH1_E`, `a_CH1_E.txt` and `s_CH1_E.txt` from the bundle's top folder, matched without regard to case. That is 414 files, 106.6 MB.
  - The iOS executable `sixsense`, the nibs, the PNGs and JPGs, `iTunesArtwork`, `PkgInfo` and the unused `stage1ground`/`stage1sound` stay out, as do the `_CodeSignature` and Facebook folders.
  - The source comes from `sixthsense.paths.game()`, which honors `--game` and `SIXTHSENSE_GAME`. If the bundle is missing it catches the SystemExit and prints a message instead of crashing.
- **`--test` was removed:** the flag, the menu entry, `test_build()` and `read_log()` are all gone. The menu now has 7 choices plus Quit, and Release build is still number 1.
- **readme.html generation was removed** (`GENERATED_PAGES` and `write_page()`). The reference script in `user/` has it, along with the `tools/md_to_html.py` converter it needs; bring both back once there's a real README.
- **`FIRST_VERSION = '1.0.0-1'` became `first_version()`**, which returns `%y.%m.%d-1` to match the repo's date-scheme VERSION.
- **The docstrings and comments** no longer mention an updater, and they explain the missing `--test` and the silent windowed failure.

## Left out on purpose
The newer reference script in `user/` bakes VERSION into the build as a module and bundles the Prism speech library (`prismatoid`, `_cffi_backend`). Sixth Sense has no updater and no Prism. Port them only if the dev asks.

## Still to do
1. **Bring `--test` back once the game supports it.** `SixthSense.py` needs a log file in `%APPDATA%\SixthSense`, a `crash.txt` excepthook, an `--exit-after N` flag and a "game data: <path>" log line. Then restore `test_build()` and `read_log()` from the reference script in `user/`, adapted without its HRTF check. This also fixes the evaluation's "no crash path" item; see [[project_evaluation_2026_09]].
2. **Silent failures:** until item 1 lands, a `--windowed` build that fails to start is silent. Tell the dev to use the console build (menu choice 4) to diagnose.
3. **The changelog:** `changelog.txt` has no `unrelease:` heading yet, so the first release build inserts one at the top. Its only heading is `26.09.20:` while VERSION says `26.09.21-1`; the dev may want to line those up.

## Fine as-is
- `BINARIES`: the vendor DLLs go to `_MEIPASS/vendor/...`, which is where `sixthsense/paths.py` looks when frozen.
- `SIDE_FILES`: changelog.txt, VERSION and LICENSE (shipped as license.txt).
- `.gitignore` covers `build/`, `dist/` and `*.spec`.

## Environment on 2026-09-21
- The dev installed **PyInstaller 6.22.3** into their Python 3.12 x64 (`C:\Users\tonys\AppData\Local\Programs\Python\Python312`).
- comtypes, numpy and av are not installed.
- PyInstaller 6 puts onedir builds' bundled files under `dist/SixthSense/_internal`, which is `sys._MEIPASS`.
- The game data goes beside the exe, in `dist/SixthSense/game`, which is `EXE_DIR/game`.

**How to apply:** Keep `compiler.py`'s structure and prose style (the menu, the flags, the spoken messages). Compare against the reference script in `user/` when bringing features across.
