---
name: project_tutorial_tester_plan
description: "PLANNED 2026-09-23, not built: tests/tutorial_tester.py, a by-ear tester like level_tester.py that opens the real tutorial on its own save, asking which ending (Start's countdown into the game, or the Tutorial button's return to the menu), which lesson to start at, and voice over on or off."
metadata:
  type: project
---

**Status: planned on 2026-09-23, every question answered, waiting for the dev's go-ahead to build.** Mark it "built, not yet confirmed" when the code lands, and "finished" only once the dev says it works ([[feedback_record_plans_first]]).

**What the dev asked for:** a tutorial tester to play by ear, not an automated test ("I meant the one I play by ear, not the other case test"). `tests/test_tutorial.py` already has the automated checks. Asked after tunmi13productions' tutorial ending work ([[project_tutorial_ending_plan]]), when the dev found the Start ending hard to reach without deleting their save.

## The dev's answers
1. **It asks which ending, like the level tester asks for a level**: the Start ending (a first run: P counts 3, 2, 1 into the real game) or the Tutorial button ending (P goes back to the main menu).
2. **It asks which lesson to start at; Enter alone means lesson One.** "You should be able to test each lesson."
3. **It asks voice over on or off.** The dev: the recorded instructions play either way; off means the screen reader also says the keyboard keys for each action (the key hints, `Stage_Tutorial.key_hint`).

## The design
- **`tests/tutorial_tester.py`**, beside `level_tester.py` and shaped like it. Not a test: its name does not start with `test_`, so the runs skip it.
- **Its own save**, `%APPDATA%\SixthSense\tutorial_tester`, taking a fresh copy of the player's `keys.json` each start, the same `_own_save()` as the level tester. The player's save is never touched.
- **Asked when opened with nothing after its name**, in this order, Enter giving the default each time:
  1. The ending: `start` or `menu` (Enter for `menu`).
  2. The lesson, 1 to 10 (Enter for 1), read out as a numbered list:
     1 shooting at 9 o'clock, 2 at 10:30, 3 at 12, 4 at 1:30, 5 at 3 o'clock, 6 the stronger zombie (FiveHalf), 7 reloading (Six), 8 changing weapon (Seven), 9 shaking off the animal zombie (Eight), 10 ending the tutorial with P (Nine).
  3. Voice over: `on` or `off` (Enter for `on`). Written to the tester's save as `EYEMODE`, "1" or "0".
- **The same on the command line:** `--ending start|menu`, `--lesson N`, `--voice on|off`, and `-v`.
- **How a lesson is started:** a `Stage_Tutorial` subclass marks every lesson before the chosen one done (`beat_done`), and swaps the chosen lesson in for the first `tutorial_beat('One')` that `MapInitInBundle` plays, so nothing of lesson One is heard. From there the tutorial runs as it does in the game: `REQUIRES` is already met, `NextTutorial` goes on in order, and P works from lesson 10 on, or once lessons One to Eight are done.
- **The ending:** the first tutorial gets `first_run` from the answer. `SixthSense._new_tutorial` is replaced, as the level tester replaces `_new_stage`, so a tutorial started later from the tester's menu also starts at the chosen lesson, with the ending the menu's own route gives it (Tutorial row: menu; a first Start: the countdown).
- It starts the game with `SixthSense.main(['--tutorial'])`.
- README's "Starting at any level" section gains a short "Starting the tutorial at any lesson" part, and CLAUDE.md's `tests/` line names the new tester.
- No automated test is added, since it is a tool, like the level tester. Checked by importing it and by `--help`, which runs nothing of the game.

## Not in it
- No choice of area: the tutorial's own stage picks it, as in the game.
- It never builds or touches the player's save or GitHub.
