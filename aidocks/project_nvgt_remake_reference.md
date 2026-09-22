---
name: project_nvgt_remake_reference
description: "The dev's old NVGT remake of Sixth Sense (formerly user/SixthSenceRemake-main) was deleted on 2026-09-21. Its only legacy is the folder layout of game/sounds; its code and rules were never used."
metadata:
  node_type: memory
  type: project
  originSessionId: 8a78e7c9-236d-421e-8e76-c11a2895c278
---

The dev's own NVGT prototype of Sixth Sense used to sit in `user/SixthSenceRemake-main`. NVGT is the Non-Visual Game Toolkit, an AngelScript engine, and the engine itself is at `C:\Users\tonys\OneDrive\Desktop\nvgt-main\nvgt_0.90.0_dev`. **The dev deleted the prototype on 2026-09-21**, as it is no longer needed.

It was a loose reimagining, not a port:
- a 2D grid with HRTF sound
- three attack directions, and weapons on keys 1 to 9
- XP and levels, and 6 health

It never had the corridor, the lanes, headshots by breathing, grabs, bosses, coins or the store.

**None of its code or gameplay rules went into the Python port**; the binary stays the authority on behavior. Its one legacy is the **folder layout of `game/sounds/`**. The dev converted its organized sounds to WAV and imported them, and Claude then renamed each file to its original name by comparing the audio ([[project_sound_organization]]).

**How to apply:** Don't look for the remake in `user/`; it's gone. If a question comes up about why `game/sounds` is laid out as it is, this is the answer.
