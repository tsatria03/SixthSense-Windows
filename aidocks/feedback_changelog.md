---
name: feedback_changelog
description: "Whenever a change players will notice lands (a bug fix or an enhancement), add a plain sentence at the top of the unrelease: block in changelog.txt, in the same commit; entries read newest first. LF, no BOM, one sentence per line, no markdown; release builds file the section under the version."
metadata:
  node_type: memory
  type: feedback
---

**Keep `changelog.txt` up to date as game changes land.** Every commit that fixes a bug or adds an enhancement a player will notice also adds a line under `unrelease:` at the top of `changelog.txt`.

**Why:** On 2026-09-22 the dev pointed out that the changelog should have been updated with each bug fix and enhancement. It had been missed since the initial import, and the eleven changes from 2026-09-21 were then added in one go.

**The game has never been released.** The same day, the dev removed the `26.09.20: Initial release.` entry because no release had happened. So the changelog has no version headings yet; the first release build creates the first one.

**How to apply:**
- **Format.** This is what `compiler.py`'s `_parse_changelog` reads:
  - A heading is one word ending in a colon, on a line of its own: `unrelease:` or a version like `26.09.21-1:`.
  - Every other line is an entry: one plain sentence or two, with no bullets, numbers or markdown.
  - A blank line separates one heading's block from the next.
- **LF, no BOM.** Checked 2026-09-22: both the working tree and HEAD use LF, whatever older notes said. Match the endings the file has when you edit it, and check afterwards.
- **New lines go at the top of the `unrelease:` block**, straight under the heading, so the block reads newest first. The dev asked for this on 2026-09-22 and the 23 lines that had built up in landing order were reversed then. If there is no `unrelease:` heading, add it at the very top, followed by a blank line before the newest version.
- **Only what a player notices:** fixes, enhancements, removed features, new sounds or files they will see. Debug mode (`--debug`) is developer-facing and never goes here.
  - Leave out notes, docs, tests, refactors and build-script internals, unless they change what ships.
  - Bugs that are only found or planned stay in `todo list.txt`, not here.
- **Wording.** Write for a player, in the style of the todo list's finished section: say what is now true, and avoid contractions.
- **Headings stay as they are** (the dev's choice, 2026-09-22):
  - bare, date-based version numbers like `26.09.21-1:`, which mean year, month, day and that day's build
  - `unrelease:` for changes that are not released yet

  A format like "Version 26.09.21-1:" or "Unreleased:" was offered, which would need `_HEADING`, `UNRELEASE` and `changelog_heading()` in `compiler.py` changed. The dev declined. Don't propose it again unless asked.
- **How big a release is (the dev, 2026-09-23).** A release holds 50 to 100 changelog entries, fixes and enhancements alike, depending on how much the game still needs. The first release closes at 100: `unrelease:` had 78 entries on 2026-09-23, and the dev said "we can do 22 more before wrapping up the change log". The same day the 8 debug mode lines moved out to [[project_dev_tasks]], since debug mode is developer-facing, leaving 70, so 30 to go. Count the entries under `unrelease:` whenever one is added, and say so when the block reaches 100, or nears it, so the dev can plan the release build. Never file the block under a version or run a build yourself ([[feedback_dont_run_or_build]]).
- **Released entries stay as they are.** A plain release build moves the `unrelease:` lines under the VERSION heading, for example `26.09.21-1:`. Never edit an entry that already has a version heading.
- **No credit lines.** Entries say what changed, not who changed it. On 2026-09-22 the dev chose no credit for tunmi13productions' coin and spoken-number fixes ("no credit"). Don't add contributor credits to the changelog unless the dev asks; commit trailers and [[project_provenance]] carry the credit instead.
