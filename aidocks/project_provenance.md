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
- **the full `README.md`**. Their version was lost before the initial commit: the repo only ever held GitHub's two-line stub, and neither the history nor Git's unreachable objects had their text. The dev restored it by hand on 2026-09-22. It was committed with updates and a Credits section as `4491f93`, which was then rewritten and force-pushed as **`7cf3e78`**, at the dev's request, to add `Co-authored-by: lbk2907`. The local backup branch `backup/before-readme-coauthor` was deleted the same day, once the dev had checked the result on GitHub. `main` is again the only branch.

They handed the repository to the dev, tsatria03, to publish at `github.com/tsatria03/SixthSense-Windows`, so the two of them can work on it together and add more contributors later. Their own version was never on GitHub, and they gave permission to publish it. The dev said all this on 2026-09-21 and plans to add lbk2907 as a contributor on GitHub. Name both by username only ([[feedback_use_github_usernames]]).

**The commit titled "Initial commit" is entirely lbk2907's work, and names them as its author.**
- It was first published as `a7108d2` with the dev as author.
- On 2026-09-21, at the dev's request, it was rewritten and force-pushed as `cf36408`, keeping the same files, message and timestamps.
- Its author is now `lbk2907 <54381410+lbk2907@users.noreply.github.com>`, and its committer is `tsatria03`, who published it.
- The second commit, "Port Sixth Sense to Windows from its reverse-engineered iOS binary", states the same attribution in its description.
- The two local backup branches made during the rewrite (`backup/before-author-rewrite` and `backup/before-username-change`) were deleted on 2026-09-21 at the dev's request, once the dev was happy with the result on GitHub. `main` is the only branch.

**Other contributors:**
- **tunmi13productions** fixed the coin economy and the spoken-digit order in `a16564f` (2026-09-21), found partly through live testing. They also committed batch 2, the vocal fixes (`503085a`), and the zombie batch (2026-09-22) from their own machine, under their own git identity.
- When a contributor's commit and our own work fix the same thing, keep the contributor's version and drop ours. That is the dev's standing preference, first applied to batch 1 on 2026-09-21.

**Why:** Credit and permission matter for this project, and the code itself doesn't say who wrote the initial import.

**How to apply:**
- Credit lbk2907 wherever credits are written: a README, a credits file, or release notes. **`README.md` has had a Credits section since 2026-09-22**, at the dev's request:
  - lbk2907 first, as the one who started the port
  - then the contributors in the order they joined: tsatria03, then tunmi13productions
  - each linked to their GitHub profile, with a line on what they did
  - Bitbee named last, as the original game's maker

  When someone new contributes, add them at the end of the contributors list. The changelog carries no credit lines ([[feedback_changelog]]).
- The dev is the author of their own commits (tsatria03, `156674543+tsatria03@users.noreply.github.com`). Only add them as a co-author when they ask; see [[feedback_git_commits]].
- When lbk2907 contributes to a commit, credit them with `Co-authored-by: lbk2907 <54381410+lbk2907@users.noreply.github.com>`. 54381410 is their public GitHub account ID, and the noreply form links the credit to their profile without exposing an email.
- `LICENSE` (MIT) reads "Copyright (c) 2026 tsatria03 and lbk2907", changed at the dev's request on 2026-09-21. Change it again only if the dev asks, for example to add new contributors.
- Rewriting published history needs the dev's explicit go-ahead each time. For how commits and pushes work in this repo, see [[feedback_git_commits]].
