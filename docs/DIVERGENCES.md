# Divergences from the original

The rule for this port is: reproduce what the binary does, including what looks like a
mistake, and write the mistake down here rather than fixing it. Anything listed as
"reproduced" is deliberate.

---

## Original behaviour kept as-is

### `Shotgun.plist` reload gain is 19.0
Index 17, "장전 소리 크기", is the string `"19"` where every other weapon has `"1.0"`.
`-[NSString floatValue]` returns 19.0, and `-[Stage_1_E GunReloadAction:]` passes it
straight to `AL_GAIN`. OpenAL clamps gain above 1.0 per source, so in practice the
shotgun reload is just loud. **Reproduced.**

### Gun "무기 소리 크기" is `"0.2f"`
Colt, Shotgun, M4A1, AK47 and MG80 all store the shot gain with a trailing `f`.
`floatValue` stops at the `f` and returns 0.2. **Reproduced** — `weapon_control.obj_float`
parses the same numeric prefix `floatValue` does.

### Melee attack gains and times are read with `intValue`
`-[WeaponControl loadWeaponForGun:fileType:]` reads indices 29, 31, 35, 37 … with
`intValue` and then widens to float (0x223f8 `intValue`, 0x22404 `vcvt.f32.s32`).
`Japanese.plist`'s "공격 1 소리 시간" of `"1.9"` therefore becomes **1.0**, and
`Knife.plist`'s `"1,0"` becomes 1.0 as well. **Reproduced.**

### The power saw is never loaded
`-[Stage_1_E weaponInit]` builds a nine-entry array ending in `powersaw` but its loop is
`cmp r4, 8` — eight iterations. `weaponSource[8]` does not exist (the ivar is
`[8@"WeaponControl"]`). The saw has a plist, a price, a shop button and sounds, and is
unreachable in play. **Reproduced.**

### `zombie_5_hit_player` has no WAV
`SoundList.plist` 162, 163 and 164 are `zombie_5_hit_player`; no such file is in the
bundle. `MonsterInit:` gives kind 5 sound **135** (`zombie_3_7_hit_player`) instead —
the original already worked around its own gap. **Reproduced**; nothing is missing at
runtime.

### The listener's up vector is not a unit vector
`-[oalPlayback setListenerRotation:]` passes `{cos, sin, 0, 0, 1, 1}` — "up" is
`(0, 1, 1)`. Combined with sources placed at `(x, z, y)`, the resulting OpenAL basis is
right `= +X`, up `= +Z`, forward `= +Y`, so the game's *y* axis is rendered as elevation
and the depth of every source is the constant `defaultZ`. **Reproduced exactly**; see
`docs/GAME_STRUCTURE.md` §5. Changing it would move every sound.

### Starting bearings do not match walking bearings
`initWithMonsterPatern:` places lanes 2 and 4 at 120° and 60°
(`(-500, 866)` / `(500, 866)`), while `MonsterMoving:` walks them at 123° and 57°. A
monster therefore jumps a couple of degrees on its first footstep. **Reproduced.**

### A monster reports bearing 0 until its first footstep
`MovingPosAngle` is only written in `MonsterMoving:`, so a monster that has just spawned
looks like it is in lane 5 to `monsterHitHeadFind`. It corrects itself within one
footstep interval. **Reproduced.**

### The swipe bands do not tile the circle
`-[Stage_1_E MovingShot:]` leaves 155.5..156.5 and 222.5..320.5 (242.5..320.5 for guns)
uncovered, and the final `else` sets `shotMonster = 3` — the same lane as 62.5..112.5.
So swiping backwards attacks straight ahead. **Reproduced.**

### `isTutorial` means "the tutorial is finished"
`TUTORIAL` is written as `"1"` by `-[Stage_1_E tutorialEnd:]`, and `Stage_1_E` only
creates its walk timer, and only spends ammunition, when the key is non-zero. A save
with `TUTORIAL` unset loads the stage and then stands still. **Reproduced** for
`Stage_1_E` itself — the port logs a warning saying so, and `--skip-tutorial` writes
the key the way the game does. In normal play this is now unreachable: see "Start Game
sends an unfinished save to the tutorial screen" below.

