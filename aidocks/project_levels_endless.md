---
name: project_levels_endless
description: "The original has no last level and no win: verified 2026-09-22 from the raw instructions. From about level 9 zombies arrive on their first step. The bundle holds unused art for a 19-stage select screen."
metadata:
  type: project
---

Checked on 2026-09-22 from the raw Thumb disassembly (`tools/dz.py 0x2c700 0x3ec00`), after the dev reached level 16 with `--debug`'s F2 and zombies attacked the moment they appeared.

- **No level cap.** `MainControl` 0x31c72..0x31c82 is `ldr; adds r2, #1; str` on `LVUP`, with no compare. `ChangeLevel:` 0x32314..0x32348 is `vmul.f32` of `monsterHPGain` by 1.5, with no compare. `LVUP` is otherwise read only by `MakeMonster:` (0x3612a, the `LVUP + 2` monster cap) and written by `viewDidLoad` and the restart.
- **No win.** `-[Stage_1_E MissionSuccessTell]` exists and its selector is in `__objc_selrefs`, but nothing in `Stage_1_E` sends it. The only sender is `-[Stage_1_TEST MainControl]` (0x45d98), the weapon test range behind the shop's Try button. A normal run ends only on death.
- **Why high levels break.** Health and step are multiplied by `monsterHPGain` = 1.5^(level-1) (0x10704, 0x10832), and zombies start 10 m out (`START_RANGE`) with the first step taken at once. Zombie 1 (30 HP, 40 cm step) needs about 25 steps on level 1, 5 on level 5 and 2 on level 8. From level 9 its first step lands on you, and on level 16 it has about 13,000 HP.
- **Not everything scales.** The girl and the woman zombie are built with HPGain 1.0 (0x38d8c, 0x39034), so they keep level 1's speed and health; zombies and the boss scale.
- **Unused stage-select art.** The bundle has `3_stage_btn_01..19` (with `_act`), `3_stage_btn_endless_*`, `_lock_*` and `_tut_*`. No code and no nib names them, so 19 stages plus an endless mode were drawn but only the endless run shipped.

**How to apply:** capping levels would be a divergence and is the dev's decision. It was offered on 2026-09-22 as a cap in debug mode only or for everyone, with no answer yet. See [[project_evaluation_2026_09]].
