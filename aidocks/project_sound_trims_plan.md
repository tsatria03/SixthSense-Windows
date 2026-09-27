---
name: project_sound_trims_plan
description: "PLANNED 2026-09-27. A per-sound gain table (trims in dB) that evens out the original's badly matched recordings, applied to the samples as each WAV loads, so the files and the binary's gains stay untouched. Sounds are levelled within families (zombie growls with zombie growls, speech with speech), never against the whole game."
metadata:
  type: project
---

**Status: planned, waiting for the go-ahead.** Asked for by tsatria03 on 2026-09-27 ("go with the per-sound gain table, write the plan first"), after finding that files "all sound mismatched in volume" and that "adding volume knobs will not negate the issue". Recorded before any code ([[feedback_record_plans_first]]). Builds on [[project_volume_knobs]] and [[project_gameplay_gain_plan]].

## What was found (2026-09-27)
- The port reads every WAV with Python's `wave` module (`game/oal_playback.py` `_load_wav`, `platform/music.py` `_load`). `soundfile` is not used. All 198 files in `used/` are 16-bit PCM (44,100 Hz, and five at 22,050 Hz), which `wave` hands over byte for byte, so the reader changes nothing.
- The mismatch is in the recordings themselves. Measured peak and RMS:
  - The loudest, the zombie and boss "coming" loops, peak at 0 dBFS with an RMS of about -5 to -6 dBFS.
  - The quietest, `player_breath_1`, peaks at -31.8 with an RMS of -50; `bgm_cave_amb` has an RMS of -57.
  - 50 files peak at or within 0.1 dB of full scale, so some were probably clipped when they were made.
- OpenAL also plays mono and stereo differently: mono is placed in space (distance, panning, about -3 dB per speaker at the centre), and stereo plays flat. Here that splits cleanly along the families below (the entity and weapon sounds are mono; the speech is stereo), so levelling within a family is not thrown off by it, and this plan does not compensate for it.
- The global knobs cannot fix any of this, since they move whole groups together.

## The design
- **A table of trims, in dB, one per sound file**, keyed by file name without `.wav`, the way `SoundList.plist` names them. 0 dB, or a file that is not in the table, means untouched.
- **Applied to the samples as the file loads**, in `_load_wav`, after the `MONO_AT_LOAD` fold: each 16-bit sample is multiplied by `volume.gain(trim)` and clamped to the 16-bit range. A file with no trim is passed through without being touched, so it stays bit for bit what it was.
  - Why at load and not on `AL_GAIN`: a source's gain stops at 1.0, and gunshots, the zombies' loops and others already play at 1.0, so a trim there could only turn sounds down. At load, a quiet file can come up too.
  - Every gain the game plays stays the binary's own value, and every knob and setting still sits on top as it does now. The sound files on disk are never changed ("don't move, rename, convert or delete sound files").
- **Levelled within families, not across the whole game.** The binary's gains already set the balance between kinds of sound (a gunshot at 1.0, a spoken row at 0.2, the breathing at 0.5), and levelling everything to one loudness would undo that. Instead, each file is brought to its family's median loudness, so a family's typical sound stays where it is and only its outliers move.
- **Loudness is measured as integrated loudness (LUFS, ITU-R BS.1770)**: K-weighted and gated, so silence and short clicks don't skew it. This matches what the ear hears more closely than peak or plain RMS. The measuring is done once, offline, by a tool (below), and never while the game runs.
- **Boosts are limited by the file's headroom**: a trim never raises a file's peak above -1 dBFS, so levelling never clips. Cuts have no limit. Trims are rounded to 0.5 dB, and a trim smaller than 0.5 dB is left at 0.

