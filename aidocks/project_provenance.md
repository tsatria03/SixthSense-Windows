---
name: project_provenance
description: "lbk2907 is the original creator of the port, and the Initial commit is entirely their work and names them as author. They handed the repo to tsatria03 to publish on GitHub and work on together. How to credit them."
metadata:
  node_type: memory
  type: project
  originSessionId: 8a78e7c9-236d-421e-8e76-c11a2895c278
---

**lbk2907 is the original creator of this repository.** Their work covers:
- extracting the binary (`analysis/bin/sixsense_armv7`)
- the analysis tools in `tools/` and everything in `analysis/`
- the whole Python port (`SixthSense.py`, `sixthsense/`)
- `docs/` and `tests/`

They handed the repository to the dev, tsatria03, to publish at `github.com/tsatria03/SixthSense-Windows`, so the two of them can work on it together and add more contributors later. Their own version was never on GitHub, and they gave permission to publish it. The dev said all this on 2026-09-21 and plans to add lbk2907 as a contributor on GitHub. Name both by username only ([[feedback_use_github_usernames]]).

**The commit titled "Initial commit" is entirely lbk2907's work, and names them as its author.**
- It was first published as `a7108d2` with the dev as author.
- On 2026-09-21, at the dev's request, it was rewritten and force-pushed as `cf36408`, keeping the same files, message and timestamps.
- Its author is now `lbk2907 <54381410+lbk2907@users.noreply.github.com>`, and its committer is `tsatria03`, who published it.
- The second commit, "Port Sixth Sense to Windows from its reverse-engineered iOS binary", states the same attribution in its description.
- Two local branches keep the earlier versions on the dev's machine: `backup/before-author-rewrite` (the history as first published) and `backup/before-username-change` (the version with real names). Neither is pushed, and the dev can delete both once they're happy.

**Why:** Credit and permission matter for this project, and the code itself doesn't say who wrote the initial import.

**How to apply:**
- Credit lbk2907 wherever credits are written: a README, a credits file, or release notes.
- The dev is the author of their own commits (tsatria03, `156674543+tsatria03@users.noreply.github.com`), so never add them as a co-author.
- When lbk2907 contributes to a commit, credit them with `Co-authored-by: lbk2907 <54381410+lbk2907@users.noreply.github.com>`. 54381410 is their public GitHub account ID, and the noreply form links the credit to their profile without exposing an email.
- `LICENSE`'s copyright line still names the dev by real name. Whether to change it, or add lbk2907, is for the dev and lbk2907 to decide; don't change it unasked.
- Rewriting published history needs the dev's explicit go-ahead each time. Don't commit or push unless the dev asks.
