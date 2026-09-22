---
name: project_prism_speech
description: "Decided 2026-09-22, not built yet: platform/speech.py moves to Prism (the prismatoid package) for JAWS, ZoomText, Narrator and the rest, with SAPI through Prism instead of comtypes; NVDA stays first through the vendored DLL; a licenses folder in the release carries Prism, pygame, OpenAL Soft and the NVDA client. The design and what compiler.py needs."
metadata:
  node_type: memory
  type: project
---

**The dev decided on 2026-09-22 to move the speech layer to Prism. It is not built yet**; the dev said "Do not build the library yet". The todo list has it as "Speak through Prism...", and `requirements.txt`, when it is added, lists pygame and prismatoid.

**What the game does today** (`sixthsense/platform/speech.py`):
- NVDA through `vendor/nvda/nvdaControllerClient64.dll`.
- Otherwise SAPI 5 through comtypes. comtypes is not installed, so without NVDA the game is silent.
- JAWS and the other screen readers get nothing.
- accessible_output2 0.17 is installed in the dev's Python, but the game never imported it. It was only ever a todo suggestion.

**Prism, as installed** (`prismatoid` 0.18.2, read but never run on 2026-09-22):
- `from prism import Context, BackendId`. `Context()` is a registry; `create(id)` returns a `Backend`.
- A `Backend` has `speak`, `output` (speech plus braille), `stop`, and `features.is_supported_at_runtime`.
- `BackendId` covers NVDA, JAWS, ZDSR, ZoomText, System Access, UIA (Narrator), PC-Talker, Window-Eyes, Boy PC Reader, Sense Reader, SAPI and OneCore.
- It needs cffi (2.1.1 is installed) and Windows 10 or later.
- Its native half is `prism/_native/prism.dll` and `_prism_cffi.pyd`.
- It is licensed MPL-2.0, and its NOTICE lists bundled third-party licenses.

**The agreed design** (the pattern of the dev's reference speech layer in `user/`):
1. **NVDA first**, through the vendored controller DLL. It is asked before every line whether NVDA is running, and Prism is never loaded for an NVDA player.
2. **Then Prism's screen readers**, tried in a fixed order.
   - Prism's UIA backend reports itself ready even with Narrator off. So check that `narrator.exe` is running (a Toolhelp32 process snapshot) before using it, or lines are lost.
   - Look for a newly started screen reader every few seconds, and let go of one that stops.
3. **Then SAPI 5 through Prism's own SAPI backend**, instead of comtypes, so comtypes can go entirely.
4. **Prism is optional at run time:** if it will not load, the game keeps NVDA and logs it, rather than crashing.

**compiler.py, when it is built** (copied from the reference build script in `user/`):
- Add `('prism', 'prismatoid')` to `PLAY_PACKAGES`, and drop comtypes from `OPTIONAL_PACKAGES` and its `--collect-submodules`.
- Pass `--collect-all prism --hidden-import _cffi_backend`.
- Add each `.pyd` in `prism/_native` with `--add-binary ...;prism/_native`. `--collect-all` misses it, because `_native` is not a package.
- **Ship the third-party licenses with the release**, for all three native pieces the game carries. The dev agreed for Prism, then asked on 2026-09-22 to cover all three. Put them beside the executable, for example in a `licenses` folder:
  - **Prism:** its MPL-2.0 `LICENSE` and `NOTICE`, found in `prismatoid-*.dist-info/licenses`.
  - **OpenAL Soft** (`vendor/openal/soft_oal.dll`, version 1.25.1): the GNU Library General Public License v2, June 1991, as the DLL's own copyright field says.
    - It is in `vendor/openal/license.txt`, copied byte for byte from the `COPYING` in the dev's `openal-soft-1.25.2-bin` download on 2026-09-22.
    - `vendor/openal/license-pffft.txt` is that download's `LICENSE-pffft`, a BSD-style license for the modified PFFFT that OpenAL Soft builds in. Its terms require the notice to ship with any binary.
  - **The NVDA controller client** (`vendor/nvda/nvdaControllerClient64.dll`): LGPL-2.1. It is in `vendor/nvda/license.txt`, copied byte for byte from `prismatoid-0.18.2.dist-info/licenses/LICENSES/nvdaController/lgpl-2.1.txt`, which Prism's NOTICE says is there for the controller client.

  - **pygame** is LGPL too, and PyInstaller bundles it along with its SDL libraries. On 2026-09-22 the dev agreed its license ships as well. It is installed as `site-packages/pygame/docs/generated/LGPL.txt`, and is collected at build time.

  **Prism does not go in `vendor/`.** It is a pip package, like pygame: its `prism.dll` and `_prism_cffi.pyd` live inside the installed package, whose loader expects them there. PyInstaller bundles them from there. `vendor/` is only for DLLs pip cannot install.

  **The agreed release layout** (the dev said yes on 2026-09-22) is a `licenses` folder beside the executable:
  - `licenses/openal-soft/`: `license.txt` and `license-pffft.txt`, from `vendor/openal`
  - `licenses/nvda-controller-client/`: `license.txt`, from `vendor/nvda`
  - `licenses/prism/`: `LICENSE`, `NOTICE` and the whole `LICENSES` folder, from the installed `prismatoid-*.dist-info/licenses` at build time. The NOTICE points readers at that folder, so it must go too.
  - `licenses/pygame/`: its `LGPL.txt`, from the installed package at build time

  The two vendored licenses live in the repo. Prism's and pygame's are collected from pip when `compiler.py` builds, so there is no second copy to keep in step.
  - The download's `bin/Win64/soft_oal.dll` is **byte-identical** to the repo's: same SHA-256 `3963B06E...FAB5B4`. Both call themselves 1.25.1, even though the zip is named 1.25.2. When the dev asked on 2026-09-22 to swap in "the newer one", there was nothing to change.

**How to apply:** Build this before the screen reader mode ([[project_screen_reader_mode]]), which depends on it. Never run anything that speaks without the dev's say-so, since they work with NVDA running ([[feedback_dont_run_or_build]]). Don't name the reference project in code, comments or notes ([[feedback_no_other_games]]).