### `checkBoosDie` compares against `gameMode - 2`
`-[Stage_1_E checkBoosDie]` (0x3604c) decides whether the level may end. The name says
boss, but what it actually compares each live monster's `monsterNumber` against is
`gameMode - 2` (0x360c4, 0x360ec). In gameMode 3 that is 1, so a live kind-1 zombie
blocks the level; in gameMode 2 it is 0, which no monster is; in gameMode 1 it is -1.
`bBOSS` is declared on `Stage_1_E` and **never read or written anywhere in the
binary** — there is no boss check. **Reproduced.**

### `MonsterKillCount:` does not count kills
Despite the name, `-[Stage_1_E MonsterKillCount:]` (0x39e00) only bumps the per-kind
tally (`killMonster1count`..`killMonster11count`, `killMonster5000count`). Every call
site increments `killMonsterCount` itself first (0x39cee, 0x3a3ae, 0x3aad4).
**Reproduced** — the port does the same, rather than folding the two together.

### Pausing works exactly once
`bStop` is set by `-[Stage_1_E StopPlayAction:]` (0x33e48), `MissionSuccessTell`
(0x32c3a) and `missionFailTell:` (0x3278e), and **there is no store of 0 to it
anywhere in the binary**. `StopPlayAction:` returns early when it is already set
(0x33e40), so the stop button works once in the life of a stage; `continueAction:`
and `gameReplayAction:` both *require* it, so continue and restart keep working.
**Reproduced.**

### The stop button skips the tutorial
`StopPlayAction:` branches on `isTutorial` before anything else (0x33e30). While the
tutorial is still running, the stop button does not pause: it stops the tutorial's
sounds, writes `TUTORIAL = "1"`, sets `isTutorial`, kills both tutorial timers and
plays 327 *tutorial success* (0x33ea4..0x34086). **Reproduced** as
`Stage_1_E.tutorial_skip`.

### The result panel's double tap is off by one
`-[Stage_1_E tapCount]`'s jump table at 0x2ff32 is the eight bytes
`04 25 61 30 3b 4b 51 57`. Row 3 is labelled *headshot* and its case points at the
method's exit, so double-tapping it does nothing; row 4 is labelled *score* and its
case reads the **headshot** count. Selecting the rows is correct — each band of
`selectTapPointSoundStart` schedules the right reader — so the mistake only shows when
a row is tapped a second time. Rows 9 and 10, the rank and the top score, fall past
the `cmp r0, 7` and cannot be re-read at all. **Reproduced.**

### `missionFailTell:` plays *game over*, not *mission fail*
Sound 228 is `mission fail` and `StopElseSpeak` stops it, but nothing in `Stage_1_E`
ever plays it: the death panel plays 354 `game over` at gain 0.5 (0x32814).
**Reproduced.**

### Gold is twelve a kill and two a headshot, and the rest is dead code
`-[Stage_1_E ReadObtainedGold]` (0x3c3f4) builds the headshot multiplier string and
calls all twelve per-kind kill counters — and drops every one of those results, because
the next selector load clobbers `r0` before anything uses it. What reaches the label is
`add.w r3, sl, sl, lsl #1` / `lsls r6, r6, #1` / `add.w r4, r6, r3, lsl #2` at 0x31616:
`12 * killMonsterCount + 2 * HeadShotCount`. **Reproduced** — the port computes the
twelve-and-two and does not pretend the rest matters.

### The gold shop cannot be reached
`mainStoreController` has a `glodShopAction:`, a jump-table case for it and a WAV that
says *Gold shop Button* (236) — but `selectMenu` is never set to 3 anywhere in the
class, so no band of `selectTapPointSoundStart` ever selects it. Same shape as
`MainController`'s unreachable Exit. **Reproduced**: the row is not offered, and the
action is still there.

### The shop and the inventory disagree about the same weapons
`-[DetailStoreController viewDidLoad]` and `-[DetailInventoryController viewDidLoad]`
each hard-code their own numbers, and they do not match:

