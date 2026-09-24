---
name: project_test_range
description: "Stage_1_TEST, the weapon test range behind the shop's Try button, was ported on 2026-09-22 as game/stage_1_test.py, a subclass of Stage_1_E. What it does, from the raw instructions, and where the port differs."
metadata:
  type: project
---

Ported 2026-09-22 at the dev's request ("follow the game", "match the original exactly"). It is `sixthsense/game/stage_1_test.py`, subclassing `Stage_1_E`. 38 of the 241 shared methods differ; the ones that matter were read in the raw disassembly (`tools/dz.py`), the rest reuse the stage's.

- **Try** (`DetailStoreController testAction:` 0x1c1c0) plays 10 and pushes the range with `setTestWeapon:`. The jump table at 0x1c1f2 maps weaponType 1..6 to slots 3..8, anything else to 0 (`TEST_WEAPON`).
- **Setup**: `isTutorial = 1` (0x409c2); the area is `(arc4random() & 1) + 1` (0x40fce), the cave or the forest, never the rain; the player gets only the test weapon (0x40be0). `gunChangeAction:` is `bx lr` (0x49198). `weaponInit` plays the sword's draw (329) for slot 7 and the saw's idle (74, looping) for slot 8.
- **MainControl** (0x459d4) never walks. Five kills (0x45be6) stop 88 and 92, play 90 (`bgm_game_complete`) and send `MissionSuccessTell` 8 s later. Otherwise `monster_num = 1` before `MakeMonster:` (0x45f12), so it spawns tier 1, up to three at once. HP == 0 plays 84 and `playerDie:` 1.3 s later. Then `walkXFlag = 1` and `timerLeft` after 0.6 s.
- **Gold** is `int(score * 0.12)` (0x46aa2, and 0x4f7d4 for the panel), paid on a win and on a death. The win and the death both say 354, "game over".
- **Panel** (0x43c24): rows 1..8. Row 1 is 227 / 228 / 229 by state, row 6 speaks only when paused (223) and is silent otherwise, and row 8 is back (13). There is no rank or top score. Restart (0x46d70) costs no coin. `GameEndAction:` pops back to the weapon's page.
- **Differences** are recorded in DIVERGENCES.md ("The weapon test range"): the VoiceOver alert and the Dropbox map fetch on restart are left out, GOLD is synchronized on a death, the rest is matched, including row 6 staying on the panel, silent after a win or a death.
- **Only zombies.** The girl and the woman come only from action cell 8 (0x45de8), and you stand on (20, 680), which is cell 9, so they never appear. `MakeMonster:` is the stage's own, and tier 1 is kinds 1 and 2. Checked in the raw code at the dev's question on 2026-09-22.
- `tests/case/weapon_range.py` covers it. Its todo line is in `##Finished.`, saying the Try button has been added, at the dev's word on 2026-09-22.
