---
name: project_sound_trims_plan
description: "FINISHED 2026-09-27, confirmed by tunmi13productions (third design, with the hits and the headshot call). A per-sound gain table (trims in dB) that levels every sound in the game, music and ambience included, to one loudness, -12 LUFS, on AL_GAIN with AL_MAX_GAIN raised so boosts pass 1.0 (at most +12 dB); files and binary gains untouched. F8 in --debug compares."
metadata:
  type: project
---

**Status: FINISHED 2026-09-27, confirmed by tunmi13productions** ("much better I think", then "makr it completed, commit and push"). Kept as they are, by the dev's word: the gameplay gain's default of 0 ("I'd leave it at 0. that way the player can then crnak it up"), and F8 with `SOUND_TRIMS_ON` for comparing by ear later. The tool gives 192 trims, 19 cuts and 173 boosts; 11 files are too quiet to reach -12 LUFS within 12 dB (the breathing, the cave and forest ambience, the rain among them) and stop 12 dB up. The gun's hit comes down 2.5 dB, the killing hit up 0.5, the shotgun down 0.5, the zombies' hottest loops down about 6.5, `headshot_4` down 4, the menu music up 4. Tests: sound_trims 10, and the covering files all pass (sound_trims, volume, gameplay_volume, monster_sound, window, input, gameplay, weapon_range, tutorial, menu_music, music_memory, audio_device, paths, menu, pause, intro). `menu_music.py` holds the trims off, as `gameplay_volume.py` does, and `menu.py` expects the menu music's gain times its trim. Asked for by tunmi13productions on 2026-09-27 ("go with the per-sound gain table, write the plan first"), after finding that files "all sound mismatched in volume" and that "adding volume knobs will not negate the issue". Recorded before any code ([[feedback_record_plans_first]]). "The dev" in this note is tunmi13productions, who asked for all of it; the notes credited tsatria03 by mistake until tunmi13productions said so the same day. Builds on [[project_volume_knobs]] and [[project_gameplay_gain_plan]].

## History
- **First design, built 2026-09-27:** cuts on `AL_GAIN`, boosts on the samples as a file loaded, never past -1 dBFS. The dev listened: "it improved it, slightly? ish?".
- **Why it fell short:** most quiet files already peak at full scale, so the samples had no headroom and their boosts were capped at almost nothing (`zombie_1_coming_forest` sits 3.4 dB under its family and got 0). Measured the gap between the loudest and quietest file of each family: the median left 2.4 to 7.6 dB (entities coming 19.3 before, 7.6 after; speech 14.2, 4.2). The loudest-member target would have been worse, since it only boosts (entities coming 16.4, speech 13.0), so it was not tried.
- **Second design, chosen 2026-09-27** (tunmi13productions: "option 2", picking the median with boosts on the gain over levelling everything down to the quietest): every trim on `AL_GAIN`, with each source's `AL_MAX_GAIN` raised so a boost can pass 1.0. The first design's sample scaling, its memory cache and F8's buffer reloading are removed.
- **The second design, built 2026-09-27**, levelled every family to within 0.5 LU of its median (entities coming 19.3 LU before, 0.5 after), with 163 trims, the largest +10.5 dB.
- **Why it changed again:** the dev heard more imbalance, not less: "honestly I think we should not trim certain sounds. it only causes more imbalance. let's just apply this to every single sound in the game and even it out completely so there is a balance. for instnace, now bullet hits sound way quieter." The gun hit (-9.5 LUFS, among the loudest files) had been pulled 3.5 dB down to the knives' hits.
- **Third design, chosen 2026-09-27** (tunmi13productions: "let's try option 2", of three levels offered): one level for every sound, **-12 LUFS**. The game's median is -16.9 and 90% of files are under -11.9, so most sounds come up; the gun hit comes down only 2.5 dB and the shotgun (-11.7) barely moves. The median (-17, the gun hit -7.5 dB) and the loudest file (-4.8, nothing ever cut) were the other two.
- **The first two designs' families**, now dropped: entities coming, hurt, dying and attacking; weapons firing, handling and hitting; speech. They left the music, the ambience, the breathing, being hurt, dying, `ui_select`, `warring`, `woman_thank_u_kiss`, `zombie_8_approach`, `zombie_8_push` and the logo alone.

