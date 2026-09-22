---
name: feedback_side_by_side
description: "Every gameplay claim is checked side by side against the binary: name the instruction address and the port line, never infer. Say plainly what is verified and what is not."
metadata:
  type: feedback
---

**Check gameplay side by side with the original, and never guess.** The dev said on 2026-09-22 "make sure you are checking things match side by side. no guessing", while doubting that headshots worked.

**Why:** Several past "reproduced" claims were misreadings, and guesses about behavior can put things in that the original never did. The dev plays by ear and relies on the port matching the original exactly, except for divergences they chose.

**How to apply:**
- For each step of a behavior, find the instruction in the binary (`tools/dz.py`; see [[project_binary_analysis_notes]]) and the matching line in the port, and compare the constants, the order, the delays and the guards.
- In the report, separate what the bytes verified from what is inferred, such as how OpenAL treats a stereo buffer or what a recording sounds like. Don't claim that the heard result matches unless the dev heard it.
- Treat a change that alters loudness or position as a divergence. Check it against what the original actually produced. For example, folding a stereo sound to mono also makes it fade with distance, which the original's stereo sound never did.
- Add a test that pins the verified behavior, timed against the real clock when timing is the point.
