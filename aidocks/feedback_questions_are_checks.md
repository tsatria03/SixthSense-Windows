---
name: feedback_questions_are_checks
description: A question about the original or the port is a check - answer it in chat, don't edit code, comments or docs off the back of it.
metadata:
  type: feedback
---

When the dev asks a question about the original or the port ("didn't the menu music fade out?"), or states a fact in reply ("the menu music never starting was a bug in the original"), answer it in chat and change nothing. Findings from the check, even a correction to the docs, are reported and offered, not written.

**Why:** On 2026-09-24 the dev asked whether the menu music faded, then said the silent first menu was an original bug. Claude rewrote docstrings, DIVERGENCES and memory notes to match. The dev said "it was just a check, not something to be modified in terms of docs" and had it all reverted.

**How to apply:** Only edit files when the dev asks for a change. If a check turns up something wrong in the docs, mention it in one line and let the dev decide.
