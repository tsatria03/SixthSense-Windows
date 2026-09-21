---
name: feedback_use_github_usernames
description: "Name people by GitHub username (tsatria03, lbk2907), never real names, in commit authors and committers, co-author lines, commit messages and committed notes."
metadata:
  node_type: memory
  type: feedback
  originSessionId: 8a78e7c9-236d-421e-8e76-c11a2895c278
---

Identify people by their GitHub username, never their real name. The dev is **tsatria03**, and the port's original creator is **lbk2907**. This applies to:
- commit author and committer names
- `Co-authored-by:` lines, for example `Co-authored-by: lbk2907 <54381410+lbk2907@users.noreply.github.com>`
- commit messages
- everything committed to the repo, including `CLAUDE.md`, `aidocks/` and `todo list.txt`, because all of it is public on GitHub

**Why:** The dev asked on 2026-09-21 for tsatria03 in place of their real name, and the same for the original author. Both commits were rewritten and force-pushed to match.

**How to apply:**
- This repo's own Git config has `user.name = tsatria03`, set with `git config --local`; the dev's global name is left as it was. Check `git config user.name` before committing. If it has drifted, pass `--author="tsatria03 <156674543+tsatria03@users.noreply.github.com>"`.
- Emails stay the GitHub noreply addresses, since those are what link a commit to the right profile.
- The one real name left in the repo is the copyright line in `LICENSE`. That is a legal notice inside lbk2907's commit, so leave it unless the dev asks.
