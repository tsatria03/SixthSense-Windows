---
name: project_macos_runtime_plan
description: "macOS universal OpenAL, Prism speech and save paths."
metadata:
  node_type: memory
  type: project
---

# macOS runtime

- Targets macOS 11 or newer. Source use supports arm64 and x86_64 with matching
  64-bit Python 3.12+ and dependencies; app builds match the build Python's architecture.
- `paths.py` selects bundled universal2 OpenAL Soft 1.25.2. A missing macOS
  library fails explicitly rather than loading Apple's OpenAL framework.
  Source, build commands, hashes and licenses: `vendor/openal/macos-source.md`.
- Prism tries `VOICE_OVER`, then `AV_SPEECH` without a reader. Recorded speech
  and gameplay are unchanged; HRTF remains off despite embedded library data.
- Saves use `~/Library/Application Support/SixthSense`; `SIXTHSENSE_USER_DIR`
  remains the isolation override.

Source and app builds were checked on ARM64 and Intel under Rosetta.

Packaging: [macOS builds](project_macos_build_plan.md).
