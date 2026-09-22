---
name: project_evaluation_2026_09
description: "Full evaluation of the port (2026-09-21): root causes of the three todo bugs, prioritized findings with file:line and binary evidence, doc entries that are misreadings, open decisions, and a suggested fix order."
metadata:
  node_type: memory
  type: project
  originSessionId: 8a78e7c9-236d-421e-8e76-c11a2895c278
---

Full evaluation of the Python port, done on 2026-09-21 with three parallel reviewers (platform, gameplay, menus/tutorial) plus independent byte-level checks. `compiler.py` and `user/` were excluded here; the compiler has its own memory, [[project_compiler_py]]. Line numbers are as of the "Initial commit" (cf36408; first published as a7108d2) plus the working tree that day. **Re-locate by symbol before editing**, because the lines will drift.

How sure each item is:
- [V] means Claude hand-verified it from the raw binary bytes or the code.
- [R] means a reviewer reproduced it in a simulation or traced it in the disassembly.
- [S] means suspected and not fully verified.

Tick items off as they land; anything not marked fixed is still open.

What has landed so far:
- **The coin economy (bug a)** was fixed by tunmi13productions in `a16564f`.
- **Batch 1, by tsatria03, after that commit:**
  - the level music at 0.02 and the ambience at 0.2
  - the rain moved to the ambience player, alone
  - stage `teardown` stopping the footsteps, the ambience and the music
  - no magazine refill on a weapon switch

  Tests: `test_gameplay`'s magazine-kept, ambience-gain and silent-teardown checks. Batch 1 had also fixed the first-launch grant and the 30-minute interval; those halves were dropped in favor of `a16564f`'s versions.

On 2026-09-21 every item below was also added to `todo list.txt` as a plain sentence, most important first, at the top of `##unfinished.` ([[feedback_todo_list_format]]). The todo file is the dev's checklist; this memory holds the technical detail behind each line.

## Overall

The low-level porting is careful: the weapon plist quirks, spawn tiers, hit bands, score formula, voice allocator, NSTimer semantics, atomic saves and ctypes bindings are all correct. The failures are system-level. Monster sounds never move, the boss and level-end flow is missing, and the audio mix buries the monsters. Several `docs/DIVERGENCES.md` entries marked "reproduced" are actually misreadings of the binary; see [[project_binary_analysis_notes]]. The first-run/coin path (bug a, below) was fixed 2026-09-21.

## The three todo-list bugs

### (a) The play button fails with no coins. Critical. **Fixed 2026-09-21.**
- [V] **No first-run grant.** The original `didFinishLaunching` (0x4268-0x430c) checks `[FIREST intValue]`. If it is 0, the original writes COIN="10" and FIREST="1" and synchronizes. The port's `app_delegate.py` `didFinishLaunching` (about lines 99-108) has no such step, so a new player starts with 0 coins.
- [R] **The recharge clock never starts from 0 coins.** `coinTiemrControlStartBackGroundRestart` (`main_controller.py` about 277-282) only runs if `COIN_TIMER_START == '1'`, and that key is written only when a coin is spent (about line 262).
- [V] **The interval is 1800 s (30 minutes), not 600 s.** The binary has `rsb.w r2, r0, #0x708` at 0xc1ee. The port's `COIN_INTERVAL = 600.0` is at `main_controller.py:51`, and `PORTING_STATUS.md` also says 10 minutes.
- [R] **No catch-up for time away.** The original `viewDidLoad` adds elapsed/1800 coins, capped at 5 (0x8aca-0x8b14).
- [R] **Spending a coin restarts a countdown that is already running.** The original writes COIN_TIMER only when no timer exists (0xbe3a). The port rewrites it every time (`main_controller.py` about 262-265, `stage_1_e.py` about 1349-1352).
- [R] **The time to the next coin can't be read out.**
  - The coin row passes type 0 where the original passes 3 (0x9812).
  - `_coin_timer_remaining` (`app_delegate.py` about 246-247) uses `intForKey_` on a date string, which always gives 0.
- [R] **With TUTORIAL unset, Start Game charges a coin and then the player stands still in silence.** The original runs the tutorial inline in `Stage_1_E MapInitInBundle` (0x2e08e-0x2e0dc). The port just logs a warning (`stage_1_e.py` about 266-272).
- **Fix:**
  - Add the FIREST grant. Existing stuck saves have no FIREST key, so they would get 10 coins once.
  - Send Start Game to the tutorial, without charging a coin, while TUTORIAL is 0.
  - Then decide the offline economy (see Open decisions).
