---
name: project_prism_speech
description: "Built 2026-09-22; the tests pass and the dev confirmed it by ear: platform/speech.py speaks through NVDA's own DLL first, then Prism (prismatoid) for JAWS, Narrator and the rest, then SAPI or OneCore through Prism; comtypes is gone. compiler.py bundles Prism and ships a licenses folder (OpenAL Soft, NVDA client, Prism, pygame). How it works and how it is tested."
metadata:
  node_type: memory
  type: project
---

**Decided and built on 2026-09-22.** The dev asked for the speech layer to move to Prism, then said "Let's implement the new screenreader/sapi library".
- **Tested and heard:** all 130 tests pass, including the 13 new speech tests. The dev then listened and said "Everything past!" (2026-09-22).
- The todo item moved to finished as "The key bindings screen and the main menu's spoken messages speak through Prism...".
- `requirements.txt` lists pygame and prismatoid. Its todo item moved to finished on 2026-09-22, when the dev confirmed it.

**Before this change:** NVDA through `vendor/nvda/nvdaControllerClient64.dll`, else SAPI through comtypes. comtypes was never installed, so without NVDA the game was silent. accessible_output2 0.17 is installed in the dev's Python, but the game never used it.

**Prism, as installed** (`prismatoid` 0.18.2; its source was read, but it has never been run by Claude):
- `from prism import Context, BackendId`. `Context()` is the registry, with `backends_count`, `id_of(i)` and `create(id)`.
- A `Backend` has `name`, `speak`, `output` (speech plus braille), `stop`, and `features.is_supported_at_runtime` and `.supports_output`.
- It needs cffi (2.1.1 is installed) and Windows 10 or later.
- Its native half is `prism/_native/prism.dll` and `_prism_cffi.pyd`. It is licensed MPL-2.0.

**How `sixthsense/platform/speech.py` works now.** The pattern follows the dev's reference speech layer in `user/`. `Speech.speak(text, interrupt=True)` tries these in order:
1. **`_Nvda`**, the vendored controller DLL, asked before every line whether NVDA runs. `Speech.prism` is built lazily, so an NVDA player never loads Prism.
2. **`_Prism.speak_reader`**, through the screen readers in `READERS`, in order: NVDA, JAWS, ZDSR, ZoomText, System Access, PC-Talker, Boy PC Reader, Sense Reader, Window-Eyes, UIA.
   - NVDA is in the list only as a backstop, for when its own DLL can't load.
   - UIA (Narrator) is last, and is even created only while `narrator.exe` runs, per `process_running()`, a Toolhelp32 snapshot. Prism's UIA backend claims to be ready either way.
   - With no reader in use, it looks for one at most every `PROBE_EVERY` (5 s).
   - It asks the reader in use whether it still runs at most every `CHECK_EVERY` (1 s), and lets it go at once if it stops or raises.
3. **`_Prism.speak_voice`**, `VOICES`: SAPI, then ONE_CORE if SAPI won't be created. After a failure it retries at most every 5 s.
4. **Nothing.** `speak` returns False.
   - The log names the speaker only when it changes (`Speech._heard`).
   - Prism missing or broken makes `_Prism.ctx` None, so NVDA carries on alone.
- `output()` is used when a backend supports it, so a braille display gets the line too; otherwise `speak()`.
- **Kept for callers:** `Speech.shared()`, `speak()`, `stop()`, `which` and `available`. `KeyBindScreen` and `MainController._say` use `speak` only.
- **Testable without sound:** `Speech(nvda=..., prism=...)` and `_Prism(loader=..., narrator_running=..., clock=...)` take stand-ins.
- **`tests/test_speech.py`** has 13 tests with a fake NVDA, a fake registry and a fake clock. It never loads the DLL or Prism, and is safe to run.

**`compiler.py` (done the same day, checked only by parsing):**
- `PLAY_PACKAGES` now includes `('prism', 'prismatoid')`, so a build stops without Prism. `OPTIONAL_PACKAGES`, `optional_missing()` and comtypes are gone.
- `command()` adds `--collect-all prism --hidden-import _cffi_backend`, plus `--add-binary` for each `.pyd` in `prism/_native` (`prism_native_modules()`). `--collect-all` misses the `.pyd`, because `_native` is not a package.
- **Licenses:** `license_files()` and `copy_licenses()` fill `licenses/` beside the executable, after `copy_side_files()`. `--dry-run` reports the count and anything missing.
  - `licenses/openal-soft/`: `license.txt` and `license-pffft.txt`, from `vendor/openal/` (`VENDOR_LICENSES`)
  - `licenses/nvda-controller-client/`: `license.txt`, from `vendor/nvda/`
  - `licenses/prism/`: every file under the installed `prismatoid-*.dist-info/licenses`, found through `importlib.metadata`. That is `LICENSE`, `NOTICE` and the whole `LICENSES/` folder the NOTICE points to. Files with no extension get `.txt`, so Windows opens them.
  - `licenses/pygame/LGPL.txt`, from the installed pygame's `docs/generated/LGPL.txt`
  - On 2026-09-22 all 17 files were found by a read-only check of the metadata.

**The vendored license files** were added on 2026-09-22:
- `vendor/openal/license.txt` is OpenAL Soft's `COPYING`: the GNU Library GPL v2, June 1991, which the DLL's own copyright field names.
- `vendor/openal/license-pffft.txt` is its `LICENSE-pffft`. It is BSD-style, and its terms say it must ship with the binary.
- Both are byte-identical copies from the dev's `openal-soft-1.25.2-bin` download. That download's Win64 `soft_oal.dll` is byte-identical to the repo's: both say 1.25.1, with SHA-256 `3963B06E...FAB5B4`.
- `vendor/nvda/license.txt` is the LGPL-2.1 text from Prism's own `LICENSES/nvdaController`, which its NOTICE says covers the controller client.
- **Prism does not go in `vendor/`.** It is a pip package, and its loader expects its DLL inside the package.

**How to apply:**
- Run `tests/test_speech.py` with the rest, the safe way ([[project_safe_test_run]]).
- Never run anything that speaks through NVDA or Prism for real without the dev's say-so, since they work with NVDA running ([[feedback_dont_run_or_build]]).
- Checking it by ear, especially without NVDA and with Narrator, is the dev's job.
- The screen reader mode ([[project_screen_reader_mode]]) builds on this.
- Don't name the reference project in code, comments or notes ([[feedback_no_other_games]]).
