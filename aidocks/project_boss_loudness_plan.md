---
name: project_boss_loudness_plan
description: "FINISHED 2026-09-28, confirmed by tunmi13productions. The levelling cut the two bosses' approach loops 5 and 6 dB, leaving them level with the zombies and under the mix; BY_EAR now boosts both 3 dB instead, putting the boss back where it stood in the mix."
metadata:
  type: project
---

**Status: FINISHED 2026-09-28, confirmed by tunmi13productions** ("it's perfect now"). Tests: sound_trims 11 pass. Follows [[project_sound_trims_plan]].

## What was found
The dev, 2026-09-28: "I think we broke the volume of the boss by doing what we did. now it's very, very quiet."
- The bosses' approach loops are among the loudest recordings: `zombies_boss_1_coming_cave` (286, the cave boss) at -6.8 LUFS and `zombies_boss_3_coming_forest` (290, the forest boss) at -6.2. Levelling to -12 LUFS cut them 5 and 6 dB.
- The boss's plists (`type5003`, `type5008`) ask for the same approach gain as zombie 1, 0.2 + 0.2 = 0.4. Its loudness came from the file alone: before the trims it was 6 to 13 dB over the zombies' loops.
- The trims boosted most other sounds (the game's median was -16.9 LUFS), so the boss fell about 8 to 10 dB against the mix.

## Chosen
Offered: (1) no trim on the two loops, (2) a 3 dB boost on them, putting the boss back where it stood in the mix, (3) also exempting the boss's hit on you and its death. The dev: "put the boss back", which is option 2, and not option 3.
- `BY_EAR` in `sixthsense/platform/sound_trims.py`: `zombies_boss_1_coming_cave` +3.0 and `zombies_boss_3_coming_forest` +3.0. `tools/sound_trims.py` never touches `BY_EAR`, so remeasuring keeps them.
- Left as measured: the boss's hurt (371, +11.5), death (-0.5) and hit on you (-3.0), and the two boss files the game never plays (`zombies_boss_1_coming_forest`, `zombies_boss_3_coming_cave`).
- `tests/case/sound_trims.py` checks the two entries. The DIVERGENCES volumes entry and a changelog line say so.
- The dev can change the 3 dB by ear in `BY_EAR`; F8 in debug mode turns every trim off at once, for comparing.
