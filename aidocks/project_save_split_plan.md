---
name: project_save_split_plan
description: "PLANNED 2026-09-25, not built. defaults.json splits into save.json (progress) and settings.json (EYEMODE, MENUMUSICVOLUME), beside the keys.json that already exists, routed by key name inside UserDefaults; an existing defaults.json is split over by itself on the first start and kept as defaults.json.old. Comes before [[project_weapon_stats_in_save_plan]]."
metadata:
  type: project
---

**Status: PLANNED, 2026-09-25.** Agreed with the dev, recorded before any code ([[feedback_record_plans_first]]), and in the todo list as unfinished. Mark it finished only once the dev says it works.

**The dev's request:** they pointed at an example in the gitignored `user/` folder, a port of another game (never name it, [[feedback_no_other_games]]), which keeps `save.json`, `settings.json` and `keys.json`, routed by key name (its `SplitDefaults`, with a `SETTINGS_KEYS` set and everything else to the save). The dev: "That's exactly what I want. save.json, settings.json, and keys.json."

## The three files, in `%APPDATA%\SixthSense`
- **`save.json`:** progress. Every key not named as a setting: `TUTORIAL`, `FIREST`, `GOLD`, `COIN`, `COIN_TIMER`, `COIN_TIMER_START`, `GRENADECOUNT`, `STAGE`, the owned weapons (`SHOTGUN`, `M4`, `AK47`, `MG80`, `JAPAN`), the equipped ones (`*USE`), `TOPSCORE`, `TOPSCOREWEEK`, `WEEKTIME`, `NOWRANK`, `REVIEWCOUNT`, and any key added later. Progress is the safe default for a new key, as in the example.
- **`settings.json`:** the player's preferences: `EYEMODE` (voice over) and `MENUMUSICVOLUME` (the menu music volume, [[project_menu_music_volume_plan]]). A `SETTINGS_KEYS` set in `platform/defaults.py` names them; a new setting is added there.
- **`keys.json`:** unchanged. `platform/keymap.py` already writes it on its own, with the defaults on the first start (2026-09-25).

## How
- `UserDefaults` keeps its interface (`standardUserDefaults()`, `objectForKey_`, `setObject_forKey_`, `synchronize`, ...), so none of the game code that uses it changes. Inside, it holds two stores and picks one by key name. `synchronize` writes whichever changed.
- **Each file keeps the damaged-save protection** tunmi13productions built for `defaults.json`: a file that cannot be read is kept as `<name>.damaged`, and the game carries on from `<name>.bak`, the copy before the last write.
- **An existing `defaults.json` is moved over by itself**, on the first start after the change, when there is no `save.json` yet: its settings keys go to `settings.json` and the rest to `save.json`, both are written, and `defaults.json` is renamed `defaults.json.old`, kept, never deleted. A damaged `defaults.json` goes through the same `.damaged` and `.bak` path first. When `save.json` already exists, a `defaults.json` beside it is left alone.
- **The choosers** (`tests/interact/level_chooser.py`, `tutorial_chooser.py`) copy `settings.json` in beside `keys.json`, so voice over and the music volume match the real game.
- **Tests:** a new save makes both files with the keys in the right one; a setting and a progress key each land in their file; the move from an old `defaults.json`, `.old` kept; the damaged path per file; `save.py`'s tests moved to the new names. `_scratch_save` already points the whole folder at a throwaway one.
- **Docs:** `docks/readme.txt` ("Your save"), `README.md`, `CLAUDE.md` (where the save lives), `aidocks/DIVERGENCES.md` (the `NSUserDefaults` entry: the original keeps one plist), `platform/defaults.py`'s docstring, and a changelog entry.
