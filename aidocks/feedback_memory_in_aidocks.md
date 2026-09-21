---
name: feedback_memory_in_aidocks
description: "All memory lives in the repo's aidocks/ folder with a MEMORY.md index; CLAUDE.md is a lean dispatcher pointing at it. Never write to the ~/.claude memory store."
metadata:
  node_type: memory
  type: feedback
  originSessionId: 8a78e7c9-236d-421e-8e76-c11a2895c278
---

Write every memory for this project into `aidocks/` at the repo root, never into the `~/.claude` memory store. `aidocks/MEMORY.md` is the index: add a one-line pointer there for every new memory, grouped by section. `CLAUDE.md` at the repo root is a lean dispatcher (under 40,000 characters) that orients and then points at memories with `[[name]]` links, which resolve to `aidocks/<name>.md`.

**Why:** The dev asked for this on 2026-09-21 so memory travels with the repo, in the layout they use.

**How to apply:** Name files `feedback_<slug>.md`, `project_<slug>.md` or `user_<slug>.md`. Use frontmatter with `name` (same as the filename), a quoted `description`, and `metadata: {node_type: memory, type: ...}`. For feedback and project memories, follow the fact with **Why:** and **How to apply:** lines. When a CLAUDE.md section grows past a few lines of real detail, move it into a memory and leave a `[[name]]` pointer. `CLAUDE.md` and `aidocks/` are committed, not gitignored.
