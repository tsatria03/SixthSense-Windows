---
name: feedback_changelog
description: "Whenever a change players will notice lands (a bug fix or an enhancement), add a plain sentence under unrelease: at the top of changelog.txt, in the same commit. CRLF, no BOM, one sentence per line, no markdown; release builds file the section under the version."
metadata:
  node_type: memory
  type: feedback
---

**Keep `changelog.txt` up to date as game changes land.** Every commit that fixes a bug or adds an enhancement a player will notice also adds a line under `unrelease:` at the top of `changelog.txt`.

**Why:** On 2026-09-22 the dev pointed out that the changelog should have been updated with each bug fix and enhancement. It had been missed since the initial release. The eleven changes from 2026-09-21 were then added in one go.

**How to apply:**
- **Format.** This is what `compiler.py`'s `_parse_changelog` reads:
  - A heading is one word ending in a colon, on a line of its own: `unrelease:` or a version like `26.09.20:`.
  - Every other line is an entry: one plain sentence or two, with no bullets, numbers or markdown.
  - A blank line separates one heading's block from the next.
- **CRLF, no BOM.** Edit it with a small Python script that splits and joins on `\r\n`, and check for bare LFs afterwards, as with the todo list ([[feedback_todo_list_format]]).
- **New lines go at the bottom of the `unrelease:` block**, in the order the changes landed. If there is no `unrelease:` heading, add it at the very top, followed by a blank line before the newest version.
- **Only what a player notices:** fixes, enhancements, removed features, new sounds or files they will see.
  - Leave out notes, docs, tests, refactors and build-script internals, unless they change what ships.
  - Bugs that are only found or planned stay in `todo list.txt`, not here.
- **Wording.** Write for a player, in the style of the todo list's finished section: say what is now true, and avoid contractions.
- **Released entries stay as they are.** A plain release build moves the `unrelease:` lines under the VERSION heading, for example `26.09.21-1:`. Never edit an entry that already has a version heading.
- **No credit lines.** Entries say what changed, not who changed it. On 2026-09-22 the dev chose no credit for tunmi13productions' coin and spoken-number fixes ("no credit"). Don't add contributor credits to the changelog unless the dev asks; commit trailers and [[project_provenance]] carry the credit instead.
