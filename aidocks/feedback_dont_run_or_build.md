---
name: feedback_dont_run_or_build
description: "Never build unless the dev says so. Tests may be run without asking, always the safe way, but only the scripts covering the Python files changed; the full suite only when the dev asks. Ask before running the game, compiler.py, or scripts that execute game code or speak. Read-only inspection is fine."
metadata:
  node_type: memory
  type: feedback
---

**Never build anything unless the dev says to.** That covers `compiler.py`, PyInstaller, and any packaging or zip step.

**Only the tests that match what changed (2026-09-23).** When one or more Python files change and a test script covers them, run only that script or those scripts, not the whole suite. For example, a change to `game/store.py` runs `tests/test_store.py`. Run the full suite only when the dev asks, for example once they have more than five commits that are not pushed, or after the conversation has been compacted. The dev said: "Do not keep running the full test suite over and over again." This replaces the earlier pause of 2026-09-22 ("for the next few commits, do not run tests unless I say so").

**The test suite may be run without asking.** The dev gave this standing permission on 2026-09-22 ("From now on, you are allowed to run test suites"). It covers the files in `tests/`, run one by one as plain scripts. Always run them the safe way ([[project_safe_test_run]]): `APPDATA` pointed at a scratch folder, `ALSOFT_DRIVERS=null` and `SDL_AUDIODRIVER=dummy`, so the dev's save is untouched and nothing is heard over NVDA.

**Still ask first before running:**
- the game (`python SixthSense.py`, including `--no-window` runs)
- `compiler.py` in any mode, including `--dry-run`
- scratch scripts that import and execute game code to check behaviour
- anything that could speak through NVDA or Prism for real, or play sound

Make the edits, report them, and hand verification by ear back to the dev.

**Read-only inspection is always fine:** reading and grepping files; `git status`, `git diff` and `git log`; listing installed packages; reading package metadata; and parsing the binary's bytes for analysis. When unsure which side of the line something falls on, ask.

**Why:** The dev set the original rule on 2026-09-21. They run and verify builds themselves, and they work with NVDA running, so an unexpected run can make noise, touch their save, or leave stray processes and artifacts. Tests run the safe way do none of that, which is why they were freed up on 2026-09-22.

**How to apply:** After a code change, run only the test scripts that cover the changed files, the safe way, and report the result. Leave the full suite for when the dev asks. When a change needs checking by ear, end with a clear "relaunch to test" note instead of running the game.