| | shop | inventory |
|---|---|---|
| Shotgun price | 7000 | 50000 |
| Shotgun capacity | 10 | 9 |
| MG80 price | 45000 | 10000 |
| Japanese sword price | 50000 | 150000 |
| Japanese sword damage | 100 | 80 |

The shop's are the ones `buyAction:` charges; the inventory's are a spec sheet.
**Both reproduced as they stand.**

### The story is in the game and cannot be heard
`intro2storyPage` is a complete screen — nib name, rows, skip button — and **nothing in
the binary ever creates one**. The story it would have shown lives in
`-[startIntroPage shakeDevice]` (0x17178), which nothing in `startIntroPage` calls
either; `skipAction` only cancels it. So sound 15 *As the ozone* and the paragraph at
0x171e4 never play. **Reproduced**: `intro.py` carries `shakeDevice` and the text, and
nothing calls it.

### Three filter classes nothing can use
`AccelerometerFilter`, `LowpassFilter` and `HighpassFilter` are Apple's
`AccelerometerGraph` sample code, compiled in and never referenced: none of the three
appears in `__objc_classrefs`, so nothing can even allocate one. `MovingAccelerometer`
does its own filtering. **Not ported.**

### `-[oalPlayback stopSoundArea:]` does nothing
It walks the array, reads `intValue` off each entry and discards it (0xe466..0xe482).
Nothing calls it. **Not ported.**

---

## Where the port necessarily differs

### Input
There is no touchscreen and no accelerometer, and the port is keyboard-only — no
mouse. The pan gesture becomes the keys **A Q W E D**, laid out as the arc the five
lanes occupy: A hard left, W straight ahead, D hard right. They hand the stage a band
directly instead of a synthesised angle, which loses nothing, because
`-[Stage_1_E MovingShot:]` quantises its angle into exactly those five bands before
anything else looks at it. Reload is **S**. Tilt-to-turn becomes the arrow keys, one
10° step per press — the same step `rotationLeftEight`/`rotationRightEight` take.
Shaking free becomes the space bar, and still needs 10 presses, the count
`-[Stage_1_E accelerometer:didAccelerate:]` uses. See `sixthsense/ui/input.py`.

### The menu is a list, not a screen to explore
`-[MainController selectTapPointSoundStart]` maps the *Y coordinate* of a touch to one
of eight rows, reads that row's name, and `tapCount` runs it on a double tap. A keyboard
has no finger, so Up and Down walk the same eight rows in the same order, reading them
with the same WAVs, and Enter is the double tap. The row set, the order and the sounds
are the original's.

Three rows cannot work: ranking, store and Game Center all need the publisher's server
or in-app purchases. The port keeps the rows — removing them would change the menu —
plays the `ui_select` the original plays, and then says, through the speech layer, that
the row is not available. That is the one place outside the binding screen where the
port speaks; the alternative was a row that silently does nothing, which is worse for a
player who cannot see it.

`exit_flag`, `-[MainController Exit:]` and `exitButton` all exist, but no row in
`selectTapPointSoundStart` claims Exit and nothing plays sound 20 (`Exit button`) — so
it is unreachable from the blind menu in the original too. **Reproduced**: there is no
Exit row, and Escape quits.

`-[MainController useHeadPhone]` asks `AVAudioSession` which route is live and only then
plays `you must use earphone`. Windows has no equivalent worth trusting, so the port
always plays it.

### The shop, the inventory and the panels are lists, not screens to explore
Every blind-mode screen in the game works the same way: a finger dragged down the
screen reads whichever row it is over, and a double tap runs it. A keyboard has no
finger, so Up and Down walk the same rows in the same order, reading them with the same
WAVs, and Enter is the double tap. That is how the main menu was ported and it is how
the pause and result panel (`Stage_1_E.pause_select`), the shop (`game/store.py`) and
the inventory (`game/inventory.py`) are ported too. The row sets, their order and
their sounds are the original's.

`P` pauses. The original's stop button is a button on the screen, and there is no
screen here; `-[Stage_1_E StopPlayAction:]` needed a key of its own.

