---
name: feedback_no_question_pickers
description: "Ask questions as plain text in the reply, never through the multiple-choice picker tool (AskUserQuestion). The dev asked for this on 2026-09-22."
metadata:
  node_type: memory
  type: feedback
---

**Never ask the dev anything through the question picker** (the `AskUserQuestion` tool, which draws a menu of options the dev has to move through). Ask in the reply instead, in plain sentences.

**Why:** The dev asked for this on 2026-09-22, after a picker was used to offer two designs for the volume constants. They read by screen reader, and a picker is a separate control to navigate rather than text they can read straight through ([[user_screen_reader]]).

**How to apply:**
- Put the question at the end of the reply, in a short numbered or bulleted list when there is more than one choice.
- Say which one is recommended and why, in one line each, so a plain "the first one" is enough to answer.
- Keep code or layout samples in a fenced block in the reply, the same as any other explanation.
