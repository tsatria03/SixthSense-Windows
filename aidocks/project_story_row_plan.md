---
name: project_story_row_plan
description: "FINISHED 2026-09-23, confirmed by the dev: a third row on the opening screen that tells the game's story, \"As the ozone\" (15), which the original recorded but never plays, with the intro music (bgm_start_end at 0.05) under it in both speech modes. tunmi13productions' idea; the dev's answers to the three questions."
metadata:
  type: project
---

**Status: FINISHED, 2026-09-23.** The dev tested it and said to mark it finished. The plan was committed on its own as `204ab96`, the code followed as its own commit with this status, and both were pushed together ([[feedback_record_plans_first]]).

**Tried and put back:** after the first build the dev asked for the story's music at 0.2, as loud as the menu music, then asked for it back ("revert that change. I realized it was better at 0.5", taken as the original's 0.05, the value before). `STORY_MUSIC_GAIN` is the original's 0.05.

**Built as planned:** `StartIntroPage.ROWS` is (1, 2, 3) with `ROW_SOUND[3]` = 15, `row_text(3)` = `STORY_TEXT`, and `select` starting `STORY_MUSIC` (`bgm_start_end`) at `volume.music(STORY_MUSIC_GAIN)` (0.05) on row 3, flagged by `story_music`. `StopElseSpeak` and `skipAction` stop it with `backgroundSoundStop` through `_stop_story_music`. The window text lists the three rows. Four tests in `tests/case/intro.py` (14 of 14); window 9/9, menu 32/32. One test first failed on its own check: once the story stops, row 2's recording can take its freed slot, so the test looks the story up again.

## Why
The dev found that `speech/game/As the ozone.wav` never plays. Checked in the binary the same day: it is sound 15, the story, and only `intro2storyPage` plays it, from `viewDidLoad` and its row selection through `shakeDevice` (0x2b714, gain 0.2), with `bgm_start_end` looping under it at 0.05 (0x17224). Nothing ever creates `intro2storyPage`: its name appears once in the binary, at 0xc0612 in the class name list, with no classref, no string naming its nib, and no other nib naming it. `startIntroPage` has its own `shakeDevice` but only cancels it (0x1892e) and has no shake handler. So the original never plays the story; the port reproduced that. The todo list has "Decide whether and where to play the game's story" in `##Unfinished.` since the finding was reported.

**tunmi13productions' suggestion**, passed on by the dev: "I'd put it below the you can skip thing if we want to include it. and we can transcribe what it says if you have the screen reader off."

## The dev's answers
1. **The intro music plays under the story in both speech modes** ("play it on both speech modes"): `bgm_start_end` at `volume.music(0.05)`, the original's gain, 12 dB under the menu music's -14 dB. The opening screen has no other music.
2. **Enter on the story row skips to the main menu**, as on the other two rows and as the original's double tap did anywhere on the story screen.
3. **The text is the binary's** (`intro.STORY_TEXT`, 0x171e4): the dev listened and said the recording says it "exactly word for word".

## The design
- `StartIntroPage.ROWS` becomes (1, 2, 3): the welcome, "you can skip", and the story. `ROW_SOUND[3]` is 15, so with voice over on, landing on row 3 plays the story recording, as the original story screen's first row did; there is no recording naming the row.
- **Landing on row 3** also starts `bgm_start_end` on the background player at `volume.music(0.05)`, looping, in both modes. With voice over off the screen reader reads `STORY_TEXT` in place of the recording, the way row 1 reads `WELCOME_TEXT`.
- **Leaving row 3**, by Up, Down, Home, End, Left or Right, stops the story (StopElseSpeak already stops every row's sound) and stops the music. Skipping with Enter or Escape stops both too.
- The earphone reminder is unchanged: moving to any other row already cancels it.
- The window text names row 3 "the story".
- `shakeDevice` stays the original's, uncalled, as a record; the row uses the same sound and music directly.
- Tests in `tests/case/intro.py`: row 3 plays 15 and starts the music; with voice over off it reads `STORY_TEXT` and starts the music; leaving the row stops both; Enter on it skips to the menu; Home and End reach it in the screen reader mode.
- Docs: DIVERGENCES.md (a port addition: the story the original never plays), PORTING_STATUS.md's `startIntroPage` and `intro2storyPage` lines, the README, the changelog, and the todo line moved to finished once the dev confirms it.
