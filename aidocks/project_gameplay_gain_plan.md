---
name: project_gameplay_gain_plan
description: "PLANNED 2026-09-26. A gameplay gain of 0 to 6 dB (listener gain up to 2.0) that raises every sound during play without changing the balance, plus weapons, entities and player volumes (0 to 100) to change the balance. Page Up and Page Down with modifiers during play, saved in settings.json, spoken in both modes."
metadata:
  type: project
---

**Status: planned, 2026-09-26.** Agreed with the dev, recorded before any code ([[feedback_record_plans_first]]). Builds on [[project_volume_knobs]] and [[project_volume_settings_plan]].

**The dev's request:** "is there possibly a way to increase game volume without affecting zombies overall? ... I could crank up, say, gameplay volume or something, so I can hear the zombies better. but without messing with zombie volumes and screwing them up. sort of like a gain knob". Then: "should we make individual volumes then? weapons volume, zombie volume, that sort?"

## Why a listener gain
- Every existing volume multiplies a source's own `AL_GAIN`, which OpenAL caps at 1.0, and gunshots already sit at 1.0, so those can only turn down.
- OpenAL's listener `AL_GAIN` comes after the mix and may go above 1.0. The game never sets it today, so it is 1.0.
- It raises every source by the same amount, so the zombies' near and far, the five lanes and one zombie against another all stay the binary's.
- Past full scale, OpenAL Soft's output limiter (on by default) squeezes the peaks rather than clipping.

## The gain
- **0 to 6 dB, whole numbers, 1 dB a step**, so at most a listener gain of 2.0. The dev chose 2.0 as the cap ("the safest gameplay cap would be, say, 2.0") and decibels for the file ("0 to 6 might be better"). 0, the default, is today's mix.
- **During play only**: the stage, the tutorial and the test range. The listener goes back to 1.0 on leaving them, so the menus are untouched.
- **What it raises:** every sound effect and the recorded speech. The dev: speech should "follow the gain", with no volume of its own.
- **What it leaves alone:** the level music and the ambience, which are OpenAL sources too. Their gain is divided by the listener gain so they sound as they do now (their gains, 0.02 to 0.5, stay under the 1.0 cap at 2x). They keep `LEVELMUSICVOLUME` and `AMBIENCEVOLUME`.

## The group volumes
0 to 100 percent, 10 a step by key, any whole number by hand, squared into the gain like the other volumes; 100, the default, is the binary's mix. Only down, because of the 1.0 cap; the gain is the way up (turning weapons down and the gain up makes the zombies louder than the guns).
- **Weapons:** `sfx/weapons/` (fire, reload, the empty click, the knives' draw and swing).
- **Entities:** `sfx/zombies/normal/`, `sfx/zombies/bosses/`, `sfx/monsters/` and `sfx/characters/` (the zombies' and the monster's steps, growls, attacks, being hurt and deaths, and the woman). The dev, 2026-09-26: "I say we group characters and zombies into a single thing, like entities".
- **Player:** `player_breath_1` to `3`, `player_damage` and `player_die` (in `sfx/misc/`).
- Everything else (`warring`, `ui_select`, the speech) has no group and follows only the master volume and the gain.
- A sound's group is decided from its file's folder or name when its buffer is loaded, and applied in `oal_playback` beside `volume.master`, so no caller has to remember it.
- A change applies at once to sounds already playing (the breathing, a zombie's loop), so each source keeps the gain the game asked for and has the knobs reapplied.

## The keys, during play only
Fixed, not rebindable, like the menu music's; the F1 screen lists them. On the menu screens Page Up and Page Down stay the menu music.
- **Page Up / Page Down:** the gain, 1 dB.
- **Shift + Page Up / Page Down:** weapons, 10%.
- **Control + Page Up / Page Down:** entities, 10%.
- **Alt + Page Up / Page Down:** player, 10%.
- Each press is saved to `settings.json` at once and spoken in both speech modes, since there is no recording for it: "Gain 3 decibels", "Entities 70 percent". At the end of the range it says the value again.

## settings.json
New keys after `AMBIENCEVOLUME` and before `EYEMODE`: `GAMEPLAYGAIN` (0 to 6, anything else counts as 0), `WEAPONVOLUME`, `ENTITYVOLUME`, `PLAYERVOLUME` (0 to 100, anything else counts as 100). Written with their defaults on the first start, like the others.

## Tests and docs
- `tests/case/volume.py`: defaults leave every gain exactly the binary's; each group moves only its own sounds; the gain sets the listener and leaves music and ambience as they were; bad values fall back; the keys step, hold at the ends and save.
- `docks/readme.txt` (the keys and the settings), `README.md`, `aidocks/DIVERGENCES.md` (the volume knobs entry), `project_volume_knobs.md`, the F1 screen's fixed keys, and a changelog line.
