# CLAUDE.md

This file guides Claude Code when it works in this repository. **It is a lean dispatcher.** It says what the project is and how it is laid out, then points to focused memory files (`[[name]]`) for the detail. When you start work in an area, read its linked memory first.

**Memory location:** all memory files (the `[[name]]` links and the `MEMORY.md` index) live in the repo's **`aidocks/`** folder, as `aidocks/<name>.md`. Read memory from there and write new or updated memory there, never to the `~/.claude` memory store. `aidocks/MEMORY.md` is the index, so add a one-line pointer there for every new memory. Keep this file under 40,000 characters and move detail into memory ([[feedback_memory_in_aidocks]]).

## What this is

A Windows port of **Sixth Sense** (`kr.co.bitbee.sixsense` 1.2), a 2013 iPhone audio-only zombie shooter for blind players. You walk down a dark corridor and shoot what you hear coming, in five lanes laid out like a clock face.

There is no source code for the original. The port is **recovered from the ARMv7 binary** and rewritten method by method **entirely in Python**. **lbk2907 created it**, including the binary extraction, and handed it to tsatria03 to publish and develop together; the "Initial commit" is entirely their work ([[project_provenance]]). Each Python module mirrors one Objective-C class and cites the binary address it came from ([[project_python_only]]).

The game plays the original's own 269 recorded WAVs, which `SoundList.plist` names by number in 371 entries. The only synthesised speech is the key-bindings screen and a few "not available" lines, through NVDA, another screen reader via Prism, or a Windows voice ([[project_prism_speech]]).

## Layout