- **Done:** all six sub-findings and all three fix steps landed 2026-09-21 (`app_delegate.py`, `main_controller.py`, `stage_1_e.py`). `COIN_INTERVAL` and `COIN_MAX` moved to `app_delegate.py` so `_coin_timer_remaining` could share them. Tests in `tests/test_menu.py`. Along the way, a live-testing session also caught and fixed a digit-order bug in `-[AppDelegate readNumber:]` (0x5cbc): `numberBackUp` was built most-significant-digit-first but read back from the end of the array, so 10 spoke "zero, one" instead of "one, zero" — this was never in the original evaluation. New tests in `tests/test_digits.py`.

### (b) The tutorial repeats "shake the device" after the kill. Critical.
- [R] **`CheckTutorial` never calls `MonsterAttPlayer`** (`stage_tutorial.py` about 145-152). The original does, guarded by isShake (0x8c754-0x8c77a).
  - As a result the grab never happens, isShake is never set, and Space is ignored (`stage_1_e.py` about 983).
  - `tests/test_tutorial.py` about line 152 calls `MonsterAttPlayer()` by hand, which hides this.
- [R] **`tutorial_sound_stop` doesn't set `noAtt = 1` before spawning type 73 at beat Eight** (original 0x8e1a8), so the grabber can be shot.
- [R] **The prompt restarts every second.**
  - `tutorial_beat` never clears `beat_flag[name]`, and `tutorial_beat_end` re-prompts every tick. Prompt 282 therefore restarts every second.
  - Each restart also cancels and reschedules the pending `tutorial_sound_stop`, so the next zombie never spawns.
  - Beats Six, Seven and Nine stutter the same way.
- [R] **P (`tutorial_skip`, `stage_1_e.py` about 1229-1238) writes TUTORIAL=1, but `CheckTutorial` keeps running.** In the original, stop during the tutorial only works once beats One to Eight are done (0x8392a-0x8393c; Stage_1_E 0x33f1e-0x33f30). After that it stops the prompts and timers, writes TUTORIAL, plays 327, and returns to the menu 2 s later.
- **Fix:**
  - Clear `beat_flag[name]` in `tutorial_beat`.
  - Set `noAtt` for beat Eight.
  - End `CheckTutorial` with `if not self.isShake: self.MonsterAttPlayer()`.
  - Give the tutorial its own `MonsterAttPlayer`: grabbers grab, and any other monster is removed and re-prompted with no HP loss.
  - Give the tutorial its own `StopPlayAction_` as described above.
  - Add a test that pumps `CheckTutorial` instead of calling `MonsterAttPlayer` by hand.

### (c) The intro overlaps the menu speech. High.
- [R] **The earphone warning plays at menu load, and the title is read over it.** `main_controller.py` about 116 plays 234 "you must use earphone" in `viewDidLoad`, and the next line reads the title over it. The original plays 234 only from `StartGame:` when no headphones are detected (0xac50-0xacf0).
- [R] **The menu's `StopElseSpeak` (about 129-135) misses sounds 234, 21 and 22.** The original's list includes them (0x9708-0x97a2). It also doesn't cancel `readNumberOfCoin` (0x97e2) or stop the synthesizer.
- [R] **`bgm_main_menu` is a port addition.** It starts at about line 115. The original `MainController` never calls `BGMusicStart`; only `GameEndAction:` does (0x330da).
- [R] **The overlap comes back every time you return to the menu**, because a new `MainController` is built each time.
- [R] **"No coin" plays WAV 358 and speaks the same text through NVDA at the same moment** (about 231-234).
- [R] **The intro's `STOP_SOUNDS = (14,)` should be `(14, 266)`** (`intro.py` about 46; original 0x1863c).

## Critical and high (beyond the todo list)

1. [V] **Monster sounds never move, and the walking loop restarts on every footstep.** `oal_playback.py` `startSound_Postion_` and `startSound_Postion_soundGain_` (about 316-336), called from `monster_control.py` about 315.
   - The original (0xe562) branches on isPlaying. While the sound is playing it sets AL_POSITION to (x, 40.0, y) and the gain, and does not restart it. It plays only when the sound is stopped.
   - Measured for zombie_1 in lane 1: the port stays at -33 dB from 600 cm inward; the original goes -30.9, -24.9, -11.1 dB at 600, 300 and 20 cm.
   - No distance cue, no zig-zag sweep, and a broken breathing rhythm for headshots.
   - `MosterPos_QuereNote_defaultZ_` has no callers.
   - Add a fake-AL test asserting that AL_POSITION changes each step.
