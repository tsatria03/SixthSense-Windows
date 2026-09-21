---
name: user_screen_reader
description: "The dev works with NVDA running and reviews output by screen reader; prefer lists and short lines over wide tables, and never make noise or speak through NVDA from tools or tests."
metadata:
  node_type: memory
  type: user
  originSessionId: 8a78e7c9-236d-421e-8e76-c11a2895c278
---

The dev builds audio-only games for blind players. They had NVDA running during the 2026-09-21 session. They review changes through a screen reader, and lines over 1024 characters get split mid-thought.

**How to apply:** In replies and docs, prefer headings and bulleted lists to wide tables, and keep lines reasonably short. Don't run anything that plays audio or speaks through NVDA without silencing it first; see [[project_safe_test_run]]. When recommending game changes, weigh how they sound to a player who can't see the window. The pygame window's text is secondary, and the WAVs and speech are the real interface.
