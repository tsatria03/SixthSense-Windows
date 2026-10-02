---
name: project_macos_build_plan
description: "Native macOS app packaging and distribution targets."
metadata:
  node_type: memory
  type: project
---

# macOS builds

Default output: `dist/SixthSense-macOS/SixthSense.app`, native architecture.
For a distributable build targeting macOS 11:

```sh
uv run --managed-python --python 3.13 --with-requirements requirements.txt --with pyinstaller python compiler.py --clean
```

- Requires 64-bit Python. ARM64 and Intel builds use the architecture of that
  Python, including x86_64 under Rosetta.
  Archive names distinguish macOS-arm64 and macOS-x86_64.
- Running from source can use uv's selected Python; managed Python is only
  needed here to preserve the distribution's older macOS minimum.
- PyInstaller onedir/windowed bundles all data, dependencies, documents and
  licenses. Its native target extracts the matching slice from universal OpenAL.
- `--console` produces a console-folder debugging build. Otherwise `--embed`
  and `--onefile` still produce an onedir app.
- The finished app is moved without rewriting its Info.plist or re-signing.
  Native binaries retain their own deployment requirements.
- Resources/Frameworks links preserve frozen lookup. Saves stay outside the app.

macOS release automation is outside this change; releaser.py is unchanged.

ARM64 and Intel/Rosetta app builds were checked after relocation.
