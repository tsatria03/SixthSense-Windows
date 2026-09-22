# SixthSense-Windows memory index

The `[[name]]` links in `CLAUDE.md` and across these memories resolve to `aidocks/<name>.md`. Add a one-line pointer here for every new memory. "Memory" or "memories" always means this folder, never the `~/.claude` store.

## Project: what the port is and how to work on it
- [Python only](project_python_only.md): the port is written entirely in Python (pygame, OpenAL Soft through ctypes, NVDA or SAPI).
- [compiler.py](project_compiler_py.md): the build script was adapted to Sixth Sense on 2026-09-21 but not yet built by the dev. It copies only the 414 game files it needs. --test and readme.html were left out until the game writes a log and has a README.
- [Binary analysis notes](project_binary_analysis_notes.md): addresses are VM addresses (file offset = addr - 0x1000). The dc_ listings drop register saves and hide the isPlaying branch. Use selrefs to prove whether something is ever called.
- [Safe test run](project_safe_test_run.md): the tests write the real save and play audio. Redirect APPDATA and use `ALSOFT_DRIVERS=null`. The tests are plain scripts. Baseline 96/96.

- [Provenance and credits](project_provenance.md): lbk2907 created the port and extracted the binary. The "Initial commit" is all their work and names them as author. They handed the repo to tsatria03 to publish and work on together. Co-author them with the noreply address, and never co-author the dev.

## Current state
- [Evaluation 2026-09](project_evaluation_2026_09.md): the full evaluation, with root causes of the three todo bugs, prioritized findings with file:line and binary evidence, docs entries that are misreadings, open decisions, and a suggested fix order.

## Feedback: how the dev wants you to work
- [Memory in aidocks](feedback_memory_in_aidocks.md): all memory goes in aidocks/ with this index, and CLAUDE.md is a lean dispatcher under 40,000 chars.
- [Git commits and pushes](feedback_git_commits.md): commit only when asked, then push right away without asking. Force pushes and history rewrites need an explicit go-ahead. Use `git commit -F` with a message file (PowerShell breaks quotes), and never hide git's errors.
- [GitHub usernames, not real names](feedback_use_github_usernames.md): name people by GitHub username (tsatria03, lbk2907) in commit authors, co-author lines, commit messages and committed notes. This repo's git user.name is set to tsatria03.
- [No other games](feedback_no_other_games.md): never name or refer to the dev's other games in the todo list, memory files, CLAUDE.md, or Python code and comments. Write about Sixth Sense alone.
- [Don't run or build](feedback_dont_run_or_build.md): never build unless told. Ask before running the game, the tests, compiler.py, or any script that executes game code. Read-only inspection is fine.
- [Todo list format](feedback_todo_list_format.md): `todo list.txt` has ##unfinished. then ##finished. headings, one plain sentence per line, new items at the top, CRLF, no markdown. Bugs are stated plainly, never as "Fix a bug where". Items move to finished only when the dev confirms.

## User
- [Screen reader](user_screen_reader.md): the dev works with NVDA running. Prefer lists and short lines to wide tables, and never make noise or speak through NVDA from tools or tests.