2. [V] **`checkBoosDie` compares against boss ids 5001 and 5000, not `gameMode - 2`** (`movw r2,#0x1389` at 0x360d4, `#0x1388` at 0x360e8).
   - [R] The boss spawn is missing. At y == 23 the original spawns 5008 in gameModes 2/3 (0x31d1c) or 5003 in gameMode 1 (0x31e0a) and stops sound 285.
   - [R] The level ends only at y == 22 once the boss is dead. Before changing level, the original kills all remaining monsters, flips gameMode, starts the new ambience, and calls `ChangeLevel:` after 2 s. `ChangeLevel` plays 88/87 at 0.02 looping, not 328.
   - Boss sounds: coming 290, damage 205, die 289, hits the player 288.
   - Port locations: `stage_1_e.py` about 339-343, 387-435.
   - `test_check_boos_die_compares_against_gamemode_minus_two` asserts the misreading.
3. [R] **Action cell 8 (the heal girl or the hostile woman-monster) never spawns in normal play.**
   - The original picks a random id from 10001..10010 (0x320e6-0x322da). After the tutorial it spawns 10008 then 10003 (0x3218a) and clears isTutorialEnd.
   - `_kind_for_type(10003)` is wrong: ids 10001..10005 are kind 21 (0x38aae).
   - When she reaches you the original plays 270 through `hitPlayer` (0x3b2c6).
   - Shooting her costs a heart (0x3a850-0x3a97a).
   - Port: `stage_1_e.py` about 348-354, 514-526, 539.
4. [R] **Free-ammo exploits.** FIXED (batch 1) for the refill on switching. The fire-while-reloading exploit is still open.
   - `gunChangeAction_` refills the magazine on every switch, which the original never does. Two presses of Tab give a full magazine.
   - `GunReloadAction_` doesn't hold `shotFlag`, so you can fire during the reload. The original clears it in `reloadGun:` (0x35f24).
   - Port: `stage_1_e.py` about 939, 948-960.
5. [V] **Turning is a port invention.**
   - `setListenerRotation:` and `setListenerPos:` are not in `__objc_selrefs`, and `MovingAccelerometer` is never instantiated, so the original never turns the listener.
   - After a 90-degree turn, a lane-3 zombie sounds 15 dB to one side but W still attacks lane 3.
   - Port: `input.py` about 77-80, `stage_1_e.py` about 263, 963-969.
6. [V] **The audio mix buries the monsters.** FIXED (batch 1). The gains were confirmed from the raw bytes: 0x3e4ccccd at 0x2ddfa/0x2de08, 0x3ca3d70a at 0x321d4/0x321dc, and 0x3f000000 at 0x2ddc8.
   - Level music: original gain 0.02 (0x321d4), port 0.5.
   - Ambience: original 0.2 (0x2ddfa), port 1.0.
   - gameMode 3: the original plays only rain, on the ambience player, at 0.5 (0x2ddc8).
   - Port: `stage_1_e.py` about 255-261, 360, 362. The port's own `continueAction_` already uses 0.2 and 0.02.
7. [R] FIXED (batch 1). **Escape or closing the window from a stage leaves the monster loops and ambience playing under the menu** indefinitely. `teardown` (`stage_1_e.py` about 1036-1043) should call `MonsterStop()` and `AMBSoundStop()`.
8. [R] **Store screens are built without a speech object**, so "not available" for the coin store, restore and buy-all goes only to the log (`SixthSense.py` about 66-72, `blind_screen.py` about 71-76). Fall back to `Speech.shared()`.
9. [V] **Key rebinding is broken.** Any key-up ends capture (`keybind_screen.py` about 149-151), so releasing Enter reports "Nothing pressed". Finish capture only on the key-up of a captured key. The test never releases Return.
10. [V] **The tests overwrite the real save.** See [[project_safe_test_run]].

## Medium

