---
name: project_binary_analysis_notes
description: "How to read the ARMv7 binary correctly: addresses are VM addresses (file offset = addr - 0x1000), the dc_ listings drop register saves, and key branches must be hand-checked from raw bytes."
metadata:
  node_type: memory
  type: project
  originSessionId: 8a78e7c9-236d-421e-8e76-c11a2895c278
---

The port is recovered from `analysis/bin/sixsense_armv7` (Thumb-2, 32-bit Mach-O). Every address in the code comments and in `docs/` is a **VM address**. `__TEXT` is mapped at vmaddr `0x1000` from file offset 0, so **file offset = address - 0x1000**. `tools/README.md` calls them file offsets, which is wrong. Reading the bytes at the raw address lands in unrelated code.

The `analysis/disasm/dc_*.txt` listings are a simplification and can mislead:
- They drop register saves and restores. For example, `-[AppDelegate didFinishLaunching]` at 0x4268-0x429e saves the FIREST object in r6 and later calls `intValue` on it. The listing makes it look as if `intValue` runs on COIN.
- They render some conditional branches as `cbnz r0` without saying what r0 holds. At 0xe562 in `startSound:Postion:soundGain:`, the "null check" is really the `isPlaying` test that decides between moving a playing sound and restarting it.
- Placeholder label text is not data: `"10:00"` at 0xbede is not the coin interval. The real interval is `rsb.w r2, r0, #0x708` (1800 s) at 0xc1ee.
- Thumb-2 immediates are stored rotated (1800 is `0xE1` rotated right by 29), so grepping for `#1800` or `#0x708` can miss them.

To prove whether something in the original is ever called, check the selector references: a message can only be sent if its selector is in `__objc_selrefs` (VM 0xd9548, size 0x1984). For example, `setListenerRotation:`, `setListenerPos:` and `MonsterQueueNote:...` are implemented but unreferenced, so nothing calls them. `__objc_classrefs` (VM 0xdaed8) is weaker evidence, because classes built from a nib (like `Stage_1_E`) don't appear there either.

**Why:** The 2026-09-21 evaluation found several docs entries marked "reproduced" that trace back to exactly these misreadings.

**How to apply:** Before porting or "reproducing" any behavior that hinges on a single branch or constant, decode the raw halfwords at file offset `addr - 0x1000`. A short Python byte dump is enough; see the MOVW and BL decoding used in the evaluation session. `tools/dz.py` and `tools/dc.py` need `capstone`, which is not installed in the dev's Python. Install it into a venv or the scratchpad, not globally, unless the dev agrees.