## What was found (2026-09-27)
- The port reads every WAV with Python's `wave` module (`game/oal_playback.py` `_load_wav`, `platform/music.py` `_load`). `soundfile` is not used. All 198 files in `used/` are 16-bit PCM (44,100 Hz, and five at 22,050 Hz), which `wave` hands over byte for byte, so the reader changes nothing.
- The mismatch is in the recordings themselves. The zombie and boss "coming" loops peak at 0 dBFS at about -5 LUFS; `player_breath_1` peaks at -31.8 dBFS; 50 files peak at or within 0.1 dB of full scale.
- OpenAL plays mono and stereo differently (mono is placed in space, stereo plays flat), and this plan does not compensate for it: the game's gains and placement decide how loud a levelled file is heard.
- **Proved on OpenAL Soft's loopback device, 2026-09-27** (rendered into memory, silent): with the default `AL_MAX_GAIN` of 1.0 an `AL_GAIN` of 2.0 plays at +0.00 dB, which is the cap; with `AL_MAX_GAIN` 4.0, gains of 2.0, 3.16 and 4.0 play at +6.02, +9.99 and +12.04 dB, exactly; and a full-scale tone at 4.0 comes out peaking at 1.000, held by the output limiter the port asks for (`ALC_OUTPUT_LIMITER_SOFT`).

