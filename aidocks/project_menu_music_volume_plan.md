---
name: project_menu_music_volume_plan
description: "PLANNED 2026-09-25, not built yet. Page Up and Page Down make the menu music (bgm_main_menu) louder and quieter, 0 to 100% in steps of 10, 100% being today's -14 dB; only on the menu screens, never in a game; saved in defaults.json; spoken with voice over off only. The level music, the ambience and the story music stay as they are."
metadata:
  type: project
---

**Status: PLANNED, 2026-09-25.** Agreed with the dev, recorded before any code ([[feedback_record_plans_first]]). Mark it finished only once the dev says it works.

**The dev's request:** "I know the original game had no way to turn down the menu music, but I want page up/down to be able to turn down the menu music in both screen reader and self voiced modes. The game music can stay as is." They pointed to an example they keep in the gitignored `user/` folder, a port of another game that does the same; read it there, never name it ([[feedback_no_other_games]]). Then: the percentage is spoken "only if the voice over is turned off".

**Why it is a port addition:** the original never plays music on its menu. `bgm_main_menu` is the port's own (`AppDelegate.BGMusicStart`, `app_delegate.py`, a PORT ADDITION), played at `volume.menu_music()`, which is `MENU_MUSIC_DB` (-14 dB) and nothing else ([[project_volume_knobs]]). No other sound uses that knob, so changing it cannot touch the original's mix. Record it in `aidocks/DIVERGENCES.md` under the port's own additions.

## What it does
- **Keys:** Page Up makes the menu music louder, Page Down quieter. Nothing in the game uses either key yet.
- **Steps:** 0 to 100% in steps of 10, holding at both ends. **100% is today's loudness**, -14 dB, never louder, since -14 dB was set by ear so the menu's own rows can be heard over the music.
- **The curve:** the percentage is squared before it becomes a gain, as the example does, so each step sounds about as big as the last. In decibels that is `MENU_MUSIC_DB + 40 * log10(percent / 100)`, and 0% is silent (gain 0).
- **Heard at once:** a press sets the menu music's gain straight away when the music playing is `bgm_main_menu`. The background player is shared with the level music, so it checks which track is playing first and never changes a level's music.
- **Where the keys work:** the screens the menu music plays under: the main menu (`MenuInput`), and the shop, its weapon list and weapon pages, and the inventory (`ScreenInput`). **Not** the opening screen (no menu music there; the story row has its own music), a stage, the tutorial, the pause and result panel, the weapon test range or the F1 screen. The keys do nothing there.
- **Spoken:** with voice over off (the screen reader mode), each press says "Menu music volume 70%" through the screen reader, cutting off the line before. With voice over on, nothing is spoken; the music changing is the answer, since no recording says a percentage. At either end a press says the same percentage again with voice over off, and nothing with it on.
- **Saved:** in `defaults.json` under a new key, `MENUMUSICVOLUME`, as a whole number. A missing or unexpected value means 100. Every later start plays the menu music at the saved level, `BGMusicStart` included, and so does coming back from a game.

## Where it goes
- `platform/volume.py`: `MENU_MUSIC_VOLUMES` (0..100 by 10), `DEFAULT_MENU_MUSIC_VOLUME = 100`, and `menu_music(percent)`, the gain for a percentage. `menu_music()` keeps working for the saved value.
- The saved value read and written through `UserDefaults`, beside the other keys the port adds.
- One helper that both `MenuInput` and `ScreenInput` call for `page up` and `page down`: step, save, set the playing menu music's gain, speak in the screen reader mode. `ScreenInput` skips it on the opening screen.
- `F1`'s screen: list Page Up and Page Down as "Menu music louder" and "Menu music quieter", like Escape and F1, as fixed keys, not rebindable, so `keys.json` does not change.
- `docks/readme.txt` (the menus section) and `README.md` (the controls) say what the keys do. `docks/changelog.txt` gets an entry.

## Tests
- A new check in `tests/case/menu.py` (or its own file): the steps and both ends, the saved value, the gain at 100% equal to today's, 0% silent, the voice over on and off speech, nothing on the opening screen, and a level's music never touched. Run only the files that cover what changed ([[feedback_dont_run_or_build]]).

## Left for later
- The dev has a separate suggestion about `defaults.json`, to be talked about after this.
