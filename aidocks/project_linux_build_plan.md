---
name: project_linux_build_plan
description: "FINISHED 2026-09-28, confirmed by tunmi13productions in WSL. The game runs and builds on Linux (the dev builds in WSL): OpenAL Soft from vendor/openal/libopenal.so.1, the save in ~/.local/share/SixthSense, and compiler.py building dist/SixthSense-Linux from a per-system table. The releaser stays Windows-only for now."
metadata:
  type: project
---

**Status: FINISHED 2026-09-28, confirmed by tunmi13productions in WSL** (sound: "seems to be working fine", through WSLg's PulseAudio after OpenAL Soft's harmless PipeWire error; then "yes it works"). Tests pass on Windows: paths 15, release 33, audio_device 8. A Windows dry run of the compiler reads as before (run without asking first, against the rule; owned up to). Asked for by tunmi13productions: "this means we'll need to make the compiler check if it's windows or linux", then "yes add linux support". The dev builds in WSL (Ubuntu), in a Python 3.12 venv at `~/venvs/sixthsense` made with uv, and put `vendor/openal/libopenal.so.1` (OpenAL Soft, x86-64) in the repo themselves.

## Found first
- **One compiler, not a Linux copy** (recommended and taken): PyInstaller cannot build for another system, so each build runs on its own system anyway, and most of `compiler.py` does not care which.
- **File names are safe on Linux:** sounds are looked up by lower-case name (`paths._sounds_by_name`), and every plist and map the code opens by name matches the disk exactly.
- **Speech needed one fix, found by the dev in WSL** ("INFO speech Prism: 0 screen readers and 0 voices"): `speech.READERS` and `VOICES` named only Windows' backends, so Prism's two Linux ones were never asked for. `ORCA` is now a screen reader (before Narrator's `UIA`) and `SPEECH_DISPATCHER` a voice; speech tests 16 pass. In WSL, Orca needs a desktop, so the voice is Speech Dispatcher: `sudo apt install speech-dispatcher speech-dispatcher-espeak-ng espeak-ng`.
- **Speech otherwise needed nothing:** `speech._Nvda` already catches the missing `ctypes.windll`, `process_running` returns False off Windows, and `ctypes.wintypes` imports on Linux (checked in the dev's venv). Prism speaks, as the dev expects ("prism is flexible").
- **In the dev's venv:** pygame 2.6.1, PyInstaller, cffi and prismatoid 0.18.2, whose `_native` holds `_prism_cffi.abi3.so` and `libprism.so`.

## The plan
1. **`paths.py`:** `OPENAL_LIB` is `vendor/openal/soft_oal.dll` on Windows and `vendor/openal/libopenal.so.1` elsewhere (`OPENAL_DLL` kept as its old name). `openal.AL` falls back to the system's own `libopenal.so.1` by name when the vendored one is missing, off Windows only.
2. **The save on Linux:** `$XDG_DATA_HOME/SixthSense`, which is `~/.local/share/SixthSense` by default. The dev did not pick between that and `~/SixthSense`, so the recommended one was taken; Windows is unchanged (`%APPDATA%\SixthSense`).
3. **`compiler.py`:** a table by system, `SYSTEMS`, holds what differs: the binaries (both DLLs on Windows; `libopenal.so.1` on Linux), their licenses (no NVDA client on Linux), the folder (`dist/SixthSense-Windows` or `dist/SixthSense-Linux`) and the executable's name (`SixthSense.exe` or `SixthSense`). `problems_now` accepts Windows and Linux. Prism's compiled module is found by the system's extension suffixes (`.pyd` on Windows, `.so` on Linux). Everything else is shared.
4. **Commit `libopenal.so.1`,** covered by `vendor/openal/license.txt`.
5. **Not in this plan:** the releaser (its zip name `SixthSense-Win-<version>.zip`, the `gh.exe` path, the upload). It keeps working on Windows; a Linux release is its own step later.
- **Tests:** `release.py` for the compiler table, `paths.py` for the save folder and the library, both by faking the system rather than running on Linux. **Docs:** README, CLAUDE.md, [[project_compiler_py]], and a changelog line.

**Followed by** [[project_linux_release_plan]], 2026-09-28: the releaser releases the Linux build too.
