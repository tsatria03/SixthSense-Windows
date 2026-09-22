---
name: project_python_only
description: "The Windows port of Sixth Sense is written entirely in Python; compiler.py was adapted to build it but has not been test-built yet."
metadata:
  node_type: memory
  type: project
  originSessionId: 8a78e7c9-236d-421e-8e76-c11a2895c278
---

The Windows port of Sixth Sense is written entirely in Python: pygame for the window and keyboard, OpenAL Soft through ctypes for audio, and the NVDA controller client, or Prism for other screen readers and a Windows voice, for the few synthesised lines. Don't propose moving parts to another language or engine.

`compiler.py` at the repo root is the PyInstaller build script. It was adapted to build Sixth Sense on 2026-09-21. The todo list's "Test the compiler with a first build" line stays until the dev's first build works. Everything known about it is in [[project_compiler_py]].

**Why:** Both are the dev's stated decisions from 2026-09-21.

**How to apply:** Write any new code in Python and follow the existing package layout (`sixthsense/game`, `platform`, `ui`). Never run `compiler.py` or build without the dev's say-so; see [[feedback_dont_run_or_build]].
