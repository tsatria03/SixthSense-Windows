---
name: project_volume_knobs
description: "sixthsense/platform/volume.py (built 2026-09-22): decibel knobs that move groups of sounds - master, level music, ambience, and the menu music in full - while every gain the game plays stays the binary's own value. How it is wired and how to tune it."
metadata:
  node_type: memory
  type: project
---

**Built 2026-09-22**, at the dev's request ("convert all volumes to use db if possible ... a constant for master volume, and gameplay related volumes"). They chose the design that keeps the binary's gains exact and puts the decibels in knobs on top.

## What is where
- **`sixthsense/platform/volume.py`** holds the knobs and the two conversions:
  - `gain(db)` is `10 ** (db / 20)`, and `decibels(g)` is `20 * log10(g)`; silence comes back as `-inf`.
  - `MASTER_DB`, `MUSIC_DB`, `AMBIENCE_DB` are **trims**, all 0.0 dB as shipped, which multiplies by exactly 1.0, so the mix is the binary's bit for bit until one is turned.
  - `MENU_MUSIC_DB` is **the whole value**, -14.0 dB, because the original never plays music on its menu and so has no gain to sit on top of.
  - `master()`, `music()`, `ambience()` and `menu_music()` are what callers use.
- **`MASTER_DB` is applied in `oal_playback`**, at every place `AL_GAIN` is set (`_configure`, `startSound_Postion_soundGain_`, and both music players), so it covers sound effects, the recorded speech and music without any caller remembering it.
- **The group trims are applied at the call site**, because only the caller knows what kind of sound it is starting: `stage_1_e.MapInitInBundle` and `continueAction_` (ambience and rain), the action-cell-10 branch in `MainControl` and `intro.shakeDevice` (music), `app_delegate.BGMusicStart` (the menu music).
- **`tests/case/volume.py`** has 7 tests: the scale, the round trip, the knobs at rest passing the binary's values through untouched, one knob moving only what it owns, and the menu music never louder than a spoken row (0.2). `tests/case/menu.py` checks `BGMusicStart` uses `volume.menu_music()`.

## The numbers, for reference
Gains in the game, with their decibels: 1.0 is 0 dB (gunshots), 0.5 is -6 dB (breathing, rain, the result panel), 0.2 is -14 dB (every spoken row, the ambience), 0.05 is -26 dB (the intro's story music, 0x17224), 0.02 is -34 dB (the level music, 0x321d4). OpenAL clamps a source above 1.0, so a bigger number buys nothing.

## The menu music
`bgm_main_menu` is a port addition. It played at 1.0 and talked over the menu's own rows. On 2026-09-22 the dev tried 0.05 ("too quiet"), then 0.1 ("too quiet"), and settled on 0.2, which is -14 dB, level with the rows. **The music itself is deliberate** - the dev added it on purpose and said so the same day ("I added menu music on perpis"), so don't propose removing it for fidelity.

**Why:** Decibels are how the dev thinks about loudness, and a knob per group lets them tune by ear without touching values recovered from the binary ([[project_binary_analysis_notes]]).

**How to apply:**
- Never replace a binary gain with a decibel constant. Add a trim if a group needs moving.
- A new kind of sound that the original has no gain for gets its own absolute `*_DB` constant, as the menu music has.
- These are constants, not saved settings. Settings would be a JSON file in `%APPDATA%\SixthSense` beside `defaults.json` and `keys.json`; the reference project in `user/` splits its own defaults into save, settings and keys files and stores its menu music as a percentage in steps of ten ([[feedback_no_other_games]]: don't name it).
- Changing a shipped knob is a player-facing change, so it needs a changelog line ([[feedback_changelog]]).
