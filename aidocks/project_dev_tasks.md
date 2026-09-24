---
name: project_dev_tasks
description: "The developer-side task list: work on the repository, the tools, the tests, the build and the docs that a player never sees. Moved out of todo list.txt on 2026-09-23, when that file became players only. Open tasks first, then finished ones, newest first."
metadata:
  type: project
---

Since 2026-09-23, `todo list.txt` holds only what a player notices ([[feedback_todo_list_format]]). Everything else that needs doing, or has been done, lives here, in the same style: one plain sentence per line, newest first. The technical detail behind each line is in [[project_evaluation_2026_09]].

**How to apply:** a new developer task goes at the top of Open. When it lands and the dev confirms, it moves to the top of Finished. A task that changes what a player hears or sees belongs in `todo list.txt` instead, and in `changelog.txt` once it is done ([[feedback_changelog]]). **Debug mode is developer-facing** (the dev, 2026-09-23: players will not know it exists), so its lines live here and never go in `todo list.txt` or `changelog.txt`. The four oldest debug lines below came from the changelog, which had them in more detail than the todo list.

## Open

- Bring the docs and notes up to date with the code, from the 2026-09-23 rescan. game/sounds/unused holds 27 files (26 WAV and one bloopers OGG), not the 25 in CLAUDE.md and these notes or the 26 in the README. CLAUDE.md still says the game opens on the splash, where it now opens on the logo, and that only the key bindings screen is synthesised, leaving out the screen reader mode. The README layout leaves out debug.py, stage_1_test.py and ui/focus.py, and CLAUDE.md says Python 3.12 where the README says 3.12 or newer. tests/case/paths.py line 6 and a few notes still use old test_*.py names. project_tests_layout.md opens with 17 files and 270 tests, feedback_changelog.md says unrelease starts at 0, and a finished line below says findings are listed in the todo list's unfinished section.
- The run loop can run a timed event twice when it raises a TypeError inside, runs every due delayed call before every due timer within one frame, and reads a clock that only moves in 15.6 ms steps. All three were confirmed on 2026-09-23; the fix is one call per event, one queue in time order, and `time.perf_counter`, with the full suite run after. Moved from the todo list the same day, since a player is unlikely to notice.
- The debug keys shown in the game window leave out F7.
- Update two outdated code comments, about the zig-zag walks and the timers. (The README half was done on 2026-09-23.)
- Add a log file and a crash.txt beside the save, so a failed start can be diagnosed.
- Add an exit after option and a game data line to the log, so the compiler's test build can come back.
- A wrong game folder silently falls back to the default one, sounds past slot 122 are dropped without a log line, a few OpenAL calls have the wrong return type, and OpenAL is never closed on exit.
- The tests overwrite the real save file.
- Update DIVERGENCES.md, PORTING_STATUS.md, GAME_STRUCTURE.md and the tests where they describe misreadings of the original as reproduced, such as the boss check.

## Finished

- In debug mode, starting a game from the menu or restarting from the panel needs no coin and spends none.
- A tutorial tester in tests/interact/tutorial_chooser.py starts the tutorial at any lesson, with the Start ending or the Tutorial button's, and voice over on or off. It asks when opened on its own, and plays on its own save so yours is never touched.
- The tutorial can be finished in debug mode. Killing its zombies still counts for nothing, but each kill now finishes its lesson as it should.
- In debug mode F2 now goes to the next section of the corridor, and Shift+F2 to the next level, instead of the other way round.
- In debug mode Shift+F2 waits two seconds between sections, as F2 does between levels, and says "Not while the section is changing" until it is ready.
- In debug mode Tab goes through every weapon, bought or not, and no gun or grenade ever runs out.
- In debug mode F7 lets zombies that reach you hit you as in a normal game, still without taking a heart, and F7 again has them die on you.
- In debug mode F2 goes back to level 1 after level 8, and Shift+F2 says "Not while the section is changing" while a level is changing.
- Starting the game with --debug gives a debug mode, and each stage says "Debug mode" as it starts. A zombie that reaches you dies on the spot, heard only by its death, so you cannot die.
- In debug mode your kills and headshots do not count, so a run earns no score and no gold. The girl still thanks you when she reaches you, but gives you no heart.
- In debug mode F2 goes to the next section of the corridor, Shift+F2 goes to the next level, F5 spawns a zombie in the lane you last attacked, and Shift+F5 chooses what F5 spawns.
- In debug mode F6 holds the zombies in place, and F11 says where they are. The key bindings screen lists the debug keys and can rebind them, but only in debug mode.
- tools/README.md says the addresses are memory addresses, and how to find them in the file, instead of calling them file offsets.
- A level tester in tests/interact/level_chooser.py starts the game at any level, in the cave, the forest or the rain, and near the boss if you like. It asks when opened on its own, and plays on its own save so yours is never touched.
- A test checks that zombie sounds really move, by reading each zombie's sound back from OpenAL itself.
- The compiler builds a working game. A console build starts and plays, and its release zip opens and holds all 643 files: the game, its data, and the licenses beside it. While it packs the zip, the compiler says so and says how far it has got, so the window is not closed too early.
- A requirements.txt lists the two packages the game needs, pygame and prismatoid, so pip install -r requirements.txt installs both.
- Every sound the game uses sits together in game/sounds/used, 329 files covering all 269 of the original's sounds, apart from the 25 in game/sounds/unused.
- The 25 sounds that are not the original's own, 11 extra copies and 14 the original never had, are kept apart in game/sounds/unused, in the same folders they came from, so the rest of game/sounds holds only the original's sounds.
- Every one of the original game's 269 sounds now has a copy in game/sounds, including the six the organized folder was missing: Game Start Button, Welcome to, game center button10, restore button, weapon_m4_fire and weapon_saw_start.
- The organized sounds are 16-bit WAV again, the format the game's sound loaders read, instead of the 24-bit the OGG conversion had left them in.
- The sounds are organized into folders in game/sounds, and every one that came from the original carries its original file name again, 323 files in all, each checked by comparing its audio with the original's.
- The compiler has been changed to build Sixth Sense. It only needs pygame, copies just the files the game reads, and leaves the original iOS executable out of the release.
- The whole port has been evaluated, and every bug and missing feature that turned up is listed in the unfinished section, most important first.
- The initial commit is credited to lbk2907 on GitHub, and every commit uses GitHub usernames instead of real names.
- The license credits tsatria03 and lbk2907.
- The private user folder and the scratchpad are kept out of the repository by the git ignore file.
- Project notes for AI-assisted work are set up in CLAUDE.md and the aidocks folder.