### Start Game sends an unfinished save to the tutorial screen
`-[MainController StartGameAction:]` (0xb2ed) always spends a coin and pushes
`Stage_1_E`; the tutorial itself runs inline inside that same screen's own
`MapInitInBundle` (0x2e08e-0x2e0dc) when `TUTORIAL` is unset, and no coin is spent
either way because the coin is only ever charged once, by `StartGameAction:`, before
`MapInitInBundle` knows whether it is about to walk or teach. The port keeps the
tutorial as a separate screen (`Stage_Tutorial`, see below), so `StartGameAction_`
checks `TUTORIAL` itself: while it is unset it goes straight to the tutorial screen
and never touches `Coin`, matching the original in the one thing a player can
notice - no coin lost, no silent standing still - without folding the tutorial into
`Stage_1_E`.

### Key bindings are a port addition
The original has no key bindings at all — every action is a swipe, a tap or a shake.
The port binds those actions to keys (`platform/keymap.py`), lets the player change
them from the screen F1 opens (`ui/keybind_screen.py`), and keeps them in
`%APPDATA%\SixthSense\keys.json`.

The defaults are not arbitrary: the tutorial teaches the lanes as clock positions, so
the arrows are laid out as a clock — Left is 9 o'clock, Left+Up is 10:30, Up is 12,
Right+Up is 1:30, Right is 3, Down is 6, which is the reload sector. A Q W E D S stay
bound alongside. Turning moved to comma and full stop because Left and Right became
lanes.

Bindings may be chords, resolved with a 60 ms window (`CHORD_WINDOW`) so that Left
alone and Left+Up can both mean something. 60 ms is far below anything this game reacts
to — a tick is a second and the shortest weapon cooldown is 0.3 s. `Shift+Tab` was
already a chord and goes through the same path.

F1 and Escape cannot be rebound, or a player could lock themselves out of both the game
and the screen that would let them fix it.

### The binding screen speaks, the game does not
The game is self-voicing from 269 recorded WAVs, which `SoundList.plist` names by number
in 371 entries, and none of them can say a key name —
the only letters or digits in the bundle are `zero`..`nine`, for the number reader. So
the binding screen alone uses a synthesiser (`platform/speech.py`): NVDA through its
controller client when NVDA is running, SAPI 5 otherwise, silence if neither is there.
Nothing else in the port speaks.

### Audio device
iOS OpenAL becomes OpenAL Soft (`vendor/openal/soft_oal.dll`). The AL calls, enums and
values are unchanged. `AVAudioPlayer` becomes a source-relative OpenAL source rather
than a second audio API, which for the stereo music and ambience files is the same
signal: gain only, no panning.

**HRTF is explicitly disabled** (`ALC_HRTF_SOFT = ALC_FALSE` in `AL.open`). The
original had no binaural rendering of any kind: it imports only core AL/ALC, touches
none of Apple's `ALC_ASA_*` spatial extensions, and iOS's OpenAL renders core AL as
distance attenuation plus amplitude panning. Leaving OpenAL Soft's default
(`ALC_DONT_CARE_SOFT`) would let HRTF engage on headphones and put the game somewhere
it never was. `tools/pan_check.py` measures what the five lanes render to; the table
is in `GAME_STRUCTURE.md` §5.

### The sounds are organized into folders
The original bundle keeps its 269 WAVs in one flat folder, next to the plists and the
map. The port keeps every sound the game uses in `game/sounds/used/`, sorted by what it
is (the paths below are inside that folder):

* `sfx/zombies/normal/normalcave1`..`12` and `normalforest1`..`12`: each kind of zombie's
  coming loop, damage, death and hit-player sounds.
* `sfx/zombies/bosses/bosscave1`..`3` and `bossforest1`..`3`.
* `sfx/characters/charcave1`, `charcave2`, `charforest1` and `charforest2`: the man and
  the woman who heal you.
* `sfx/monsters/monstercave` and `monsterforest`: the woman-like monster.
* `sfx/weapons`: firing, reloading, the empty click and the hits.
* `sfx/misc`: music, ambience, rain, breathing and the interface sounds.
* `speech/game`, `speech/logos`, `speech/menus/main`, `speech/menus/store`,
  `speech/numbers`, `speech/tutorials` and `speech/weapons`.

