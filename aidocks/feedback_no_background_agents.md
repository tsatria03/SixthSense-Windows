---
name: feedback_no_background_agents
description: "Don't launch background subagents for reviews or scans; do the work in the foreground, because background agents make the terminal jump around under NVDA."
metadata:
  type: feedback
---

**Do reviews and scans in the foreground, not with background subagents.** On 2026-09-22 three parallel reviewer agents were launched for an evaluation. The dev stopped one and then asked for the rescan to be done again, saying "My commandline keeps jumping around doing things."

**Why:** The dev works with NVDA ([[user_screen_reader]]). Background agents keep updating the terminal, which moves the reading focus and makes the session hard to follow.

**How to apply:** Read the files directly, one step at a time, and report once at the end. Use a subagent only if the dev asks for one.
