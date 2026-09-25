---
name: project_sound_organization
description: "Every sound the game plays lives in game/sounds/used, in folders (a deliberate divergence); everything it never plays is in game/sounds/unused; since the dev's third sort on 2026-09-25 the zombies, bosses, monster and characters have one folder each, misnamed sounds are renamed, and SoundList.plist follows them with entry 371 added. How it was built and verified on 2026-09-21, and how the code finds the sounds (lookup rewritten the same day; tests pass and the dev confirmed it in play)."
metadata:
  node_type: memory
  type: project
  originSessionId: 8a78e7c9-236d-421e-8e76-c11a2895c278
---

**Every sound the game uses lives in `game/sounds/used/`**, in folders, under its original file name. They are no longer in the original bundle's flat folder. With the renamed `SoundList.plist` entry 290 (below), these are the only ways the port departs from the original's data; everything else stays faithful. It is documented in `aidocks/DIVERGENCES.md` under "The sounds are organized into folders" and "One sound list entry is renamed".

## The third sort, 2026-09-25 (commit `8fbf9fc`), and the renames
- **One folder each** for the zombies (`sfx/zombies/normal`), the bosses (`sfx/zombies/bosses`), the monster (`sfx/monsters`) and the characters (`sfx/characters`), under `used/` and `unused/`, with one file per name: the `normalcave1..12` / `normalforest1..12`, `bosscave`/`bossforest`, `monstercave`/`monsterforest` and `charcave`/`charforest` folders are gone. `used/` has 195 files, `unused/` 101, and the blooper clip moved to `game/sounds/bloopers/`, which is outside `paths.SOUND_FOLDERS`, so builds no longer carry it. A build is 441 files: 296 sounds and 145 plists and map layers.
- **The dev renamed sounds they found misnamed**, by ear, and `SoundList.plist` follows them, with entry 371 added for the bosses' own being-hurt sound: [[project_sound_rename_plan]] has the table. `stage_1_e.MONSTER_SOUNDS[KIND_BOSS]` uses 371 instead of zombie 9's 205.
- **Checking a sort: compare audio, not bytes.** On 2026-09-25 a byte check called 17 cave and forest pairs "different recordings" and "lost"; their samples were identical and only their WAV headers differed, and both matched the original's file in `user/SixthSenseSounds` (the dev's flat copy of the original 269, read-only) equally. Compare the samples, or against that folder, before calling a recording lost.
- The dev made two tries at this sort the same day before this one; the notes about them in the session are superseded.

