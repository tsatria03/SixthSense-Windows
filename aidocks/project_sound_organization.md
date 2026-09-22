---
name: project_sound_organization
description: "Every sound the game uses lives in game/sounds/used, in folders, under its original file name (a deliberate divergence); non-original files are in game/sounds/unused. How it was built and verified on 2026-09-21, and the one thing still open: the code lookup, which should search used/ only."
metadata:
  node_type: memory
  type: project
  originSessionId: 8a78e7c9-236d-421e-8e76-c11a2895c278
---

**Every sound the game uses lives in `game/sounds/used/`**, in folders, under its original file name. They are no longer in the original bundle's flat folder. It is the only way the port departs from the original's data; everything else stays faithful. It is documented in `docs/DIVERGENCES.md` under "The sounds are organized into folders".

## The layout (dev's final reorganization, 2026-09-21)
- **`game/sounds/used/`** has 329 files covering **all 269** of the original's sounds:
  - `sfx/zombies/normal/normalcave1..12` and `normalforest1..12`
  - `sfx/zombies/bosses/bosscave1..3` and `bossforest1..3`
  - `sfx/characters/charcave1..2` and `charforest1..2`
  - `sfx/monsters/monstercave` and `monsterforest`
  - `sfx/weapons` and `sfx/misc`
  - `speech/game`, `logos`, `menus/main`, `menus/store`, `numbers`, `tutorials` and `weapons`
- **The extra 60 files are same-audio copies.** 38 sounds are shared between folders (for example the boss hit and death in all six boss folders, or `zombie_3_7_hit_player` in six zombie folders), since the original shares damage, death and hit sounds between areas and zombie kinds; only the "coming" loops differ.
- **`game/sounds/unused/`** holds 25 files that are not the original's own, under their old sub-paths:
  - 11 extra same-folder copies: `sfx/misc/menuclick.wav` (another `ui_select`), five `sfx/weapons/*hit.wav` (`gun_att_sound_1`) and five `*empty.wav` (`weapon_nonbullets`)
  - 14 sounds the original never had: the eight character `hurt1`/`hurt2`, `grenadereload`, `yes`, `no`, `question`, `GameStart` (an edited cut of `Game Start Button`) and `welcome`

  Nothing uses them.
- **Every file is 16-bit PCM WAV**, 120 MB for `used/`. The `game/` root keeps the plists, the maps, the images and the iOS binary. `game/sounds2/` (the original flat WAVs, kept for matching) is safe to delete, and the dev said they would.

## How it was built and verified (2026-09-21)
1. The dev converted their old NVGT remake's organized OGG sounds back to WAV. Claude matched each file to its original by audio: a loudness envelope, then the waveform at 8 kHz with `audioop.findfit` (a residual below about 0.3 means the same recording). The scripts are in the session scratchpad under `match/`.
2. **Renames:** 187 files got their original names, 136 already had them, and 3 changes were case-only. The remake had labelled some sounds its own way; for example `bgm_rain_mus` is really `bgm_start_end`, `menuwrap` is `coin_sound`, and `warning` is the original's misspelled `warring`.
3. **16-bit:** the OGG round trip had left the files 24-bit. `oal_playback.py` and `platform/music.py` treat any width other than 1 as 16-bit, so 24-bit data would have played as loud noise. The dev reconverted everything to 16-bit. Any future sound must be 8-bit or 16-bit PCM WAV for those loaders.
4. **The six originals the remake lacked** were copied in byte-identical from `sounds2`:
   - `Game Start Button`, `game center button10` and `restore button`, into `speech/menus/main`
   - `Welcome to`, into `speech/game`
   - `weapon_m4_fire` and `weapon_saw_start`, into `sfx/weapons`
5. **The non-original files** went to `unused/`, and then the dev moved the rest into `used/`.
6. **Final recheck after the last move:**
   - all 354 files are 16-bit
   - all 329 files in `used/` match their namesake original's waveform (worst residual 0.294)
   - all 269 originals are present
   - all 25 non-original files are in `unused/`, and none are anywhere else

## Still open, and in `todo list.txt`
**The code still expects the flat folder.** `paths.path_for_resource` joins names straight onto `game()`, `compiler.py`'s `game_files()` only copies the top folder, and tests such as `tests/test_data.py` build `game/<name>.wav` paths by hand. The game finds no sounds, and those tests fail.

**The agreed plan.** The dev approved it on 2026-09-21 ("I love it!"); it has not been implemented yet.
1. **`paths.path_for_resource(name, ext)`** is the one choke point, called from `oal_playback.py`'s buffer loader and its BG and AMB players, and also used for the plists and maps. Make it check the `game()` root first, exactly as now, then fall back to a sound index. Root-first keeps the plists and maps unchanged, and keeps `--game` working on an untouched flat original bundle.
2. **The sound index** is built lazily, once, by walking **`game()/sounds/used/` only** (never `unused/`) in sorted order. It maps lowercase file name to path, and the first copy wins when a name appears in several folders, since all copies are the same audio. `set_game()` clears it. Walking about 329 files is trivial.
3. **`paths.sounds()`** returns `game()/sounds/used` when it exists, otherwise `game()`.
4. **Tests:**
   - Route the six hand-built `os.path.join(paths.sounds(), name + '.wav')` lines through the lookup: three in `test_data.py` (including the `listdir` in `test_sound_list_covers_the_wavs`), and one each in `test_menu`, `test_pause` and `test_store`.
   - Add tests that a nested sound is found, `unused/` is never found, a case mismatch still resolves, and a flat bundle still works (a tiny temporary bundle built in the test).
5. **`compiler.py`:** also copy `game/sounds/used/` recursively, keep the top-level `GAME_FILES` for flat bundles, leave `unused/` out, and report the count in the dry run.
6. **Docs last:**
   - the `paths.py` docstring, which still says the bundle is flat
   - the "Still to do" list in `DIVERGENCES.md`, and `PORTING_STATUS.md`
   - the todo list's top item, moved to finished
   - these notes

Then ask the dev before running the tests (the safe way, [[project_safe_test_run]]), and commit and push when they say so. The analysis tools only read `SoundList.plist` and the binary from the root, so they need no change.

**How to apply:** Never move, rename, convert or delete sound files unless the dev asks. When fixing the lookup, change the code, run the tests with the dev's go-ahead, and update the "Still to do" list in `DIVERGENCES.md`.
