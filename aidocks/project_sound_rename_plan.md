---
name: project_sound_rename_plan
description: "PLANNED 2026-09-25, not built. The dev's third sound sort flattens the zombie, boss, monster and character folders and renames sounds they found misnamed (the 'woman' monster is a man; shared zombie sounds split per zombie). SoundList.plist entries are pointed at the new names, and a new entry 371 gives the bosses their own being-hurt sound. Recorded before any code."
metadata:
  type: project
---

**Status: PLANNED, 2026-09-25.** Agreed with the dev, recorded before any code ([[feedback_record_plans_first]]). Mark it finished only once the dev says it works.

**The dev's third sort** of `game/sounds` (2026-09-25), after two tries the same day: the per-zombie folders (`normalcave1..12`, `normalforest1..12`), the boss, monster and character folders become one folder each (`used/sfx/zombies/normal`, `used/sfx/zombies/bosses`, `used/sfx/monsters`, `used/sfx/characters`, and the same under `unused/`), with one file per name. Sounds they found misnamed in the binary are renamed, by ear:
- The "woman" monster sounds like a man: `woman_coming_cave_monster1` -> `man_coming_cave_monster`, `woman_coming_forest_Monster` -> `man_coming_forest_Monster`, `woman_like_monster_hit` -> `man_monster_hit`, and its death `man_die` -> `man_monster_die`. (Not the girl who heals you, whose files are `woman_*` in `characters`.)
- Sounds the original shares between zombies are named for one zombie: `zombie_2_4_hit_player` -> `zombie_2_hit_player`, `zombie_3_7_hit_player` -> `zombie_3_hit_player`, `zombie_9_10_damage` -> `zombie_9_damage`, `zombie_9_10_die` -> `zombie_9_die`, so that a zombie can be given its own file later.
- The bosses: `zombies_boss_big_die` -> `zombies_boss_1_die`, `zombies_boss_2_hit_player` -> `zombies_boss_1_hit_player`, the second boss's two coming sounds swapped; and a new `zombies_boss_1_damage`, a copy of zombie 9's being-hurt recording.
- Unused: `zombies_11_walk_cave` / `_forest` -> `zombies_11_coming_cave` / `_forest`, `zombies_12_coming1` -> `zombies_12_coming_cave`, `zombies_12_coming` -> `zombies_12_coming_forest`; the characters' `hurt1`, `hurt2` -> `man_damage_1`, `woman_damage_1` and so on.

**Checked before planning:** every file removed has its audio kept under another path; nothing audible was lost. Several names looked lost by bytes (the cave and forest copies of zombies 2 to 9's sounds, and the cave `woman_like_monster_hit`), but each pair had identical samples and differed only in its WAV header; both match the original's file in `user/SixthSenseSounds` equally (0.986 to 0.999, the codec noise the port's copies carry). So the game sounds exactly as before once the names are pointed at.

## The dev's decisions
- Zombies 4, 5 and 7 hit you with zombie 2's or 3's sound, and zombie 10 is hurt and dies with zombie 9's, as in the original: they have no files of their own.
- Boss 3 (the forest boss, going by its coming sound 290) reuses boss 1's (the cave boss's) being-hurt and dying sounds, in the cave and the forest.
- The bosses get a being-hurt sound of their own, `zombies_boss_1_damage`, instead of borrowing zombie 9's entry 205, so changing one never changes the other.

## What changes
`game/SoundList.plist`, rewritten with `plistlib` in binary as entry 290 was (2026-09-24), checked to change only these entries:

| entries | from | to |
|---|---|---|
| 120-122 | zombie_2_4_hit_player | zombie_2_hit_player |
| 135-137 | zombie_3_7_hit_player | zombie_3_hit_player |
| 205-207 | zombie_9_10_damage | zombie_9_damage |
| 208-210 | zombie_9_10_die | zombie_9_die |
| 271 | woman_coming_cave_monster1 | man_coming_cave_monster |
| 272 | woman_coming_forest_Monster | man_coming_forest_Monster |
| 273 | man_die | man_monster_die |
| 274 | woman_like_monster_hit | man_monster_hit |
| 289 | zombies_boss_big_die | zombies_boss_1_die |
| 292-294 | zombies_11_walk_cave | zombies_11_coming_cave |
| 295-297 | zombies_11_walk_forest | zombies_11_coming_forest |
| 304-306 | zombies_12_coming1 | zombies_12_coming_cave |
| 371 (new) | - | zombies_boss_1_damage |

Entry 273 was already quietly wrong: `man_die` was only in `unused/` since the second sort, found because the lookup searches it last.

In the code, `stage_1_e.MONSTER_SOUNDS[KIND_BOSS]`'s being-hurt list goes from `[205]` to `[371]`, a PORT DIVERGENCE with a comment. Nothing else in the code names a sound by these names.

## Tests and docs
- `tests/case/data.py` already checks that every sound number the monster tables use resolves to a WAV; it is extended to the boss's 371, and a check that every entry above names a file.
- `aidocks/DIVERGENCES.md`: the renames, as the dev's own, by ear, with the reasons; the new entry 371; the "woman" monster being a man. [[project_sound_organization]] gains the third sort. A changelog entry, since the boss now has a being-hurt sound of its own entry (it sounds the same).