## The second sort, 2026-09-24, commit `e299647` (superseded by the third)
- **`used/` holds only what the game plays: 236 files under 196 names.** `unused/` holds 126: 125 WAVs and the blooper OGG in `unused/bloopers/`. Every one of the 269 originals is in one folder or the other.
- **The dev's moves and renames:** the weapon sounds from `sfx/misc` to `sfx/weapons`; zombie 8's approach and push into `normalcave8` and `normalforest8`; "You can skip by using double tab" from `speech/tutorials` to `speech/game`; `zombies_boss_3_cave` and `zombies_boss_3_forest` renamed `zombies_boss_3_coming_cave` and `zombies_boss_3_coming_forest`.
- **`SoundList.plist` entry 290** (the forest boss's approach, `stage_1_e.py:157`) follows the rename, at the dev's request, or the boss would come in silently. It was rewritten with `plistlib` in binary after checking it re-saves byte for byte, so it is the only change. The cave rename needed nothing: no entry names it.
- **How the deletion was done:** the dev copied what the game never plays into `unused/`, then Claude deleted the 95 copies left in `used/`, each matched to its `unused/` copy by the audio data, not the name. A read-only trace of every candidate (loading on first play, the monster and weapon tables, the rows the port keeps) found 12 the game plays, and their loaded copies stay in `used/`: `man_die` (273), `weapon_knife_att2` (60), `weapon_japen_knife_att2` (73), `gun_att_sound_1` (56), `weapon_nonbullets` (78), the boss's hit and death (288, 289), `mission fail` (228), "You can skip by using double tab" (266), "you must use earphone" (234), `effective range` (256) and `this weapon has been purchased` (359). Eight folders left empty were removed. The dev keeps a backup of the layout before the deletion in `user/sounds` (read-only for Claude).
- **What the unused ones are:** kinds 11 and 12 (never spawned); the power saw (no shop page); the left-out rows (ranking, Game Center, coin and gold packs, restore, purchase all weapons); lines no row plays; the second logo 341; unlisted recordings such as the zombie shouts; extra copies; and the fifteen non-original files. A number whose file is only in `unused/` logs "sound file missing" and plays silence; it never crashes, and the port never asks for one in play.
- **Every name with several copies in `used/` has identical copies** (checked 2026-09-24: 28 names, 38 extra copies), so which one the lookup takes does not matter.
- **The lookup searches `unused/` last, and builds carry it** (the dev's request, 2026-09-24): `paths.SOUND_FOLDERS` is (`sounds/used`, `sounds/unused`), and `_sounds_by_name` indexes them in that order, so a name in `used/` always wins and the 45 sound list names now only in `unused/` still resolve. None of them is a non-original file, and `tests/case/data.py` checks the sound list never names one. `compiler.py` copies both folders (or embeds both), 507 files: 362 sounds and 145 plists and map layers.
- **The tests pass unchanged in what they expect of the sound list**: with the fallback, `test_sound_list_covers_the_wavs`, `test_monster_sounds_resolve_to_wavs` and `pause.py` pass as before. tunmi13productions' `8cb8f9d` and `bca782f` did part of the same move and a `data.py` fix; the dev chose not to bring them in, since this sort is the fuller one.

## The first layout (dev's reorganization, 2026-09-21)
- **`game/sounds/used/`** had 329 files covering **all 269** of the original's sounds:
  - `sfx/zombies/normal/normalcave1..12` and `normalforest1..12`
  - `sfx/zombies/bosses/bosscave1..3` and `bossforest1..3`
  - `sfx/characters/charcave1..2` and `charforest1..2`
  - `sfx/monsters/monstercave` and `monsterforest`
  - `sfx/weapons` and `sfx/misc`
  - `speech/game`, `logos`, `menus/main`, `menus/store`, `numbers`, `tutorials` and `weapons`
- **The extra 60 files are same-audio copies.** 38 sounds are shared between folders (for example the boss hit and death in all six boss folders, or `zombie_3_7_hit_player` in six zombie folders), since the original shares damage, death and hit sounds between areas and zombie kinds; only the "coming" loops differ.
- **`game/sounds/unused/`** held 27 files: 26 that are not the original's own, under their old sub-paths (25 until 2026-09-22; see the update below), and since tunmi13productions' `e08fd89` (2026-09-22) one blooper clip, `bloopers/stop_standing_by_the_zombie!.ogg`, which is not a game sound:
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

## The real `main menu button` turned up (2026-09-22)
The dev replaced `speech/menus/main/main menu button.wav` in `used/` themselves. What had been there was a trimmed cut that said only "main menu"; they found the original recording, which says the whole phrase, and put it in. It is mono, 1.41 s, 44.1 kHz, 16-bit, where the trimmed one was stereo and 1.86 s.
- The trimmed cut is kept in `unused/speech/menus/main/main menu.wav`. **The dev asked for it not to be deleted.**
- `unused/` therefore holds 26 non-original sounds now (27 files with the blooper clip), and the never-in-the-original group is fifteen rather than fourteen.
- Sound 355 is what the pause panel's last row reads, so this is what a player hears on the panel's "main menu" row.
- The 2026-09-21 audio matching found this file matched its namesake, since the trimmed cut is the same recording cut short. A name matching by ear beats a waveform match; if another trimmed cut turns up, the dev's ear decides.

## How the code finds the sounds (done 2026-09-21)
The dev approved the plan on 2026-09-21 ("I love it!"), and it was built the same day. **The full suite passed, 117 of 117**, with the dev's go-ahead ([[project_safe_test_run]]), and no "sound file missing" warning was printed. **The dev then played the game on 2026-09-21 and confirmed it finds its sounds** ("Everything worked!"). The todo item moved to finished as "The game finds its sounds in game/sounds/used again...".
- **`paths.path_for_resource(name, ext)`** is the one place every sound, plist and map is looked up. It is called from `oal_playback.py`'s buffer loader and its BG and AMB players, and also for the plists and maps.
  - It checks the `game()` top folder first, as the original did. That keeps the plists and maps unchanged, and keeps `--game` working on an untouched, flat original bundle.
  - Then it falls back to `_sounds_by_name()`.
- **`_sounds_by_name()`** is built once, on first use, by walking **`game()/sounds/used/` only** (`paths.SOUNDS_USED`), in sorted order.
  - It maps each lowercase file name, with its extension, to the file's path.
  - The first copy in sorted order wins when a name is in several folders. The 2026-09-21 rescan confirmed that every copy of a name has the same channels, width and rate, so this is safe.
  - `set_game()` clears it, and `set_game(None)` goes back to the default places.
  - It never walked `unused/` then; since 2026-09-24 it walks it last (above).
- **`paths.sounds()`** returns `game()/sounds/used` when that folder exists, otherwise `game()`.
- **Tests:**
  - The seven hand-built `os.path.join(paths.sounds(), name + '.wav')` lines now go through the lookup: three in `tests/case/data.py`, one in `menu.py`, two in `pause.py` and one in `store.py`.
  - `tests/case/data.py` has a new check, `test_every_sound_comes_from_the_sounds_folder`.
  - The new `tests/case/paths.py` builds tiny temporary bundles to check the lookup itself: a nested sound, `unused/` never searched (since 2026-09-24: searched last, and `used/` winning), case, a shared sound, the top folder first, the plists and maps, a flat bundle, a missing sound, and switching bundles.
- **`compiler.py`:**
  - `sound_files()` copies `sounds/used/` with its folders.
  - `GAME_FILES` still matches the top folder, including `*.wav`, so a flat original bundle still builds. `unused/` was left out until 2026-09-24, and is copied since.
  - `data_summary()` reports the counts, and the dry run prints them. A build then copied 474 files: 329 sounds, plus 142 plists and 3 map layers (507 since the second sort, with `unused/` copied too).
- **The analysis tools** only read `SoundList.plist` and the binary from the top folder, so they needed no change.

**How to apply:** Never move, rename, convert or delete sound files unless the dev asks. A new sound goes anywhere under `game/sounds/used/` under its `SoundList.plist` name, as 8-bit or 16-bit PCM WAV, and the lookup finds it with no code change. Two files with the same name in different folders must be the same recording, because only the first one is ever used.
