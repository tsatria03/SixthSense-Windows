---
name: project_tutorial_ending_plan
description: "FINISHED 2026-09-23, confirmed by the dev: how the tutorial ends, from the binary. P (the original's three-finger double tap, beat Nine) ends it once beats One to Eight are done; from the menu row it goes back to the menu, and on a first Start (a coin spent) it counts 3, 2, 1 and starts the real game."
metadata:
  type: project
---

**Status: finished 2026-09-23; the dev confirmed it works.** The dev said yes to both open questions (P does nothing before beats One to Eight; the first Start spends a coin) and to build. They confirmed the beat Nine recording says that tapping with three fingers ends the tutorial, so the hint is "Press P to end the tutorial." Built: `Stage_Tutorial.tutorial_skip`, `tutorialEnd_`, `ending`, `first_run`; `MainController.StartGameAction_` sends `('tutorial', True)`; `SixthSense._new_tutorial(first_run)`. Tests: `test_tutorial` 18/18, `test_menu` 26/26, `test_window`, `test_pause`, `test_input` pass. One deliberate difference: a second P during the 3.05 s wait is ignored, where the original would pause.

**What the dev reported (tunmi13productions, 2026-09-23):** "'p' actually closes the tutorial and plays tutorial end. but what's funny is you actually get stuck in that area, unable to do anything." It should go to the main menu. From memory: the first time, the tutorial says "3, 2, 1, the zombies are coming" and starts the real game; other times, "tutorial end" and back to the main menu. They asked whether a coin was spent, and to check the original.

**What the binary does (checked in the raw instructions):**
- `-[MainController StartGameAction:]` (0xb2ed) never reads `TUTORIAL`. It spends a coin whenever `Coin >= 1` (0xb324) and pushes `Stage_1_E` (0xb3f8). So the first run does spend a coin, and the tutorial runs inline inside `Stage_1_E`.
- The Tutorial row pushes `Stage_Tutorial`, a separate class.
- In both classes the stop button, while `isTutorial == 0`, first ANDs `tutorialOne` to `tutorialEight` (Stage_1_E 0x33f1a..0x33f30, Stage_Tutorial 0x83926..0x8393c). If any is still clear it returns and does nothing. FiveHalf and Nine are not in the test.
- If they are all set, both: stop the prompt (`tutorialSoundStop`), write `TUTORIAL = 1`, set `isTutorial = 1` (Stage_1_E 0x33fec), invalidate `tutorialTimer` and `checkTutorialTimer`, play 327 "tutorial success", and after 3.05 s (0x40086666_60000000) call `tutorialEnd:`.
- `-[Stage_Tutorial tutorialEnd:]` (0x83738) is just `GameEndAction:`, back to the main menu.
- `-[Stage_1_E tutorialEnd:]` (0x33bec) calls `TTSNumber:321 type:1`, which reads the digits 3, 2, 1 a second apart, then after 6.0 s (0x4018...) `tutorialEndGameStart:` plays 328 "zombies are coming" and starts the walk.
- `-[Stage_Tutorial tutorialEndGameStart:]` exists but nothing in `Stage_Tutorial` calls it: the Tutorial row never leads into the game.
- The stop button is the three-finger double tap (the gesture set up at 0x7edfe), so beat Nine, "if you tab the screen using three finger twice", is taught by doing the stop itself. The port's P is that stop button. The port finished beat Nine on Shift+Tab (previous weapon), which the evaluation already flagged as a misreading.

**What the port does now:** P calls `tutorial_skip` at any time, plays 327, and does nothing more, so you are stuck. Start with `TUTORIAL = 0` sends you to the tutorial without a coin. Finishing all ten beats always starts the real game, even from the Tutorial row.

**The plan (Claude's proposal):**
1. P ends the tutorial only once beats One to Eight are done, as in the original. Before that, P does nothing in the tutorial. Escape still leaves at any time.
2. Ending it plays "tutorial success" and writes `TUTORIAL = 1`. 3.05 s later:
   - from the Tutorial row, back to the main menu.
   - from a first Start, the digits 3, 2, 1 a second apart, then "zombies are coming" 6 s after the countdown began, and the real game.
3. Start always spends a coin, as in the original, including the first run. A new save has 10.
4. Beat Nine is finished by P, not Shift+Tab. Shift+Tab stays previous weapon. Its key hint becomes "Press P to end the tutorial."
5. Finishing the beats no longer starts the game by itself; the P press is the last step.
6. Tests in `test_tutorial.py` and `test_menu.py`, a `DIVERGENCES.md` update, and a changelog line.

**Open questions for the dev:**
- Keep the original's rule that P does nothing until beats One to Eight are done? Claude recommends yes.
- Spend the coin on the first Start, as the original does? Claude recommends yes.
- What does the beat Nine recording (284) actually say, so the hint matches it?
