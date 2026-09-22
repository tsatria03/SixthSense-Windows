---
name: project_safe_test_run
description: "The tests write the dev's real save and play audio; run them with APPDATA redirected and OpenAL's null driver. Plain scripts, not pytest. Baseline 96/96."
metadata:
  node_type: memory
  type: project
  originSessionId: 8a78e7c9-236d-421e-8e76-c11a2895c278
---

The tests in `tests/` write keys such as `TUTORIAL`, `COIN`, `GOLD` and the weapon keys through `UserDefaults`. That class saves to `%APPDATA%\SixthSense\defaults.json` (`paths.user_dir()` reads the `APPDATA` environment variable), which is the dev's real save. `test_gameplay.py` also opens a real OpenAL device and plays about 35 seconds of game audio, and the dev keeps NVDA running while working.

**Why:** Found during the 2026-09-21 evaluation. A plain run would have overwritten the dev's save and played audio over their screen reader.

**How to apply:** Since 2026-09-22 the dev lets Claude run the tests without asking ([[feedback_dont_run_or_build]]), but always like this. Until the repo has its own override (a `SIXTHSENSE_USER_DIR` variable read by `paths.user_dir()` and set by each test), run the tests like this, in PowerShell:
- set `$env:APPDATA` to a folder in the session scratchpad
- set `$env:ALSOFT_DRIVERS = 'null'` so OpenAL Soft renders silently
- set `$env:SDL_AUDIODRIVER = 'dummy'`
- run each file as `python tests\<name>.py`; each is a plain script with its own `__main__` runner

The first baseline on 2026-09-21 was 96 of 96 passing across 7 files, in about 90 seconds (`test_gameplay` takes about 35 s because it runs on wall-clock time). Later that day the suite grew to 106 tests across 8 files (`test_digits.py`, and new menu and gameplay checks). With the sound-lookup change it has 117 across 9 files, adding `test_paths.py` and one more check in `test_data.py`. `test_paths.py` builds its own temporary bundles and never touches the save, the audio or `APPDATA`.

Latest run, 2026-09-22, after the zombie batch: **178 of 178 pass across 13 files**, including the new `test_monster_sound.py`, which opens OpenAL on the null driver and reads each zombie's source back. The run before that, after the Prism speech layer: **130 of 130 pass across 10 files** in about 87 seconds; `tests/test_speech.py` adds 13, all with fakes. The run before that, 2026-09-21: 117 of 117 in about 84 seconds. `test_gameplay` took 33 s, `test_input` 17 s and `test_tutorial` 11 s. No "sound file missing" warning was printed, and only the scratch `APPDATA` folder was written. Running the files one at a time in a PowerShell `foreach`, and printing only the lines that are not `ok`, keeps the output short. Several tests assert behavior the evaluation found to be a misreading, for example `test_check_boos_die_compares_against_gamemode_minus_two`. Fixing that behavior means updating its test in the same change. See [[project_evaluation_2026_09]].