**Input**
- [R] **Rollover picks the wrong lane.** `keymap.py` about 206-213 matches on all held keys, so holding A and pressing D fires lane 1. Prefer bindings that contain the newly pressed key.
- [R] **Held keys go stale across screens.** Call `keymap.clear_held()` in `Input.__init__` and on window focus loss (`input.py` about 50-55).
- [R] **The reload key skips the attack guards** (`input.py` about 71-72). With the grenade equipped it plays blast 57 with no effect; the original skips the grenade (0x351c8).
- [R] **The three-finger tap is pause, not previous weapon** (0x2ec84 and 0x7edf4). "Previous weapon" is invented, and tutorial beat Nine keys off the wrong action.
- [R] **Shaking free takes 10 Space presses in 2.5 s.** The original needed one shake of about a third of a second (10 samples at 30 Hz, 0x2db20). Consider counting key-repeat while Space is held.

**Run loop (`platform/runloop.py`)**
- [R] **Callbacks can run twice.** A `TypeError` raised inside a callback triggers the "no-argument" retry, so the callback runs again (about 58-61, 141-147). Decide the argument count once with `inspect.signature`.
- [R] **Ordering is wrong.** Due delayed calls always run before due timers, and timers run in creation order. Use one heap keyed by fire time.
- [R] **The clock is coarse.** `time.monotonic()` has 15.6 ms resolution on Windows here; use `time.perf_counter()`. Also, `_by_key` never removes empty lists.

**Saves (`platform/defaults.py`)**
- [R] **A truncated `defaults.json` loads as `{}` and is then overwritten on the same launch.** Rename a bad file aside, keep a `.bak`, and flush and fsync before `os.replace`.
- [R] **A file that parses but isn't a JSON object crashes every launch.**

**Audio and platform**
- [R] **Music buffers leak.** They are deleted while still attached to the source (`music.py` about 63-67); detach with `AL_BUFFER 0` first.
- [R] **`pygame.init()` also opens the SDL mixer.** Initialise only the display and font.
- [R] **No pause on focus loss, and no recovery when the audio device is lost.**
- [R] **There is no crash path.** Nothing writes a log file, there is no `sys.excepthook`, and a missing data folder, DLL or audio device fails silently for a blind player. Log to `%APPDATA%\SixthSense`, write `crash.txt`, and speak the error.

**Gameplay**
- [R] **`LVCount` should reset on every attempt once it reaches 3** (`stage_1_e.py` about 444-452; 0x3623a), so spawns come too fast.
- [R] **There is no spawn lull after action cell 9.** The original falls through to `monster_num = 9`, a 16 s pause (0x31e70-0x31f06).
- [R] **A new monster reads as bearing 0 (lane 5) for up to 1.5 s.** The original calls `MonsterMoving:` immediately (0x1194c).
- [R] **Melee is wrong.**
  - The original runs 0.1 s after the swing, with no headshot doubling.
  - It plays att2 on a non-lethal hit, att1 on a kill, and the whoosh only on a miss.
  - Port: `stage_1_e.py` about 639-645, 753-759.
- [R] **A grab can free or kill the wrong monster**, because the port removes monsters while looping over the list (about 530-545). The original defers removal (0x3b44e).
- [R] **Gunshots are 14 dB too quiet, and a kill sound is missing.** Guns fire at ReloadSoundGain 1.0, not 0.2 (0x2f488 and others), and kill sound 79 at 1.0 is missing (0x3a83a).
- [R] **Death plays the wrong sound.** It plays 354 "game over"; the original plays 84 `player_die` at z 40 (0x320ae), so the player hears "game over" twice.

**Menus and meta**
- [R] **The inventory lets you equip weapons you don't own** (`inventory.py` about 55-90, 178-188). The original gates on `itemN_have_flag`.
- [R] **Tutorial beats can finish out of order** (`stage_tutorial.py` about 169-211).
- [R] **Replaying the tutorial reads isTutorial=1 from the save.** The original forces it to 0 (0x7cfd8).
- [R] **The end of the tutorial starts a free walk through `tutorialEndGameStart:`**, which nothing in the binary calls. It should return to the menu.
- [R] **"Now Loading" (46) plays over the first tutorial prompt.** The original waits 2.8 s before `MapInitInBundle` (0x7d6a2, 0x2d45e).
- [R] **`app.mode` defaults to 0.** "Gold is lacking" is then silent, and the mode row says "voice over on" (`store.py` about 289-293, `main_controller.py` about 147-149).

