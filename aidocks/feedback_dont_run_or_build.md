---
name: feedback_dont_run_or_build
description: "Never build unless the dev says so. Ask before running anything for smoke-test purposes: the game, the tests, compiler.py, or scripts that execute game code. Read-only inspection is fine."
metadata:
  node_type: memory
  type: feedback
  originSessionId: 8a78e7c9-236d-421e-8e76-c11a2895c278
---

**Never build anything unless the dev says to.** That covers `compiler.py`, PyInstaller, and any packaging or zip step.

**Ask before running anything for smoke-test purposes.** That covers:
- the game (`python SixthSense.py`, including `--no-window` runs)
- the test suite in `tests/`
- `compiler.py` in any mode, including `--dry-run` and `--test`
- scratch scripts that import and execute game code to check behavior

Make the edits, report them, and hand verification back to the dev, or ask first and wait for a yes.

Read-only inspection is always fine: reading and grepping files, `git status`, `git diff` and `git log`, listing installed packages, and parsing the binary's bytes for analysis. When unsure which side of the line something falls on, ask.

**Why:** The dev set this rule on 2026-09-21. They run and verify builds themselves, and they work with NVDA running, so an unexpected run can make noise, touch their save, or leave stray processes and artifacts.

**How to apply:** When a change needs verifying, end with a clear "relaunch to test" or "run X to check" note instead of running it. If a smoke test would help, ask one short question saying exactly what you'd run and why. If the dev agrees to running the tests, follow [[project_safe_test_run]] so their save and ears are protected.
