---
name: feedback_record_plans_first
description: "Write a plan into its own aidocks note before building it, especially big ones like the releaser; mark it finished in that same note only once the dev says it works."
metadata:
  type: feedback
---

**Record a plan in aidocks before starting on it.** Once the dev and Claude have agreed a plan, it goes into its own note, `aidocks/project_<name>_plan.md`, with a pointer in `MEMORY.md`, before any code is written. The note keeps every decision, the dev's own words where they settle something, and what is left out and why. The first was [[project_release_tooling_plan]].

**Mark it finished only when the dev says it works.** Its status stays "planned" while waiting for the go-ahead, then "built, not yet confirmed" once the code lands, and becomes "finished" only when the dev confirms it works, in that same note and its `MEMORY.md` line. Code landing, or tests passing, is not enough. This is the same rule as the todo list's ([[feedback_todo_list_format]]).

**Why:** The dev said on 2026-09-23: "In the future, we need to record plans down before commiting to them, especially the releaser thing because that is a huge one," and "mark the plan as finished in that same memmory file, but only after I know it works." A plan agreed in conversation is lost when the context is compacted, and a big change built from memory drifts from what was agreed.

**How to apply:**
- A plan big enough to need questions answered gets a note before its first edit. A one-line fix does not need one.
- If the plan changes while it is being built, update the note first, then the code.
- Update the note as each part lands, and say which parts are built and which are waiting.
- A finished plan stays as a record. Don't delete it.
