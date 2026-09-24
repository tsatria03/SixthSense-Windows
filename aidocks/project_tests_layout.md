---
name: project_tests_layout
description: "The tests folder since the dev's reorganization on 2026-09-23: tests/case/ for the automated tests (no test_ prefix), tests/interact/ for the two tools played by ear (level_chooser, tutorial_chooser). The old name of each, and what had to change for them to run."
metadata:
  type: project
---

**The dev reorganized `tests/` on 2026-09-23**, moving every file unchanged:

- **`tests/case/`**: the 17 automated test files, each a plain script with its own runner, without the old `test_` prefix. `test_test_range.py` became `weapon_range.py`; the rest keep their names: `data`, `digits`, `focus`, `gameplay`, `input`, `intro`, `menu`, `monster_sound`, `paths`, `pause`, `release`, `speech`, `store`, `tutorial`, `volume`, `window`. The test functions inside still start with `test_`. `save.py` was added on 2026-09-23, making 18; it works only in temporary folders, so it never touches the real save.
- **`tests/interact/`**: the two tools you play by ear, `level_chooser.py` (was `level_tester.py`) and `tutorial_chooser.py` (was `tutorial_tester.py`).

**What Claude changed to make it work, the same day:**
- Every file found the repository by going one folder up from itself, which was now `tests/`, so none could import `sixthsense` (`ModuleNotFoundError`). Each now goes two folders up. `case/release.py` also uses that root to check where the zip goes.
- The choosers' own saves moved with their names, at the dev's choice: `%APPDATA%\SixthSense\level_chooser` and `...\tutorial_chooser`. Their old `level_tester` and `tutorial_tester` folders are left behind unused, and can be deleted.
- Their headers give the new commands and say they are tools, not tests, by their folder, rather than "the name does not start with test_".
- README.md, CLAUDE.md, PORTING_STATUS.md and the notes that give instructions use the new paths. History entries in [[project_evaluation_2026_09]] and [[project_safe_test_run]] keep the old names, as records of their time.
- The full suite passes from the new place: 270 of 270 across the 17 files.

**How to apply:** run a test as `python tests\case\<name>.py`, the safe way ([[project_safe_test_run]]); the full suite is every `tests\case\*.py`. Only the matching files run after a change ([[feedback_dont_run_or_build]]); for example a change to `game/store.py` runs `tests\case\store.py`. The choosers are never run by Claude, since they open the real game with sound.
