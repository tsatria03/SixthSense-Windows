---
name: feedback_git_commits
description: "Commit only when the dev asks, then push to GitHub right away without asking. Force pushes and history rewrites still need an explicit go-ahead. Use git commit -F with a message file, and never hide git's errors."
metadata:
  node_type: memory
  type: feedback
  originSessionId: 8a78e7c9-236d-421e-8e76-c11a2895c278
---

**Commit only when the dev asks.** Once a commit is made at their request, **push it to `origin main` straight away**, without asking. The dev said on 2026-09-21 that they no longer need to be asked about pushing.

**Rewriting published history still needs an explicit go-ahead every time.** That covers force pushes, amending or rebasing pushed commits, and changing authors. When it is approved, push with `--force-with-lease=main:<expected hash>`, and keep a local backup branch until the dev is happy.

**Why:** The dev approves what goes into a commit, and after that, pushing is routine for them. History rewrites can lose work, so they stay a deliberate choice.

**How to apply:**
- Write the message to a file in the scratchpad and run `git commit -F <file>`. Windows PowerShell 5.1 breaks double quotes inside arguments passed to programs, so `-m` messages that contain quotes fail. Never send git's error output to `$null`; a failed commit must be visible.
- Stage files by name when the commit should hold exactly what the dev approved, or `git add -A` when they ask to commit everything; check `git status` first either way.
- Format: a short summary line, a blank line, then a plain-text description wrapped at about 72 characters. End with the trailers: `Co-authored-by: lbk2907 <54381410+lbk2907@users.noreply.github.com>` only when lbk2907 contributed, then the Claude attribution line.
- The dev is always the author. When they ask to be named as a co-author too, as they did on 2026-09-21 for the sound reorganization commit, add `Co-authored-by: tsatria03 <156674543+tsatria03@users.noreply.github.com>`; GitHub shows them once either way. Don't add it unasked.
- Never commit throwaway working folders, such as `game/sounds2/` (the flat originals kept only for matching). Binary files stay in git history forever even after deletion, so leave them out with `':(exclude)path'` and say so.
- Names are GitHub usernames only ([[feedback_use_github_usernames]]). The author is tsatria03 through this repo's local git config.
- After pushing, confirm with `git ls-remote origin refs/heads/main` and report the new commit to the dev.
- Committing isn't building or running; [[feedback_dont_run_or_build]] still applies to those.
