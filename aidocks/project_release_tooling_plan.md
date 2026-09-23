---
name: project_release_tooling_plan
description: "PLANNED, not built (2026-09-23): split the build from the release. compiler.py only builds and zips, with a new option to embed the sounds and game data in one exe; a new releaser.py sets the date version, files the changelog, runs the compiler, commits, tags V<version> and uploads the zip to GitHub. Every decision the dev made, and what is still waiting."
metadata:
  type: project
---

**Status: planned on 2026-09-23, every question answered, waiting for the dev's go-ahead to build.** Nothing here exists in code yet. When it is built, change this status to "built, not yet confirmed". Change it to "finished" only once the dev says it works ([[feedback_record_plans_first]]), then fold the lasting parts into [[project_compiler_py]].

The dev asked for "a releaser python script", pointing at two references in the gitignored `user/` folder: a release script from another of their projects (a numbered menu of git and release steps, driving `gh`) and another port's build script (a PyInstaller one-file build with the game data added inside). Read both there, but never name them in writing ([[feedback_no_other_games]]).

## The split (the dev's words: the compiler "should only deal with compiling the game and packaging it into a zip, also an option to embedded most things into the exe file", and the releaser "will handle everything else, like creating tags, finding packages, and then uploading them")

### compiler.py: build and zip, nothing else
- Never touches `changelog.txt` or `VERSION` any more. `prepare_release_files`, `plan_changelog` and the rest of the filing move to the releaser. The menu's "Release build" becomes a plain "Build and zip".
- Keeps taking the empty `unrelease:` heading out of the copy beside the exe (`strip_shipped_changelog`), and keeps warning when that copy still has unreleased lines (`release_warnings`).
- **New: an embed option**, a single exe with the game's data inside, through PyInstaller `--onefile` and `--add-data`. Whole folders are passed, not one entry per file, or the command line gets too long. `paths.py` needs no change: frozen, `ROOT` is `sys._MEIPASS`, and `_candidates()` already tries `ROOT/game`.
  - **Inside:** `game/sounds/used` (329 files, about 125.6 MB, with its folders), the 142 `.plist` files and the three map layers `g_CH1_E`, `a_CH1_E.txt`, `s_CH1_E.txt` (about 0.3 MB). This is exactly what `copy_game()` copies today.
  - **Never packed, in any build:** the PNG and JPG images, the nibs, `en.lproj`, the iOS executable `game/sixsense`, `iTunesArtwork`, `PkgInfo`, `_CodeSignature`, `FacebookSDKResources.bundle`, `stage1ground`, `stage1sound` and `game/sounds/unused`. The game never opens them. The dev first said "the game's binary", meaning the `game` folder, and agreed once the list was explained.
  - The cost, told to the dev: a one-file exe unpacks its roughly 126 MB to a temp folder on every launch, so it starts a few seconds slower.
- **Beside the exe, never embedded ("Docks never get embedded"):** `changelog.txt`, **`todo list.txt` (new, the dev asked for it to ship)**, `license.txt`, `VERSION` and the `licenses` folder. `todo list.txt` goes into `SIDE_FILES` under its own name. This is why the todo list became players only ([[feedback_todo_list_format]], [[project_dev_tasks]]).
- Folder builds stay as they are, with the data beside the exe in `game\`.

### releaser.py: new, beside compiler.py
A numbered menu like the compiler's: "Full release", plus each step on its own. Each step asks Y or N. **Only the release steps**: no commit, undo, push, history or hand-made tag options ("I do not plan to make hand written commits or tags myself"). **No website step**, because Sixth Sense has no website.
1. **Check** that the tree is clean and pushed, `gh` is there (`C:\Program Files\GitHub CLI\gh.exe`; the dev's shared `%USERPROFILE%\.game_tools\tools.ini` has a `gh` entry), and `unrelease:` has lines.
2. **Version, automatic** (the dev: "I'd rather it be automatic"): today's date as `YY.MM.DD-N`, the format kept, written to `VERSION`. N is that day's release number, counted from the existing `V<date>-*` tags: `-1` for the first release of the day, `-2` for the second. The repo has no tags yet, and `VERSION` still says `26.09.21-1` from the first commit.
3. **Changelog:** file the `unrelease:` lines under the new version, the moved `plan_changelog` logic. It keeps the old `VERSION` and changelog, and puts both back if the build fails, so a failed build still leaves the repository unchanged.
4. **Build:** run the compiler, and ask for a folder build or the single exe.
5. **Commit and push** `changelog.txt` and `VERSION`.
6. **Tag:** `V` plus the version, for example `V26.09.23-1` (the dev: "That's how tags work on github"). Push the tag. Refuse to overwrite a tag or release that already exists.
7. **Upload:** find the zip in `dist\`, then `gh release create` with the title **`SixthSense V<version>`** (for example "SixthSense V26.09.21-3"), and that version's changelog lines as the notes.
- **Archive: a zip only**, as now. The dev turned down a password-protected 7z.

### Also in the same change
- New `tests/test_release.py`, covering only what can be checked without building or uploading: the version numbering against a list of tags, filing the changelog, and finding the zip. Run only that file ([[feedback_dont_run_or_build]]).
- README.md, CLAUDE.md and [[project_compiler_py]] describe how to build and release.
- The dev runs the releaser and the compiler. Claude never runs either, and never builds or uploads.

## Related rules made the same day
- A release aims for 50 to 100 changelog entries, can go out with fewer, and never holds more than 100. The first release goes out with the 70 it has ([[feedback_changelog]]).
- Debug mode is developer-facing and never goes in the changelog or the todo list ([[project_dev_tasks]]).