## Low
- [R] **The SAPI fallback is dead.** It needs `comtypes`, which isn't installed. `accessible_output2`, which is installed, would cover NVDA, JAWS and SAPI.
- [R] **Closing the window doesn't quit.** It goes to the menu, and stacked screens and their coin timers are never torn down (`SixthSense.py` about 221-228).
- [R] **Several actions are silent or unconfirmed.**
  - R in the bindings screen resets everything without asking.
  - The weapon Try button is silent.
  - Shop screens open by saying only "back button".
  - Escape in a stage drops the run and the coin with no confirmation.
- [R] **Loading and path issues.**
  - A bad `--game` path silently falls back to `game/`.
  - The DLLs are only looked for under ROOT.
  - ALCboolean return values are typed `c_int`.
  - The device leaks if context creation fails.
- [R] **`setListenerPos_` calls `alListener3f`.** The original only stores the value (0xe9c8).
- [R] **Notes 122 and up are dropped without a log line.**
- [R] **Small binary mismatches.**
  - `MonsterKillCount_` should count kind 22 under `killMonster11count` (0x3a04c).
  - The `MONSTER_SOUNDS` rows should be full triples.
  - The range clamp is 20, not 0 (0x11032).
  - The original never resets the shake count.
  - HP is lost only when isTutorial is set (0x3b2e2).
  - Switching to the sword should play 329 (0x35ecc).
- [R] **Two save keys are never written.** Without `WEEKTIME` the weekly best never resets. Without `NOWRANK` the rank always reads 0.
- [R] **The zig-zag walks are faithful but can't be reached**, because the monster tables only use straight-lane types.
- [V] **Repo housekeeping.** There is no `requirements.txt`: pygame is needed, comtypes or accessible_output2 for speech, and capstone for `tools/`. (`New File.txt` at the root is the dev's private scratchpad, not a leftover. It was untracked and gitignored on 2026-09-21, so leave it alone.)

## Docs entries that are misreadings (fix with the code, docs last)
- **`DIVERGENCES.md`**
  - `checkBoosDie` "gameMode - 2".
  - The listener up vector and turning: the listener is never set.
  - "Starting bearings" and "bearing 0 until first footstep".
  - Gun gain "0.2f": guns use 1.0.
  - "isTutorial ... stands still": the original runs the tutorial inline. **Clarified 2026-09-21** — the entry now says this is unreachable in normal play, since `StartGameAction_` routes an unfinished save to the tutorial screen instead.
  - "The stop button skips the tutorial": only after beats One to Eight.
  - "Pausing works exactly once": `gameReplayAction_` sets bStop False.
  - The Input section says the arrow keys turn; the code uses comma and full stop.
  - "Nothing else in the port speaks": the menu and store do.
  - It lists the store among the rows that can't work.
- **`PORTING_STATUS.md`**
  - The 10-minute coin: it is 30. **Fixed 2026-09-21.**
  - "Half the shipped monster types walk" the zig-zags.
  - `MovingAccelerometer` is listed as if it were used.
- **`GAME_STRUCTURE.md`**
  - §3: the boss and level end.
  - §5: the pan table uses listener parameters the game never sets.
  - §9.
- **`tools/README.md`**: the addresses are VM addresses, not file offsets.

## Open decisions (the dev's call)
1. **Fidelity policy.**
   - The docs' rule is to reproduce every original bug: pausing works once, the result-panel double-tap off-by-one, the unreachable power saw, and the swipe gaps.
   - Claude's recommendation: fix what is hostile to players and record each fix as a divergence, so the docs still say what the original did.
2. **The offline coin economy.** The coin store, gifts and purchases can't exist offline. The choice is free play (no coin gating) or the faithful 30-minute recharge with the first-run grant and catch-up. **Settled 2026-09-21: the faithful recharge**, kept as a gate on Start Game rather than made free.
3. **Shaking free.** Keep 10 presses, or count a held Space key.
4. **The turn keys.** Remove them (faithful), or keep them as a documented divergence.
5. **Running the test suite.** Settled on 2026-09-21: ask first, and never build unless told. See [[feedback_dont_run_or_build]].

## Suggested fix order
1. Test isolation: a `SIXTHSENSE_USER_DIR` override, used by every test.
2. The `startSound` isPlaying branch (item 1), with a fake-AL test.
3. Todo bugs (a), (b) and (c). **(a) is done 2026-09-21; (b) and (c) are still open.**
4. The audio mix gains, stage teardown stopping the loops, and store speech.
5. The boss and level-end flow, and action cell 8.
6. The ammo exploits, the rebinding capture, rollover and stale held keys.
7. Run loop robustness, save robustness, and the crash log.
8. The docs corrections, last.
