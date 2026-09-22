---
name: project_sound_organization
description: "Every sound the game uses lives in game/sounds/used, in folders, under its original file name (a deliberate divergence); non-original files are in game/sounds/unused. How it was built and verified on 2026-09-21, and how the code finds the sounds (lookup rewritten the same day; tests pass and the dev confirmed it in play)."
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
- **Every file is 16-bit PCM WAV**, 120 MB for `used/`. The `game/` root keeps the plists, the maps, the images and the iOS binary. `game/sounds2/` (the original flat WAVs, kept for matching) was deleted by the dev before the commit, and was never committed.

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

## How the code finds the sounds (done 2026-09-21)
The dev approved the plan on 2026-09-21 ("I love it!"), and it was built the same day. **The full suite passed, 117 of 117**, with the dev's go-ahead ([[project_safe_test_run]]), and no "sound file missing" warning was printed. **The dev then played the game on 2026-09-21 and confirmed it finds its sounds** ("Everything worked!"). The todo item moved to finished as "The game finds its sounds in game/sounds/used again...".
- **`paths.path_for_resource(name, ext)`** is the one place every sound, plist and map is looked up. It is called from `oal_playback.py`'s buffer loader and its BG and AMB players, and also for the plists and maps.
  - It checks the `game()` top folder first, as the original did. That keeps the plists and maps unchanged, and keeps `--game` working on an untouched, flat original bundle.
  - Then it falls back to `_sounds_by_name()`.
- **`_sounds_by_name()`** is built once, on first use, by walking **`game()/sounds/used/` only** (`paths.SOUNDS_USED`), in sorted order.
  - It maps each lowercase file name, with its extension, to the file's path.
  - The first copy in sorted order wins when a name is in several folders. The 2026-09-21 rescan confirmed that every copy of a name has the same channels, width and rate, so this is safe.
  - `set_game()` clears it, and `set_game(None)` goes back to the default places.
  - It never walks `unused/`. None of the 25 names in `unused/` is a `SoundList.plist` name anyway.
- **`paths.sounds()`** returns `game()/sounds/used` when that folder exists, otherwise `game()`.
- **Tests:**
  - The seven hand-built `os.path.join(paths.sounds(), name + '.wav')` lines now go through the lookup: three in `test_data.py`, one in `test_menu`, two in `test_pause` and one in `test_store`.
  - `test_data.py` has a new check, `test_every_sound_comes_from_the_sounds_folder`.
  - The new `tests/test_paths.py` builds tiny temporary bundles to check the lookup itself: a nested sound, `unused/` never searched, case, a shared sound, the top folder first, the plists and maps, a flat bundle, a missing sound, and switching bundles.
- **`compiler.py`:**
  - `sound_files()` copies `sounds/used/` with its folders.
  - `GAME_FILES` still matches the top folder, including `*.wav`, so a flat original bundle still builds. `unused/` is left out.
  - `data_summary()` reports the counts, and the dry run prints them. A build today copies 474 files: 329 sounds, plus 142 plists and 3 map layers.
- **The analysis tools** only read `SoundList.plist` and the binary from the top folder, so they needed no change.

**How to apply:** Never move, rename, convert or delete sound files unless the dev asks. A new sound goes anywhere under `game/sounds/used/` under its `SoundList.plist` name, as 8-bit or 16-bit PCM WAV, and the lookup finds it with no code change. Two files with the same name in different folders must be the same recording, because only the first one is ever used.
