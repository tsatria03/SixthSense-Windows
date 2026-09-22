---
name: project_screen_reader_mode
description: "Planned 2026-09-22 (the dev's idea): turning the voice over row off makes the screen reader speak everything the speech recordings would say, with numbers read whole; sfx stay recordings; new players start self-voiced. Design, prerequisites and suggested stages. Not built yet."
metadata:
  node_type: memory
  type: project
---

**The dev's idea, agreed on 2026-09-22 and not built yet.** When the main menu's voice over row is turned off, the screen reader speaks everything the game's recordings would say, and reads numbers whole ("1,250", not digit by digit). It is in `todo list.txt` and in `docs/DIVERGENCES.md` under "Planned: a screen reader mode".

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

**How to apply:** Keep the recordings the default and the reference. Screen reader mode is a deliberate divergence, and each piece that lands needs its line in `DIVERGENCES.md`. Don't drop a recording's text into code without the dev confirming the wording for the ones whose file names don't already say it.