- **`SixthSense.py`**: the entry point and screen loop (stands in for `UINavigationController`).
- **`sixthsense/game/`**: one module per original class. `stage_1_e.py` is the core loop; the others include `monster_control.py`, `weapon_control.py`, `main_controller.py` (the menu and coin economy), `stage_tutorial.py`, `stage_1_test.py` (the weapon test range behind the shop's Try button, [[project_test_range]]), `debug.py` (the `--debug` keys), `store.py`, `inventory.py`, `intro.py`, `app_delegate.py` and `oal_playback.py`.
- **`sixthsense/platform/`**:
  - `openal.py`: a ctypes binding to OpenAL Soft, with HRTF off.
  - `runloop.py`: stands in for `NSTimer` and `performSelector:afterDelay:`.
  - `defaults.py`: stands in for `NSUserDefaults`.
  - `speech.py`, `keymap.py`, `music.py` and `volume.py` (the decibel knobs, [[project_volume_knobs]]).
- **`sixthsense/ui/`**: the keyboard input for the stage, the menus and the screens, plus the F1 key-bindings screen.
- **`game/`**: the original app bundle's data: the plists, the maps, the images and the iOS binary. Every sound the game uses lives in `game/sounds/used/`, in folders, under its original file name, a deliberate divergence. `game/sounds/unused/` holds 25 files that aren't the original's own, which the game never uses. `paths.path_for_resource` looks in the top folder first, then by file name under `game/sounds/used/` ([[project_sound_organization]]). Don't move, rename, convert or delete sound files unless the dev asks.
- **`analysis/`**:
  - `bin/sixsense_armv7`: the binary itself.
  - `disasm/dc_*.txt`: per-class decompiled listings.
  - `digest/dg_*.txt`: condensed call summaries.
  - `data/objc_classes.json`.
- **`tools/`**: the Mach-O and disassembly tools that produced `analysis/`. `dz.py` and `dc.py` need `capstone`.
- **`docs/`**: `PORTING_STATUS.md` (done, stubbed, not ported), `DIVERGENCES.md` (where the port differs, and which original bugs it reproduces) and `GAME_STRUCTURE.md`. Some "reproduced" entries are misreadings; see [[project_evaluation_2026_09]].
- **`tests/`**: plain scripts, each with its own runner. **They write the real save**, so read [[project_safe_test_run]] before running any. `tests/level_tester.py` is not a test: it starts the real game at any level, area and row, on its own save in `%APPDATA%\SixthSense\level_tester`, for checking by ear.
- **`vendor/`**: `soft_oal.dll` and `nvdaControllerClient64.dll` (x64).
- **`compiler.py`**: the PyInstaller build script. Run it with no flags for a menu; it builds `dist\SixthSense`, a folder build or with `--embed` one exe holding the sounds and data, and never zips or changes the repository ([[project_compiler_py]]).
- **`releaser.py`**: sets the date version, files the changelog, runs the compiler, zips the build, commits, tags `V<version>` and uploads the zip to GitHub through `gh` ([[project_release_tooling_plan]]). Built 2026-09-23, not yet confirmed by the dev.
- **`bloopers/`**: short clips of funny bugs, kept for fun and preferably under two minutes. Its README sets the naming and format rules. The build leaves it out; only add clips the dev provides.
- **`New File.txt`** at the root is the dev's private scratchpad. It is gitignored; never read, edit, flag or delete it.
- **`user/`** is gitignored private reference material. Read it, but never edit it. Never name the dev's other games that are kept in it, in the todo list, memory, or code and comments ([[feedback_no_other_games]]). The dev's old NVGT remake of this game used to be there; it was deleted on 2026-09-21 ([[project_nvgt_remake_reference]]).

The save file and the key bindings live in `%APPDATA%\SixthSense\` (`defaults.json`, `keys.json`).

## Running and building

**The dev runs and builds, not Claude.** Never build unless told to. The tests may be run without asking, always the safe way ([[project_safe_test_run]]), but only the scripts that cover the Python files changed; the full suite runs only when the dev asks ([[feedback_dont_run_or_build]]). Ask before running the game, `compiler.py`, or anything else that executes game code or speaks ([[feedback_dont_run_or_build]]).

`python SixthSense.py` opens the splash, then the menu. Flags:
- `--no-intro` opens straight on the menu.
- `--stage` and `--tutorial` start those directly.
- `--skip-tutorial` writes `TUTORIAL=1`.
- `--no-window` runs headless.
- `--debug`: a zombie that reaches you just dies, nothing takes a heart, and no kill, headshot, score or gold counts. Tab reaches every weapon and nothing runs out. It adds F2, Shift+F2, F5, Shift+F5, F6, F7 and F11 (`game/debug.py`), which the F1 screen lists only in debug mode.
- `-v` gives verbose logging.

This needs Python 3.12 x64, pygame and `prismatoid` (Prism). Without Prism the game still runs, but only NVDA speaks ([[project_prism_speech]]). `pip install -r requirements.txt` installs both.

## Porting rules

- Port from the binary, and cite the address in the code. Record every deliberate difference in `docs/DIVERGENCES.md`.
- Before "reproducing" anything that hinges on one branch or constant, check the raw bytes. The decompiled listings mislead in known ways, and addresses are VM addresses, so file offset = address - 0x1000 ([[project_binary_analysis_notes]]).
- Several tests assert current behavior, including some misreadings. Changing that behavior means updating its test in the same change.

## Where the detail lives

- **The current state, the known bugs, the three todo-list root causes, open decisions and the fix order**: [[project_evaluation_2026_09]].
- **Reading the binary correctly**: [[project_binary_analysis_notes]].
- **The screen reader mode** (the voice over row off means the screen reader speaks the game's words; built for the menus and the result panel; the tutorial stays recorded): [[project_screen_reader_mode]].
- **Running the tests safely**, once the dev says yes: [[project_safe_test_run]].
- **Adapting the build script**: [[project_compiler_py]].
- **The task list** (`todo list.txt`) and how to write in it: [[feedback_todo_list_format]]. It holds only what a player notices, since it ships beside the game; developer tasks, open and finished, are in [[project_dev_tasks]].
- **The changelog** (`changelog.txt`): every player-facing fix or enhancement adds a line at the top of the `unrelease:` block in the same commit, newest first ([[feedback_changelog]]).
- **Plans**: an agreed plan goes into its own aidocks note before any code, and is marked finished there only once the dev says it works ([[feedback_record_plans_first]]).
- **Committing and pushing** (commit when asked, then push without asking; history rewrites need a go-ahead): [[feedback_git_commits]].
- **Who made what, the permission to publish, and how to credit contributors in commits**: [[project_provenance]]. Name people by GitHub username only: [[feedback_use_github_usernames]].
- **Who you're working with**: [[user_screen_reader]]. The dev uses NVDA, so prefer lists and short lines, and never make noise from tools.

`CLAUDE.md` and `aidocks/` are committed, not gitignored.