## The families (a first sort, from the file names; the dev confirms or moves them)
- **Entities coming**: every `*_coming_cave` and `*_coming_forest` (zombies, bosses, the monster, the woman).
- **Entities hurt**: `zombie_*_damage`, `zombies_boss_1_damage` (the bosses' being-hurt sound, entry 371) and `man_monster_hit`.
- **Entities dying**: `zombie_*_die`, `zombies_boss_1_die`, `man_monster_die`, `woman_die`.
- **Entities attacking**: `zombie_*_hit_player`, `zombies_boss_1_hit_player`.
- **Weapons firing**: every `weapon_*_fire`, the knives' and the sword's swings included.
- **Weapons handling**: the reloads, `weapon_japen_knife_draw` and `weapon_gun_nonbullets`.
- **Weapon hits**: `weapon_gun_att1`, `weapon_gun_att2` and the knives' and the sword's `_att1` and `_att2`.
- **Speech**: everything in `speech/` except the logo, so the menus, the numbers, the game's callouts, the weapon names and the tutorial all sit at one loudness. This matters most for the numbers, which are read one after another.
- **Left alone (no trim)**, because their loudness is probably intended or they have nothing to be compared with: the music and the ambience (`bgm_*`, `effect_forest_rainng`), `player_breath_1` to `3` (quietest first, perhaps on purpose, as the player tires), `player_damage`, `player_die`, `ui_select`, `warring`, `woman_thank_u_kiss` and the logo `bitbee_1`. So `platform/music.py` is not changed at all.
- **Weapons firing stays a family** (tsatria03, 2026-09-27: "level the weapon firing"). The per-gun volume declined on 2026-09-26 was a player setting; this is a fixed table no player sees, and it evens the guns out (the shotgun is about 3 dB louder than the AK).
- **The breathing, being hurt and dying stay untouched** (tsatria03, 2026-09-27: "leave the breathing and dying alone").

## What is built
- **`sixthsense/platform/sound_trims.py`**: two dicts.
  - `MEASURED`: written by the tool, the family-levelling trims.
  - `BY_EAR`: the dev's own trims, written by hand after listening. One here replaces the measured one for that file, and the tool never touches it.
  - `trim_db(name)` returns the one that applies, or 0.0.
  - A Python module rather than a JSON file, so PyInstaller bundles it with no change to `compiler.py`.
- **`tools/sound_trims.py`**: measures every file in `game/sounds/used/`, sorts them into the families, and rewrites only `MEASURED`. It prints a plain list, one line per file, with its family, loudness, peak and trim, for reading with NVDA. It needs no new package: the K-weighting filters are two biquads written out in Python. It makes no sound.
- **`game/oal_playback.py`**: `_load_wav` applies `sound_trims.trim_db(name)` to the samples.
- **A switch to hear the difference**: `volume.SOUND_TRIMS_ON = True`, a constant; at False every file loads untouched.
- **A debug key to compare by ear** (tsatria03, 2026-09-27: "make a debug key"): **F8**, free among the debug keys (F2, Shift+F2, F5, Shift+F5, F6, F7, F11). Only with `--debug`, like the others: a keymap action in `game/debug.py`, rebindable, and listed on the F1 screen only in debug mode. It flips `SOUND_TRIMS_ON` and reloads every buffer that is loaded, so the next sound played is heard the other way; it says "Sound trims off" or "Sound trims on" in both speech modes. A sound already playing, such as a zombie's loop, is stopped and started again from the reloaded buffer, since OpenAL cannot swap a playing buffer. The flip lasts until the game closes and is never saved.
- **Tests**, `tests/case/sound_trims.py`, silent like the rest ([[project_safe_test_run]]):
  - every trimmed name is a file that exists in `used/`;
  - no trim raises its file's peak above -1 dBFS;
  - a file with no trim loads bit for bit as it is on disk;
  - a trimmed file loads scaled by the right amount, and clamped at full scale;
  - `BY_EAR` wins over `MEASURED`;
  - with `SOUND_TRIMS_ON` False, nothing changes;
  - F8 flips the switch, reloads the loaded buffers and speaks, and does nothing without `--debug`.
- **Docs**: the F8 line in `game/debug.py`'s docstring and in CLAUDE.md's `--debug` list, `aidocks/DIVERGENCES.md` (a new entry: the port levels the recordings, the files stay the original's), [[project_volume_knobs]] (a pointer here), a changelog line, and a line in `docks/readme.txt` only if the dev wants players told.

## Settled on 2026-09-27
- Weapons firing is levelled; the breathing, being hurt and dying are left alone; there is a debug key, F8 (above). The rest of the families are the first sort as written, and the dev can still move a file once they hear it.

## Still open
- Is the family median the right target, or should a family be brought to its loudest member (fewer cuts, more boosts, where the headroom allows)?

## Commits
The plan goes in as its own commit, local only; the code follows once the dev has tested it by ear; both are pushed together ([[feedback_record_plans_first]]).
