---
name: feedback_todo_list_format
description: "todo list.txt: ##unfinished. then ##finished. headings, one plain sentence per line stating the bug itself (never \"Fix a bug where\"), new items at the top, LF endings, no markdown or numbers."
metadata:
  node_type: memory
  type: feedback
  originSessionId: 8a78e7c9-236d-421e-8e76-c11a2895c278
---

`todo list.txt` at the repo root, with a space in the name, is the dev's task list. Its format:
- `##Unfinished.` on the first line, a blank line, then one item per line.
- A blank line, then `##Finished.` with its items below. The dev capitalized both headings on 2026-09-21; keep them that way.
- Each item is a plain sentence or two. **A bug is stated as what happens, with no "Fix a bug where" in front**: "Switching weapons refills the magazine for free.", not "Fix a bug where switching weapons refills the magazine for free." The dev found that opening too repetitive (2026-09-21).
- An enhancement or task starts with what to do: "Add ...", "Make ...", "Remove ...", "Update ...", "Decide whether ...", "Test ...".
- A `##finished.` item says what is now true, starting with its subject: "The license credits tsatria03 and lbk2907.", "The compiler has been changed to build Sixth Sense." List real milestones, not housekeeping like rewording this file, with the most significant first. The first six were added on 2026-09-21 at the dev's request.
- No numbering, no bullets, no markdown, no file:line references. Write in plain words about what the player or dev experiences.
- Avoid contractions, as the existing lines do ("does not", not "doesn't").
- **New items go at the top of `##unfinished.`**, most important first, above the existing ones.
- The file uses **LF** line endings with no BOM (checked 2026-09-22; older notes said CRLF). Match what the file has when you edit it. Keep every line well under 1024 characters.

**Why:** The dev asked on 2026-09-21 for new items to go at the top and for the file's existing style to be matched. They read it by screen reader, so plain sentences read cleanly and markdown symbols would be spoken aloud.

**How to apply:**
- After editing, check the line endings with a byte check (the Edit tool can insert LF-only lines).
- Move an item to `##finished.` only when the dev confirms it is done, not when code lands, since the dev runs and verifies; see [[feedback_dont_run_or_build]].
- The technical detail behind each item (file:line, binary evidence, root cause) lives in [[project_evaluation_2026_09]], not in the todo file.