**Every file keeps its original name**, for example
`sfx/zombies/normal/normalcave1/zombie_1_coming_cave.wav`. The binary asks for a sound
by number, `SoundList.plist` turns the number into a file name, and that name is
unchanged, so the right file is still found. Each file was named by comparing its audio
with the original's waveform, not by guessing from names. Where the original reuses
one recording in several places, such as the boss death or the empty-magazine click,
each folder that uses it has its own copy.

The files went through an OGG round trip on the way and were converted back to 16-bit
PCM, the originals' format, at the same sample rates and channel counts. They carry
faint codec noise; otherwise the audio is the original's. Six originals were missing
from that set: `Game Start Button`, `Welcome to`, `game center button10`,
`restore button`, `weapon_m4_fire` and `weapon_saw_start`. They are the original files
themselves, copied in unchanged, so all 269 of the original's sounds are present.
`game/sounds/used/` holds 329 files in all: the 269 sounds, plus 60 copies of the ones
more than one folder shares.

`game/sounds/unused/` holds 25 files that are not the original's own, laid out in the
same sub-folders they came from. Eleven are extra copies of a sound already in its
folder: one more `ui_select` in `sfx/misc`, and five more each of `gun_att_sound_1`
(the `*hit` files) and `weapon_nonbullets` (the `*empty` files) in `sfx/weapons`. The
other fourteen never came from the original: the eight character `hurt` sounds,
`grenadereload`, `yes`, `no`, `question`, `GameStart` (an edited cut of
`Game Start Button`) and `welcome`. Nothing in the port uses them, so the sound lookup
never looks in `game/sounds/unused/`.

How the port finds them: `paths.path_for_resource`, which stands in for
`-[NSBundle pathForResource:ofType:]`, looks in the bundle's top folder first, the only
place the original ever looked, and then by file name anywhere under
`game/sounds/used/`. File names are matched without regard to case, as Windows matches
them. Where a sound has copies in several folders, the first in sorted order is taken,
and every copy is the same recording. Because the top folder comes first, the plists and
the map are found exactly as before, and `--game` pointed at an untouched original bundle,
with its WAVs all in its top folder, still works. `compiler.py` copies
`game/sounds/used/` into a build with its folders, and leaves `game/sounds/unused/` out.

### The tutorial is a table, not ten copies
The original spells each beat out as five methods — `tutorialOne`, `tutorialOneSoundStop`,
`tutorialOneEnd`, `tutorialOneRestart`, `tutorialOneRestartFinger` — ten times over, with
only the sound number, the arrow to show and the monster to spawn differing. The port
drives them from one table (`stage_tutorial.BEATS`). The behaviour, the timings (9.5 s
per prompt, 6.5 for beat eight) and the spawns are the original's.

### Timers
`NSTimer` and `performSelector:withObject:afterDelay:` become one cooperative queue
(`sixthsense/platform/runloop.py`) drained by the main loop. Ordering, cancellation by
`(target, selector)` and the "skip missed fires" behaviour of a repeating `NSTimer` are
preserved; there is no separate run-loop mode.

### `NSUserDefaults`
A JSON file in `%APPDATA%\SixthSense\defaults.json`, same keys.

### `arc4random()`
Python's `random.getrandbits(32)`. The moduli and offsets are the original's, so the
spawn distribution is the same; the sequence is not.

### UIKit
There are no view controllers, nibs, labels or image views. The port draws a plain text
panel showing what the HUD showed. Every method whose entire body was UIKit
(`HPImageCount`, `scratch1Pos`..`scratch5Pos`, `lodingBar01`..`04`, `buttonSelectImage`)
is present as a stub so the call sites stay honest.

### Server features
The map download, ranking, friends, score upload, in-app purchases, Game Center and the
Facebook SDK are not ported. The map download in particular points at a Dropbox URL that
stopped resolving years ago; `MapInitInBundle` is the path that works and is what the
port uses.
