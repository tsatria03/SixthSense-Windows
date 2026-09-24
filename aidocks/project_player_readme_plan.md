---
name: project_player_readme_plan
description: "PLANNED 2026-09-23: docks/readme.txt, a plain-text readme for players that ships beside the executable as readme.txt, based on README.md minus everything for developers, one sentence per line. The dev approved a five-sentence sample and asked for the real thing."
metadata:
  type: project
---

**Status: PLANNED, 2026-09-23.** The dev asked for it after the player documents moved into `docks/` ([[feedback_record_plans_first]]: this note is committed on its own first, and nothing is pushed until it is built and tested). Marked finished here only once the dev says it works.

## Why
The repository's `README.md` is for developers: Markdown, Python requirements, tests, the build, the binary. A player who downloads a release gets the executable with `changelog.txt`, `todo list.txt`, `license.txt` and `VERSION` beside it, and nothing that says how to play. A `.md` file would be read aloud with its `#`, `*` and `|`, which is why `compiler.py` never shipped the README ([[user_screen_reader]]).

## What the dev decided
- **Plain text, no markdown.** The dev approved a sample of five sentences, written to their scratchpad on 2026-09-23 ("Perfect. I like it."): what the game is, why to wear headphones, the logo and the menu, F1, and coins.
- **One sentence per line** ("In the real readme, these would be split in to lines").
- **Based on README.md, minus the developer stuff** (the dev's words).

## The design
- **File:** `docks/readme.txt`, UTF-8 without BOM, LF endings like the other player documents, no contractions, in the todo list's plain style ([[feedback_todo_list_format]]).
- **Layout:** a section title alone on a line (no `#`, no colon), then its sentences one per line, with a blank line between sections.
- **Sections, from README.md's player parts:**
  1. Sixth Sense: what it is (the sample's first sentence), Bitbee's game from 2013, ported to Windows.
  2. Headphones: the sample's second sentence.
  3. Starting: the logo, Enter and Escape, the opening screen's three rows (the welcome, how to skip, the story).
  4. The main menu: its six rows (coins, title, Start Game, Tutorial, Store, voice over), Up and Down, Enter; Left, Right, Home and End with voice over off.
  5. Coins: a game costs one, a new player starts with ten, one comes back every 30 minutes up to five, even while the game is closed.
  6. The tutorial: ten lessons, taken first on the first Start Game; P ends it at its last lesson.
  7. Controls: each lane on its own line (A or Left, Q or Left and Up together, W or Up, E or Right and Up together, D or Right), reload (S, R or Down), Tab and Shift+Tab, Space, P, Escape, F1. Checked against `keymap.ACTIONS` on 2026-09-23.
  8. Changing keys: the F1 screen's keys (Up and Down, Enter, A, Delete, R twice, Escape or F1), that F1 and Escape cannot be rebound, and that it speaks through the screen reader or a Windows voice.
  9. How to play: the five lanes, footsteps getting closer, attack before it reaches you, the gap in the breathing for a headshot, your own breathing as your health.
  10. The shop: the weapon list, a weapon's page, Try for the test range, the inventory; gold is 12 a kill and 2 a headshot (`ObtainedGold`, 0x3c616).
  11. Voice over: on, the game's own recordings; off, the screen reader reads the menus, the shop, the inventory, the opening screen and the result panel, and names the keys in the tutorial.
  12. Your save: `%APPDATA%\SixthSense`, `defaults.json` and `keys.json`.
  13. Credits: Bitbee's game; lbk2907 made the port; tsatria03 and tunmi13productions, by GitHub username ([[feedback_use_github_usernames]]); a line each, no long lists.
  14. Licenses: the license.txt and the licenses folder beside the game, and that the game's sounds and data are Bitbee's.
- **Left out:** Python and pip, command-line flags, debug mode ([[feedback_changelog]]: players never see it), the layout, tests, building and releasing, the choosers, where the port came from, the porting status.
- **Shipping:** `compiler.SIDE_FILES` gains `docks\readme.txt`, shipped as `readme.txt`. The comment about a future `readme.html` goes. `tests/case/release.py` checks it ships and that the file is in `docks/`.
- **Docs:** README.md's layout and "Building and releasing" name it, CLAUDE.md's `docks/` line and [[project_compiler_py]] list it, and the changelog gains a line (a player sees a new file beside the game). The todo list line goes to finished once the dev confirms it.

**How to apply, after it lands:** whenever a change alters something the player readme says (a key, the menu rows, coins, the opening), update `docks/readme.txt` in the same commit, as with the changelog.
