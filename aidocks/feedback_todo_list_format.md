---
name: feedback_todo_list_format
description: "todo list.txt: ##unfinished. then ##finished. headings, one plain sentence per line, new items at the top of ##unfinished., CRLF endings, no markdown or numbers."
metadata:
  node_type: memory
  type: feedback
  originSessionId: 8a78e7c9-236d-421e-8e76-c11a2895c278
---

`todo list.txt` at the repo root, with a space in the name, is the dev's task list. Its format:
- `##unfinished.` on the first line, a blank line, then one item per line.
- A blank line, then `##finished.` with its items below.
- Each item is a plain sentence or two: "Fix a bug where ...", "Add ...", "Make ...", "Remove ...", "Update ...", "Decide whether ...".
- No numbering, no bullets, no markdown, no file:line references. Write in plain words about what the player or dev experiences.
- Avoid contractions, as the existing lines do ("does not", not "doesn't").
- **New items go at the top of `##unfinished.`**, most important first, above the existing ones.
- The file uses **CRLF** line endings with no BOM. Keep every line well under 1024 characters.

**Why:** The dev asked on 2026-09-21 for new items to go at the top and for the file's existing style to be matched. They read it by screen reader, so plain sentences read cleanly and markdown symbols would be spoken aloud.

**How to apply:**
- After editing, check the line endings with a byte check (the Edit tool can insert LF-only lines).
- Move an item to `##finished.` only when the dev confirms it is done, not when code lands, since the dev runs and verifies; see [[feedback_dont_run_or_build]].
- The technical detail behind each item (file:line, binary evidence, root cause) lives in [[project_evaluation_2026_09]], not in the todo file.
