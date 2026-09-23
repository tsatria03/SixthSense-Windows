---
name: project_screen_reader_mode
description: "The dev's idea (2026-09-22): with the voice over row off, the screen reader speaks the game's words, numbers read whole, sfx stay recordings, new players start self-voiced. The menus and result panel built 2026-09-22 and confirmed by ear; the tutorial and in-play announcements stay recordings by the dev's decision."
metadata:
  node_type: memory
  type: project
---

**Built for the menus and the result panel on 2026-09-22, and the dev confirmed it by ear the same day (now in the todo list's finished section).** The intro, main menu, shop, inventory and the stage's pause/result/game over panel speak in mode 0. **The dev decided (2026-09-22) that the tutorial and the announcements during play stay recordings in both modes**, because their timing follows the recordings; don't propose converting them unless asked. What was built:
- The panel: `Stage_1_E.pause_row_text`, `_panel_voice` and `PANEL_MESSAGE_TEXT` (227, 229, 354, 358); in mode 0 activating a result row rereads it instead of the off-by-one reader. Test in `test_pause.py`.
- `AppDelegate.saved_mode()` (missing `EYEMODE` means 1) and `app.screen_reader` (mode 0). Used by the menu, the intro and `didFinishLaunching`.
- The dev asked (2026-09-22) for rows as "<name>, Button" for buttons and "Shotgun, Image" for a weapon's picture, so the words live per screen: `ROW_TEXT`/`row_text`/`TITLE_TEXT` on each `BlindScreen` and in `main_controller.ROW_TEXT`, plus `MESSAGE_TEXT` in `blind_screen.py` for replies (259, 260, 351, 352, 359). This replaced the one-choke-point idea below for the menus.
- The voice over row names what choosing it does, as the original does (0xa2b8): 332 in mode 1, "Voice over on, Button" in mode 0. From 2026-09-22 it named the current mode because the dev heard the original as flipped; on 2026-09-23 tunmi13productions asked for the original back, since "voice over on button" while voice over is on sounded like pressing it turns voice over on.
- Wording mostly follows the recordings' file names; the dev may want it polished (the coin row says "The coin is charged after N minutes N seconds").
- Tests added in `test_menu.py` and `test_store.py`; `DIVERGENCES.md` has "A screen reader mode, in the menus so far".

**The original plan, agreed on 2026-09-22:** When the main menu's voice over row is turned off, the screen reader speaks everything the game's recordings would say, and reads numbers whole ("1,250", not digit by digit). It is in `todo list.txt` and in `docs/DIVERGENCES.md` under "Planned: a screen reader mode".

**Why it fits the original:** the original has two modes, and `ModeChageAction:` (0xb830) switches between them.
- `app.mode` 1 is the self-voiced mode, "the voice over lady".
- `app.mode` 0 is the standard screens, which the iPhone's VoiceOver reads. `RankingAction:` (0xaef4) only opens the ranking page while VoiceOver runs.

The port has no standard screens, so mode 0 becomes "the Windows screen reader speaks the game's words".

**Decisions:**
- **New players start in the self-voiced mode** (the dev, 2026-09-22). The choice is saved under `EYEMODE`.
- This also fixes the todo item "'Not enough gold' is silent on a new save, and the mode row says voice over is on". Today `app.mode` defaults to 0 on a new save, and `buyAction:` only plays 259 in mode 1.

**Design (Claude's proposal, which the dev liked):**
- **Speech is replaced, sound effects are not.** Anything whose file is under `game/sounds/used/speech/` is spoken as text in screen reader mode. Everything under `sfx/` still plays: zombies, weapons, breathing, music and ambience. The folder decides, so there's no hand-made list of which sounds are speech.
- **One choke point.** `AppDelegate.playSound_Gain_Pos_z_reprats_` gets a table from sound number to text. In mode 0 it speaks instead of playing, and `stopSoundBufNumber_` or `StopElseSpeak` interrupts the speech.
- **Numbers:** `TTSNumber_type_` speaks the formatted number, with its unit ("minutes", "coins are full"), in one go instead of the one-second digit timer.
- **Labels and values together:** the rows that read a number 2 s after their label (`READ_DELAY`) should speak "Score, 1,250" as one line in mode 0.
- **Timing:** delays tied to a recording's length need a mode-0 version. For example, the tutorial waits 9.5 s (6.5 for beat Eight) before `tutorial_sound_stop` spawns the zombie.

**Prerequisites:**
- **Text for the speech recordings.** The sound list uses 126 speech recordings:
  - by folder: 29 in `speech/game`, 2 in `logos`, 47 in `menus`, 10 in `numbers`, 12 in `tutorials` and 26 in `weapons`
  - The 10 digits are replaced by whole numbers.
  - Many file names are already their words, like "Store Button".
  - The binary has some texts: `WELCOME_TEXT` and `STORY_TEXT` in `intro.py`, and the shop's "This weapon has been purchased." and "Gold is lacking.".
  - The tutorial lines and the longer ones must be transcribed by the dev by ear, since Claude can't hear audio.
- **A dependable speech layer:** NVDA, JAWS and the rest, and SAPI without comtypes. The Prism layer was built on 2026-09-22 and the dev confirmed it works ([[project_prism_speech]]), so this prerequisite is done.

**Suggested stages:**
1. The speech layer, and `EYEMODE` defaulting to self-voiced.
2. The menus, shop and inventory.
3. The result panel.
4. The tutorial and the announcements during play.

**Home and End, 2026-09-23:** in screen reader mode only, Home and End go to the first and last row. They work in the main menu (`MainController.jump`), in every `BlindScreen`, meaning the shop, the inventory and the opening screen (`BlindScreen.jump`), and on the pause and result panel (`Stage_1_E.pause_jump`, which the test range's own `pause_rows` also uses). The keys are handled in `menu_input.py`, `screen_input.py` and `Input.handle_panel`. With voice over on, the main menu's Home still goes to row 1, and End repeats the current row. Tested in `test_menu` and `test_pause`.

**Tutorial key hints, 2026-09-23 (confirmed by the dev the same day):** tunmi13productions asked that, with voice over off, the tutorial keep its recordings and the screen reader add the keyboard equivalent. `Stage_Tutorial.key_hint` speaks from `KEY_HINTS` in `tutorial_sound_stop`, after the recording (every recording is shorter than its 9.5 s or 6.5 s stop, measured), using the live `KeyMap` bindings, such as "Press A or Left Arrow to shoot toward 9 o'clock." FiveHalf has no hint. A chord bound with both Left and Right Shift (or Control, Alt) is said once as "Shift", which beat Nine used for Shift plus Tab until it became "Press P to end the tutorial." with the tutorial ending (`_merge_sides`, asked for the same day). Teardown stops the speech. Test: `test_tutorial.test_voice_over_off_adds_the_keys_after_the_prompt`. This adds to the recordings rather than replacing them, so the earlier decision that the tutorial stays recorded still holds.

**How to apply:** Keep the recordings the default and the reference. Screen reader mode is a deliberate divergence, and each piece that lands needs its line in `DIVERGENCES.md`. Don't drop a recording's text into code without the dev confirming the wording for the ones whose file names don't already say it.