## The design (third)
- **A table of trims, in dB, one per sound file**, keyed by file name without `.wav`. A file not in the table is untouched.
- **Every sound in `game/sounds/used/` is levelled to `TARGET_LUFS`, -12 LUFS**: the zombies, the weapons, the speech, the breathing, being hurt and dying, the music, the ambience, the rain, the UI click, the logo. No families, and nothing left alone but silence (a file with no measurable loudness).
- The game's own gains still set the mix on top, as the binary has them (a gunshot at 1.0, a spoken row at 0.2, the level music at 0.02, the ambience at 0.2), and every setting sits on top of that.
- **Loudness is integrated loudness (LUFS, ITU-R BS.1770)**, measured once offline by the tool. Trims are rounded to 0.5 dB; smaller ones are left out.
- **No boost is more than `MAX_BOOST_DB`, +12 dB** (a gain of 3.98, under the sources' 4.0). A few files are too quiet to reach -12 within it and stop 12 dB up: `bgm_cave_amb` needs +40.9, `player_breath_1` +38, `effect_forest_rainng` +27. Raising the cap would raise their hiss too, so it stays.
- **Every trim goes on `AL_GAIN`**: in `oal_playback._gain` for the sound sources, and in `platform/music.py`'s `_heard` for the music and ambience players, whose sources get the same raised `AL_MAX_GAIN`. The game's own gain is capped at 1.0 first, as OpenAL capped it before, then the trim multiplies it. Past full scale the output limiter holds the peaks.
- Every file loads bit for bit as it is on disk.

## What is built
- **`sixthsense/platform/sound_trims.py`**: `MEASURED` (written by the tool), `BY_EAR` (the dev's own, which win and which the tool never touches), `MAX_GAIN`, and `trim_db`, `gain` (what `AL_GAIN` is multiplied by). A Python module, so PyInstaller bundles it with no change to `compiler.py`.
- **`tools/sound_trims.py`**: measures every file in `game/sounds/used/`, prints one line per file (folder, loudness, peak, trim) for NVDA, and rewrites only `MEASURED`; `--dry-run` only prints. Standard library only; makes no sound.
- **`platform/openal.py`**: `AL_MAX_GAIN`.
- **`platform/music.py`**: `_ensure` raises the source's `AL_MAX_GAIN`; `_heard` caps the game's gain at 1.0 and multiplies in the playing file's trim, so the music and the ambience are levelled too and F8 reaches them through `refreshGains`.
- **`game/oal_playback.py`**: `_gain` applies the trim after capping the game's gain at 1.0; `initSourceOne_` raises `AL_MAX_GAIN`; `setSoundTrims_` flips the switch and reapplies every gain through `refreshGains`, playing sounds included.
- **`volume.SOUND_TRIMS_ON`**: True; at False every sound plays as the file is.
- **F8 in `--debug`** (tunmi13productions, 2026-09-27: "make a debug key"): a keymap action (`debug_sound_trims`), rebindable, listed on the F1 screen and in the window's debug line only in debug mode, and working in the tutorial too. It flips `SOUND_TRIMS_ON` at once for every sound, the playing ones included, and says "Sound trims off" or "Sound trims on". It lasts until the game closes.
- **Tests**, `tests/case/sound_trims.py`: every trimmed name is a file in `used/`; every measurable file is in the table unless already within 0.25 dB of the target; the music and ambience players hear their file's trim; no boost passes `MAX_BOOST_DB`; every file loads bit for bit; a cut and a boost are heard on `AL_GAIN`, a boost above 1.0; a sound's `AL_MAX_GAIN` is raised; the game's own gain above 1.0 is still capped at 1.0 before the trim; `BY_EAR` wins; the switch turns everything off; F8 flips it, speaks and reaches playing sounds; the loudness measure matches BS.1770. `gameplay_volume.py` holds the trims off, since it checks the settings alone; `monster_sound.py` expects the headshot callout at 0.1 times its trim.
- **Docs**: DIVERGENCES (the volumes entry and the debug keys), CLAUDE.md, README.md, tools/README.md, [[project_volume_knobs]], and a changelog line. `docks/readme.txt` does not list the debug keys, so it is not changed.

## The hits and the headshot call (added 2026-09-27)
The dev, on the third design: "it's improved a lot, ut why are the weapon hit sounds not playing loud enough? and their headshots?" What was found, from the code and the binary:
- **The hits fade 2.5 times sooner than the zombies.** A zombie's own sounds go through `MonsterQueueNote:` (0xe188), with `AL_REFERENCE_DISTANCE` 100 and `AL_MAX_DISTANCE` 1600; every hit on it goes through the ordinary `queueNote:` (0xe028), 40 and 800, at the zombie's `Pos`. So past 100 a hit is always about 8 dB under the zombie it lands on (20 log 40/100), and at 500 it is 22 dB under the gunshot beside you.
- **The impact asks for 2.5** (`playerHitSoundGain * 2.5`, 0x12110, with `playerHitSoundGain` 1.0 in every `typeN.plist`) and always got 1.0, since OpenAL caps a source at 1.0. The trims keep that cap, so nothing changes here.
- **The headshot call, `headshot_4` (330), plays at 0.1** (0x3a24a), half a spoken row's 0.2, and levelling took 4 dB off it (it was -8 LUFS). The gun's hit lost 2.5 dB the same way.

**Chosen (tunmi13productions, 2026-09-27: "1 and 3"):**
1. **Every weapon hit fades like the zombie it hits**: the impact (56, `MonsterHitSound:`), the killing hit (79, `MonsterDamage`) and the blades' `att1` and `att2` (`MonsterDamageKnife`) are queued with the zombie's reference and maximum distance, 100 and 1600, through a new `AppDelegate.playHitSound_Gain_Pos_z_` (`MonsterQueueNote:`), instead of 40 and 800. A hit close by is as loud as before; one further off is up to 8 dB louder, level with the zombie. Gains and positions stay the binary's.
2. **The headshot call plays at 0.2**, level with every spoken row, instead of the binary's 0.1: 6 dB up. It stays in the centre, being stereo.
- Not chosen: letting the impact's 2.5 through (about 8 dB more, the limiter working harder close up), and hand trims in `BY_EAR`.
- Both are PORT DIVERGENCEs, recorded in `aidocks/DIVERGENCES.md`, with two changelog lines. **Built and confirmed 2026-09-27.** Tests: `monster_sound.py`'s headshot test checks the call at 0.2 times its trim and the gun's hit at 100 and 1600; `gameplay.py`'s gun-impact and knife tests also listen on `playHitSound`. The covering files pass: monster_sound 9, gameplay 55, weapon_range 13, tutorial 19, pause 26, input 27, sound_trims 10, gameplay_volume 7, menu 34, intro 14, digits 3, store 20, focus 4.

## Commits
The plan went in as its own commits, local only; the code follows once the dev has tested it by ear and it is marked finished; then all of it is pushed together ([[feedback_record_plans_first]]).

## Follow-up
- 2026-09-28: the levelling left the bosses too quiet, so `BY_EAR` boosts their two approach loops 3 dB ([[project_boss_loudness_plan]]).
- 2026-09-28: the zombies, bosses, monster and woman are never cut, only boosted ([[project_entity_full_volume_plan]]).
