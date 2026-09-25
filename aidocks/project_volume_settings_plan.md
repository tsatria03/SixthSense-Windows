---
name: project_volume_settings_plan
description: "PLANNED 2026-09-25, not built. settings.json gains MASTERVOLUME, LEVELMUSICVOLUME and AMBIENCEVOLUME beside MENUMUSICVOLUME: percentages 0 to 100, 100 the original's mix, set only by editing the file, read on start, written with every default on the first start. Needs [[project_save_split_plan]] first."
metadata:
  type: project
---

**Status: BUILT, 2026-09-25, not yet confirmed by the dev.** Agreed with the dev, recorded before any code ([[feedback_record_plans_first]]), and in the todo list as unfinished. Mark it finished only once the dev says it works. Built after [[project_save_split_plan]], since it lives in `settings.json`.

**What was built:** `platform/volume.py`: `VOLUME_KEYS`, `percents` (what `load` last read, all 100 until then), `valid_percent`, `percent` (invalid means 100), `percent_gain` (squared) and `load(defaults)`, called from `AppDelegate.didFinishLaunching`, which writes missing volumes at 100 and `EYEMODE` at the current mode, so settings.json lists every setting. `master()`, `music()` and `ambience()` multiply by their setting; `menu_music(p)` uses `percent_gain`. `defaults.SETTINGS_KEYS` is now in the dev's order. `AppDelegate.menu_music_volume` takes any whole number, and Page Up and Page Down step to the next ten from it. `ChangeLevel:`'s 0.02 ambience note now goes through `volume.ambience`. The story row's music goes through `volume.music`, so the level music setting covers it too. Tests: five new in `tests/case/volume.py`; `menu_music.py`'s bad-value test updated (55 is valid now) and one new for stepping from 55. Built in the batch with the other two save plans; no test ran until all three were committed (2026-09-25).

**The dev's request:** asked what `settings.json` would hold (`EYEMODE`, `MENUMUSICVOLUME`), they wanted "more modifiable keys, like look at volumes.py". Changed "Only in settings.json", not in the game. They first asked for up to 200%, then: "on second thought, 0 to 100 percent is fine for now."

## The keys, all in `settings.json`, in this order
The dev, 2026-09-25: "master volume should go before menu music volume", and the level music's key is named for the level music. `settings.json` is written in this fixed order, not sorted by name (the save's own `synchronize` sorts; this file does not):
1. **`MASTERVOLUME`:** everything the game plays (`volume.MASTER_DB`'s group, applied in `oal_playback` on every `AL_GAIN`).
2. **`MENUMUSICVOLUME`:** already there ([[project_menu_music_volume_plan]]), still set by Page Up and Page Down in the menus as well.
3. **`LEVELMUSICVOLUME`:** the level music, `bgm_cave` and `bgm_forest`, on top of the binary's 0.02 (0x321d4). The other level's ambience note at 0.02 (0x32362) is ambience, not this.
4. **`AMBIENCEVOLUME`:** the cave and forest ambience at 0.2 (0x2ddfa), the rain at 0.5 (0x2ddc8), the level change's 0.3 (0x31ce2) and the quiet loop at 0.02 (0x32362).
5. **`EYEMODE`:** voice over, the one setting that is not a volume.

A setting added later goes where it belongs in that list, not at the end by default.

## How they behave
- **0 to 100 percent, 100 being the original's mix**, so every default leaves the game sounding as it does now: the binary's gains stay in the code where they are used, and the setting only scales its group. Nothing above 100, so no gain goes past what the binary sets, and OpenAL's cap of 1.0 per source never matters.
- **The same curve as the menu music**: the percentage is squared into the gain (`volume.menu_music` does it today), so each step sounds about as big as the last. 50% is a quarter of the gain, about -12 dB; 0% is silent.
- **Any whole number from 0 to 100** is taken, since the file is edited by hand. Anything else (a word, a fraction, below 0, above 100) counts as 100. The menu music's Page Up and Page Down step to the next ten from wherever the value is (55 goes to 60 or 50), and the menu music's own check, which today treats a value that is not a step of ten as 100, widens to match.
- **Only in the file.** No keys and no menu in the game change the three new ones. They are read when the game starts, so an edit takes effect on the next start.
- **Written with every default on the first start**, like `keys.json` since 2026-09-25, so a player opening `settings.json` sees every volume they can change. A file that lacks a key gains it at its default, and the player's own values are kept.

## Where it goes
- `platform/volume.py`: `MASTER_DB`, `MUSIC_DB` and `AMBIENCE_DB` stay the fixed trims, and each group's percentage is read from the settings and applied on top in `master()`, `music()` and `ambience()`. One `percent_gain(percent)` shared with the menu music.
- `platform/defaults.py`: the three keys join `SETTINGS_KEYS`, with their defaults, so the split writes them into `settings.json`.

## Tests and docs
- Each key at 100 leaves every gain exactly the binary's; 50 and 0 scale only their own group; bad values mean 100; the first start writes every default; a player's own value is kept.
- `docks/readme.txt` ("Your save": the volumes in settings.json and what 0 and 100 mean), `README.md`, `aidocks/DIVERGENCES.md` (the volume knobs entry), and a changelog entry.
