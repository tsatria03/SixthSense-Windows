---
name: feedback_no_other_games
description: "Never name or refer to the dev's other games in the todo list, the aidocks memory files, CLAUDE.md, or Python code and comments; write about Sixth Sense alone."
metadata:
  node_type: memory
  type: feedback
  originSessionId: 8a78e7c9-236d-421e-8e76-c11a2895c278
---

Don't mention the dev's other games anywhere in this repo's own files:
- `todo list.txt`
- any `aidocks/` memory file
- `CLAUDE.md`
- the Python code, including its comments and docstrings

That rules out their names, their folder names and their paths, and phrases like "the same as in their other game". Write about Sixth Sense alone.

**Why:** The dev asked for this on 2026-09-21, after the first memories, todo lines and `compiler.py` comments described where things came from by naming other projects. The rule covered the todo list and memory first, and the Python comments were added the same day.

**How to apply:**
- When a fact matters but its source is another project, state the fact on its own. For example, "the dev reviews through a screen reader", not where that was learned.
- When something in this repo came from elsewhere, describe it by where it lives here. For example, "the earlier build script kept for reference in the gitignored `user/` folder".
- Reading material in `user/` for reference is fine; just don't name it in writing.
- Before saving a memory, a todo line or a code comment, check it for other games' names. The gitignored `user/` folder is the only place they belong.
