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

### Gun "무기 소리 크기" is `"0.2f"`, and nothing reads it
Colt, Shotgun, M4A1, AK47 and MG80 all store the shot gain with a trailing `f`.
`floatValue` stops at the `f` and returns 0.2. **Reproduced** — `weapon_control.obj_float`
parses the same numeric prefix `floatValue` does.

It is never used, though: `-[Stage_1_E MovingShot:]` plays the shot at the weapon's
*reload* gain, reading `ReloadSoundGain` at 0x2f248, 0x2f484, 0x2f664, 0x2f7e2, 0x2f930
and 0x2fba6, and never reads `ShotSoundgain` anywhere. That is 1.0 for every gun, and
19.0 on the shotgun, which OpenAL clamps. The port passed the 0.2 for a while, which left
every gunshot 14 dB down; it now passes what the binary passes.

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

### A new monster takes its first footstep at once
`-[MonsterControl MonsterComing:]` opens with `performSelector:@selector(MonsterMoving:)`
(0x1194c), so a monster is on its lane from the moment it appears. An earlier version of
this file said it read as bearing 0, lane 5, until its first timed footstep; that was a
misreading, and the port now takes the step the way the original does.

### A zombie stops 20 cm out, not on top of you
Once a monster is within 25 cm, `MonsterMoving:` sets its range to 20.0 (0x11032:
`movs r2, #0` / `movt r2, #0x41a0`), not 0, so it stays in its own lane at the end.
**Reproduced**, except that the step before it no longer overshoots: see "A monster's
last step stops at 20 cm" below.

### The walk sample is moved, not restarted
`-[oalPlayback startSound:Postion:soundGain:]` (0xe524) tests the source's `isPlaying`
(0xe560). While the walk sample plays, each footstep only moves it to `(x, 40, y)` and
sets its gain; only a stopped source is started. The port used to restart it every step
at the spot the zombie came in, so you could not hear a zombie come closer. The rebind of
`AL_BUFFER` that follows (0xe59c..0xe5c0) is refused by OpenAL on a playing source, so
the port leaves it out. **Reproduced.**

### The player breathes once every four seconds
`MainControl` tries to breathe on every second one-second tick, and `breath:`, which
lets it breathe again, comes 3.0 s later (0x31964: `movt r5, #0x4008`). So every
other try is skipped, and the breath that tells you your health (80 at three hearts, 81
at two, 82 at one) comes once every four seconds. The port used 1.0 s, which breathed
twice as often. **Reproduced.**

### A shot lands half a second after it is fired
`MovingShot:` schedules `MonsterDamage` 0.5 s after the shot, for every gun (0x2fd70)
and the grenade (0x2f32a): `movt r1, #0x3fe0`. No weapon's plist changes it, and
`ShotSpeed` is never read. Whether it is a headshot is decided at the trigger, by the
breathing gap at that moment (0x2fc0e..0x2fc48 sets `isHeadShot`), and applied when the
hit lands. The port used to land every shot at once. **Reproduced**, and kept at
tsatria03's and tunmi13productions' decision on 2026-09-22. `stage_1_e.SHOT_TRAVEL` is
still the one setting, and 0.0 would bring the instant hits back.

The mark is put on the monster aimed at when you fire, and taken off by the hit that
uses it. If a different monster is nearest in that lane when the shot lands, that one
takes a plain hit and the first keeps its mark, so its next gun hit counts as a
headshot whenever it comes. **Reproduced.**

The windows themselves match the original: one window `headShotTimeStart` seconds into
each walk cycle, or, for a list like `"0.3,1.3"`, each time in the list, every cycle
(`headShot:` sets `headShotTimer` back to nil as it fires, 0x11b74, so `MonsterComing:`
starts the list again, 0x11a2e), each open for `headShotTimeEndHowLong`.

### Reloading keeps you from firing
The reload is the 6 o'clock swipe, so it passes `MovingShot:`'s guards: not while a shot
or reload is still going, not while held, not while attacks are barred, not once the
game-over music has started. `shotFlag` then stays up until `reloadGun:` drops it
(0x35f24), so nothing can be fired with the magazine out, and `reloadGun:` refills the
weapon the reload began with (`reloadWeaponNumber`, 0x35f2a). The grenade is not
reloaded (0x351c8). The port's reload key called `GunReloadAction:` directly, past all
of that. **Reproduced**; the key now does nothing with the grenade or a blade.

### The zig-zag walks cannot be reached
Types whose id ends in 6 to 0 walk the zig-zags (`MovingType` 11..55), but
`monsterArray` only holds ids ending in 1 to 5, and the scripted spawns are straight
walkers too. The walks are ported and their sound sweeps, but no zombie in play uses
them. **Reproduced.**

### Losing the window's focus is pressing P
In the original, `applicationDidEnterBackground:` posts `InterruptON` (0x4d90), and the
stage and the tutorial answer it with `interruptStop`, which calls `StopPlayAction:`
(0x2c6ce, 0x84962), the stop button. The port does the same when the window loses focus
(`ui/focus.py`), calling what P calls: the pause panel in a stage, every time, and in the
tutorial whatever P does there. The menus ignore it, as nothing else
observed the notification. Coming back resumes nothing; the panel waits for Continue.
`InterruptOff`'s rebuild of the audio device (`audioRestart`, 0x2c5bc) is not ported
yet. **Reproduced.**

### Shaking free takes 1 to 5 presses, drawn for each grab
The original takes ten shakes of the phone, and the only two methods that reset
`shakeCount`, `checkShakeMode` (0x323d8) and `shakeCheck:` (0x324f8), have no selector
reference, so nothing calls them. After the first escape in a stage the count stayed at
ten or more, and every later grab broke on a single shake. This was reproduced until
2026-09-23, when the dev decided that each grab should need a random 1 to 5 separate
presses of the shake key (`SHAKES_MAX` in `stage_1_e.py`), with the count reset at every
grab (`Stage_1_E._grabbed_by`). Holding the key down counts as one press
(`Input.handle`).

### Kind 11 hits you with kind 12's sound
`MonsterInit:` gives kind 11 the hit-player sounds 307..309, which are
`zombies_12_hit_player`; 298..300, `zombies_11_hit_player`, are never listed.
**Reproduced.**

### `ChangeLevel:` loops the other level's ambience
Going into the forest, `ChangeLevel:` plays note 88, `bgm_cave_amb`, looping at 0.02
(0x32362); going into the cave, 87, `bgm_forest_amb`. The new level's own ambience is
already on the ambience player by then, at 0.3. **Reproduced**, and stopped when the
stage is left.

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

### The boss holds the end of each level
At row 29 `MainControl` sounds the alarm (285); at row 23 it sends the boss down the
middle lane, type 5008 in the forest and the rain (0x31d1c) or 5003 in the cave
(0x31e0a), and stops the alarm (0x31e2e). The player stops at row 22, and
`-[Stage_1_E checkBoosDie]` (0x3604c) holds the level while a monster with
`monsterNumber` 5001 (0x360d4) or 5000 (0x360e8) is alive, those being the two bosses.
Once it is dead, every zombie left is killed and counted, the ambience changes, and
`ChangeLevel:` follows two seconds later. **Reproduced.** This file used to say the check
compared against `gameMode - 2` and that there was no boss; that was a misreading of the
`movw` constants. `bBOSS` is declared and never used.

### `MonsterKillCount:` does not count kills
Despite the name, `-[Stage_1_E MonsterKillCount:]` (0x39e00) only bumps the per-kind
tally (`killMonster1count`..`killMonster11count`, `killMonster5000count`). Every call
site increments `killMonsterCount` itself first (0x39cee, 0x3a3ae, 0x3aad4).
**Reproduced** — the port does the same, rather than folding the two together.

The chain tallies `monsterNumber` 1 to 10, then 22, the woman zombie, under
`killMonster11count` (0x3a04c), then the two bosses under `killMonster5000count`. Kind
11 and 12 zombies are counted as kills but never tallied, so they add nothing to the
score. The girl who heals you is not a kill at all: killing her costs a heart once the
tutorial is behind you (0x3a850..0x3a97a). **Reproduced.**

### Pausing works as often as you like
`bStop` is set by `-[Stage_1_E StopPlayAction:]` (0x33e48), `MissionSuccessTell`
(0x32c3a) and `missionFailTell:` (0x3278e), and `StopPlayAction:` returns early while it
is set (0x33e40). `continueAction:` and `gameReplayAction:` both require it, and both
clear it straight away: `cmp r1, #0 / itt ne / movne r1, #0 / strbne` at 0x3395a..0x33960
and 0x33106..0x3310c. **Reproduced.** This file used to say `bStop` was never cleared,
so that the stop button worked once per stage. The listings drop those conditional
stores, so that was a misreading, and the port copied it: after one pause, P did
nothing for the rest of the stage. tsatria03 found it in play on 2026-09-22.

### The stop button skips the tutorial
`StopPlayAction:` branches on `isTutorial` before anything else (0x33e30). While the
tutorial is still running, the stop button does not pause: it stops the tutorial's
sounds, writes `TUTORIAL = "1"`, sets `isTutorial`, kills both tutorial timers and
plays 327 *tutorial success* (0x33ea4..0x34086). But only once beats One to Eight are
all done: the branch loads `tutorialOne`..`tutorialEight`, ANDs them together
(0x33f1e, 0x33f22) and returns doing nothing when any is still clear (`beq` at
0x33f30). `Stage_Tutorial` does the same (0x83926..0x8393c). The stop button is the
three-finger double tap, so this is beat Nine: doing it ends the tutorial. 3.05 s later
`tutorialEnd:` runs. From the Tutorial row, `-[Stage_Tutorial tutorialEnd:]` (0x83738) is
`GameEndAction:`, back to the menu. On a first Start, `-[Stage_1_E tutorialEnd:]`
(0x33bec) reads 3, 2, 1 (`TTSNumber:321 type:1`) and 6.0 s later
`tutorialEndGameStart:` plays *zombies are coming* and starts the walk.
**Reproduced** since 2026-09-23 in `Stage_Tutorial.tutorial_skip` and `tutorialEnd_`,
with P as the stop button. Before that the port let P skip at any beat and then left you
standing there, finished beat Nine on Shift+Tab, and started the game after every
tutorial. One difference: the original sets `isTutorial` as it ends, so a second stop
during the 3.05 s wait would run the ordinary pause; the port ignores P until the menu
or the game comes (`Stage_Tutorial.ending`).

### The result panel's double tap is off by one
`-[Stage_1_E tapCount]`'s jump table at 0x2ff32 is the eight bytes
`04 25 61 30 3b 4b 51 57`. Row 3 is labelled *headshot* and its case points at the
method's exit, so double-tapping it does nothing; row 4 is labelled *score* and its
case reads the **headshot** count. Selecting the rows is correct — each band of
`selectTapPointSoundStart` schedules the right reader — so the mistake only shows when
a row is tapped a second time. Row 10, the top score, falls past the `cmp r0, 7` and
cannot be re-read at all, and so did row 9, the rank, which the port now leaves out.
**Reproduced.**

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

## Where the port differs on purpose

### Shots and swings are heard down their lane
The original plays every gunshot from `(0, 0)` at z 40, dead centre (0x2f248 and its
copies), and a melee miss the same way (0x39c3c). The port places them 40 cm out along
the lane they are aimed down, at the listener's height. That pans a shot the way a
zombie in the same lane pans, and 40 cm is the reference distance, so it is exactly as
loud as before. The grenade and the reload stay in the centre.

### The bullet striking a zombie is heard where the zombie is
`gun_att_sound_1` (56) is a stereo file, and OpenAL never places stereo sounds, so the
original played it in the middle of your head even though it passes the zombie's
position. `oal_playback.MONO_AT_LOAD` folds it to mono as it loads; the file is not
changed. The headshot announcement, `headshot_4` (330), is stereo too and is left that
way: it is meant to be heard in the centre, at 0.1, wherever the zombie is, and it is.

### Shaking free is heard where you are
`shakingFind` plays the animal zombie's push at the monster's `Pos` (0x3baa0). By then
it is on top of you and the push is your own doing, so the port plays it at the
player, the way a kill of your own is heard, rather than out in the lane.

### Two zombies reaching you at once
`MonsterAttPlayer` collects the monsters it is done with and removes them after the loop
(0x3b44e), but when one of them grabs you it returns straight away and drops that list,
so a zombie that hit you on the same tick stayed on top of you and hit again once you
were free. The port removes them either way. It also keeps the grabbing monster itself
rather than only its index, so shaking free always frees and kills the one holding you.

### The woman zombie's growl after a pause
The woman zombie (types 10006..10010) walks on `woman_coming_cave_monster1` (271) or `woman_coming_forest_Monster` (272): about four seconds of quiet footsteps, then the growl. Her plists give 16 steps of 50 cm every 6 s (`comingSoundInWalk`, `comingRange`). She keeps that speed on every level: `MonsterInit:` builds her, and the girl who heals you, with an HPGain of 1.0 (0x38d8c, 0x39034: `mov.w r2, #0x3f800000` stored as the argument), where every other monster gets `monsterHPGain`. So a new woman starts at the top of her sample, as in the original, and growls 4.5 m out in the cave and 3.5 m in the forest.

After a pause, `ReplayGame` starts her sample again from the top wherever she is (0x10d98), so the original could let her reach you before the growl, and `hitPlayer` stops her sound, so she hit you unheard. The port starts the sample far enough in that the growl lands as she comes within 3.5 m (`monster_control.GROWL_AT`), worked out from where she is. The files are unchanged.

The port used to build the girl and the woman with the level's `monsterHPGain`, so they got 1.5 times faster and tougher each level. That was a misreading, found on 2026-09-22, and the growl timing above was first written to make up for it.

### A monster's last step stops at 20 cm
`MonsterMoving:` takes `comingRange` off the range while it is over 25 cm (0x10fee) and
sets it to 20 cm once it is not (0x11032), but nothing stops that step overshooting.
The girl's 50 cm step took her from 50 cm to 0, dead centre, and the next step put her
back out at 20 cm in her lane, so she walked in and then stepped to the side, right
from lanes 4 and 5, left from 1 and 2. Any monster whose step overshoots does the
same, and a zombie's step grows 1.5 times each level, so it can overshoot past you and
onto the other side; `zombie_1` also lands on 0 on level 1. The original does it too. The port stops
a step at 20 cm, where the monster ends up anyway, so it stays in its lane all the way
in. Every step that would have overshot already landed within 25 cm, so a monster
reaches you on the same step as before.

### The weapon test range
`Stage_1_TEST`, which the Try button on a weapon's page opens, is ported in `game/stage_1_test.py`, with these differences:
- `-[DetailStoreController testAction:]` refuses while VoiceOver is running and shows an alert asking for it to be turned off (0x1c20a). The port leaves that out: a player here always has a screen reader running, and the range speaks for itself.
- `gameReplayAction:` fetches the ground map from the developer's Dropbox (0x471fe..0x47292) and builds the level when it arrives. The port reads the bundled map, as the first start does.
- `missionFailTell:` writes `GOLD` without a `synchronize` (0x467ee). iOS saves it soon after anyway; the port saves it at once.
- The range's pause checks and sets `bStop` before it looks at `missionCompletSounding` (0x479d6..0x479ee), the reverse of the stage's; the port keeps that order.
- The range's own `monsterHitHeadFind`, `MonsterDamage`, `MonsterDamageKnife`, `MovingShot:` and the reloads differ from the stage's only in the inline tutorial's flags and in which weapon a reload refills (there is only one), so the port uses the stage's.

Kept as the original has them: a win plays `bgm_game_complete` (90) and then says "game over" (354) when the panel comes up, the range is always the cave or the forest, never the rain (0x40fce: `arc4random() & 1`), and the gold for a run is 12% of the score, not the stage's twelve a kill.

### A debug mode
The original has none. `python SixthSense.py --debug` sets `AppDelegate.debug`, and the stage then keeps every heart, so you cannot die. A zombie that reaches you, or a grab you do not shake off, plays the zombie's death (`DieMonster`) and nothing else: no hit on you and no `player_damage`. Shooting the girl who heals you sounds as usual but takes nothing. The girl still reaches you and thanks you, but gives no heart. Nothing you kill counts either, so `killMonsterCount`, `HeadShotCount` and the per-kind tallies stay at 0, and with them the score, the gold (`ObtainedGold`) and the top score. The tutorial still sees each kill, through `Stage_1_E._kill_seen`, so its first five lessons finish as usual. A headshot still does double damage and is still heard. A coin is still spent to start a run. The window's title says "SixthSense (debug)", and each stage says "Debug mode" through the screen reader as it starts. Tab and Shift+Tab go through all eight weapons, bought and equipped or not, and nothing runs out: no shot takes a round from the magazine, and the grenade can be thrown with none in `GRENADECOUNT` and takes none from it.

It also adds seven keymap actions, which only match, and only show on the F1 screen, with `--debug` (`KeyMap.debug`). They live in `sixthsense/game/debug.py`, speak through the screen reader whatever the voice over row says, and do nothing in the tutorial:
- In the weapon test range, F2 and Shift+F2 only say that it has no levels or sections.
- Shift+F2 goes to the next level, the way the end of a level does (`_level_transition`), boss or no boss. After level 8 it goes round to level 1, with level 1's zombies (`debug.MAX_LEVEL`). While a level is changing it says "Not while the level is changing". F2 says "Not while the section is changing" then too, and for 2 s after each jump (`debug.SECTION_SECONDS`, as long as a level change takes), so it cannot skip through the sections at once.
- F2 goes to the start of the next section of the corridor in the same level: the next row on your path whose action cell is 9, of the eight at rows 680, 601, 500, 400, 300, 200, 99 and 34, the last being the boss's. The zombies around you die, but not the girl who heals you, and the next tick reads that cell 9 as walking there would.
- F5 spawns a zombie in the lane you last attacked, 12 o'clock before your first attack. Shift+F5 chooses which: zombies 1 to 10, the woman zombie, the girl or the boss, which always comes down the middle.
- F6 holds every zombie where it is, and any that appear while it is on. They keep breathing and their headshot windows keep coming, but `MonsterMoving:` leaves their range and gain alone (`MonsterControl.frozen`). F6 again lets them walk.
- F7 lets a zombie that reaches you, or a grab that lands, hit you as in a normal game, with its hit sound and `player_damage`, but still without taking a heart (`Stage_1_E.debugHits`). F7 again goes back to them dying on you.
- F11 says each zombie's kind, lane and distance, nearest first, and whether its head is open.

## Where the port necessarily differs

### Input
There is no touchscreen and no accelerometer, and the port is keyboard-only — no
mouse. The pan gesture becomes the keys **A Q W E D**, laid out as the arc the five
lanes occupy: A hard left, W straight ahead, D hard right. The arrow keys do the same
as a clock face: Left, Left+Up, Up, Right+Up and Right. They hand the stage a band
directly instead of a synthesised angle, which loses nothing, because
`-[Stage_1_E MovingShot:]` quantises its angle into exactly those five bands before
anything else looks at it. Reload is **S** or Down. There is no turning: the original
never turns the listener at all (`setListenerRotation:` is not in `__objc_selrefs`, and
nothing creates a `MovingAccelerometer`), so the comma and full stop turn keys the port
once had were its own, and were removed on 2026-09-23. The port still sets the listener
once, facing 0, as a stage starts, because that orientation is what puts the lanes on
the right sides.
Shaking free becomes the space bar, and still needs 10 presses, the count
`-[Stage_1_E accelerometer:didAccelerate:]` uses. See `sixthsense/ui/input.py`.

### The menu is a list, not a screen to explore
`-[MainController selectTapPointSoundStart]` maps the *Y coordinate* of a touch to one
of eight rows, reads that row's name, and `tapCount` runs it on a double tap. A keyboard
has no finger, so Up and Down walk the rows in the same order, reading them with the
same WAVs, and Enter is the double tap. The order and the sounds are the original's.

Two rows are left out: ranking (row 5) and Game Center (row 8). Both opened online
services, the publisher's ranking server and Apple's Game Center, that the Windows port
does not have. The port used to keep them and say they were not available; the devs
decided on 2026-09-23 to remove them everywhere. So the menu has six rows, which keep
their original numbers, and Up and Down skip the gaps. The result panel's rank (row 9)
went with them, for the same reason.

The coin row reads the count, then "after", then the minutes and the seconds to the
next coin, each queued behind the last. `-[AppDelegate readStop]` (0x5ae8), which every
move between rows calls, stops only the digits, so moving away after "after" still had
the minutes and seconds read over the next row. The port's `readStop` also cancels the
queued minutes and seconds and stops the words already playing.

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
their sounds are the original's, except that the shop leaves out restore purchases
(row 6 of `mainStoreController`, `restoreAction:` 0x1eb78), which restored Apple
in-app purchases that no longer exist, and the result panel leaves out the rank.

`P` pauses. The original's stop button is a button on the screen, and there is no
screen here; `-[Stage_1_E StopPlayAction:]` needed a key of its own.

### The first Start runs the tutorial in its own screen
`-[MainController StartGameAction:]` (0xb2ed) never reads `TUTORIAL`: it always spends
a coin and pushes `Stage_1_E`, and that screen's `MapInitInBundle` (0x2e08e-0x2e0dc)
runs the tutorial inline while `TUTORIAL` is unset. The port runs that tutorial in
`Stage_Tutorial`, marked `first_run`, so it ends the way `Stage_1_E`'s does: the 3, 2, 1
and the real game. The coin is spent as in the original (2026-09-23). Before that the
port sent an unfinished save to the tutorial without spending one.

### Now Loading blocks, and the earphone warning moved to the intro
Two port additions, decided 2026-09-22 after they were heard colliding in play.

`-[Stage_1_E viewDidLoad]` plays *Now Loading* (46) as its very first act, before
`BGMusicStop` or anything else here touches audio. `BGMusicStop` itself moved into
`MapInitInBundle`, which `LOADING_SECONDS` (2.8 s, `stage_1_e.LOADING_SECONDS`)
already holds back - so the menu music keeps playing under *Now Loading* instead of
cutting to silence before the player hears it, and only stops once the level (or the
tutorial's first beat) is ready to take over. Nothing in the binary ties these two
sounds together; this is purely about not leaving dead air or an abrupt cut in a game
with no picture to fall back on.

*You must use earphone* (234) only ever plays from `MainController StartGameAction:`
in the original (`useHeadPhone`, 0xaa3d, gated on a headphone check Windows cannot
make). Playing it there in the port meant repeating the same four-second recording
every single time a game was started. It now plays once, from `StartIntroPage`, timed
to start after the welcome message (`WELCOME_SECONDS`, measured from the WAV) - and
skipping the intro (`skipAction`) cancels or stops it, the same way skipping cuts off
the welcome message itself, so a player who skips never hears it at all.

### The menu has music, and the volumes have knobs
`bgm_main_menu` under the main menu is a port addition: the original's `MainController`
never starts music, and the only call to `-[AppDelegate BGMusicStart]` in the binary is
`-[Stage_1_E GameEndAction:]` (0x330da), on the way back from a finished run. Since the
gain is not the binary's, it is the port's to pick. It started at 1.0, which talked over
the rows the menu reads aloud, and now plays at `volume.MENU_MUSIC_DB`, −14 dB, chosen by
ear in 2026-09-22 play-testing — the same loudness the rows themselves are read at.

`sixthsense/platform/volume.py` is the rest of that addition: a set of knobs, in decibels,
that move whole groups of sounds. Every gain the game actually plays is still the
binary's, written where it is used with the address it came from — the level music 0.02
(0x321d4), the ambience 0.2 (0x2ddfa), the rain 0.5 (0x2ddc8), a gunshot 1.0 — and the
knobs sit on top of those:

* `MASTER_DB` — everything, applied in `oal_playback` where every `AL_GAIN` is set, so it
  reaches sound effects, the recorded speech and music alike.
* `MUSIC_DB` — the level music.
* `AMBIENCE_DB` — the cave, the forest and the rain.
* `MENU_MUSIC_DB` — the menu music, which has no binary gain to sit on, so this is the
  whole value.

All of them but the last ship at 0.0 dB, which multiplies by exactly 1.0, so the mix as
shipped is the original's to the bit. They are constants: nothing writes them to the save
yet, and a settings screen would read its sliders into them.

The music itself stays: tsatria03 put it on the menu deliberately, and said so on
2026-09-22. A silent menu is what the original has, and it is not what this port wants.

It also carries on rather than restarting. A menu is built fresh every time the player
comes back from a stage, the shop or the tutorial, and each one calls `BGMusicStart`, so
the music used to jump back to its first bar each time. `platform/music.py` now leaves a
player alone when it is asked for the file it is already playing, and only takes the new
gain and loop setting. The original rebuilds its `AVAudioPlayer` every time and so always
starts at the top; it has no menu music for this to matter to.

### Every shop and inventory screen says which one it is
`-[mainStoreController startRead]` (0x1d124) is three lines long and plays one sound, 13
`back button`; the weapon list, the weapon page and the inventory open the same way. On a
phone that was enough, because the screen itself was there to feel; here the shop, the
weapon list, a weapon's page and the inventory all announced themselves as "back button"
and nothing else.

Each screen now plays its own name as it opens — `Store Button` (18), `Weapon shop Button`
(235), `Inventory Button` (237), or the weapon's own name on a weapon's page — and reads
row 1 `TITLE_DELAY` (1.5 s) behind it. All of those are the original's own recordings;
nothing is synthesised. Moving or choosing cancels the wait, so the name is never talked
over. `blind_screen.BlindScreen.TITLE_SOUND` is where a screen names itself, and None
keeps the original's silence.

### A weapon that has not been bought cannot be equipped
The original lets you carry any of them for nothing. `-[DetailInventoryController
equipToggleAction:]` (0x2a618) reads only the `...USE` keys; the `itemN_have_flag`s it
could have checked are read in exactly one place, `-[InventoryController
blindModeSelectedMenu]` (0x2424c-0x242f4), where an unset flag only skips a button's
rounded corners; and `Stage_1_E` reads `useWeapon` alone (0x35724 in `startWeapon`,
0x35b54 and 0x35be0 in `gunChangeAction:`) and never `haveWeapon`. So the shop's prices,
and the gold a run pays, bought nothing that the inventory could not switch on for free.

**Fixed rather than reproduced**, at tsatria03's decision on 2026-09-22: equipping a
weapon that is not owned refuses, sets the page's message and says so through the speech
layer. Unequipping is always allowed, so a save that already has one switched on can be
cleared. The grenade, the knife and the colt count as owned, as `-[AppDelegate
weaponHave]` (0x4ee8) has it.

### Key bindings are a port addition
The original has no key bindings at all — every action is a swipe, a tap or a shake.
The port binds those actions to keys (`platform/keymap.py`), lets the player change
them from the screen F1 opens (`ui/keybind_screen.py`), and keeps them in
`%APPDATA%\SixthSense\keys.json`.

The defaults are not arbitrary: the tutorial teaches the lanes as clock positions, so
the arrows are laid out as a clock — Left is 9 o'clock, Left+Up is 10:30, Up is 12,
Right+Up is 1:30, Right is 3, Down is 6, which is the reload sector. A Q W E D S stay
bound alongside. There are no turn keys, since the original never turns you.

Bindings may be chords, resolved with a 60 ms window (`CHORD_WINDOW`) so that Left
alone and Left+Up can both mean something. 60 ms is far below anything this game reacts
to — a tick is a second and the shortest weapon cooldown is 0.3 s. `Shift+Tab` was
already a chord and goes through the same path.

F1 and Escape cannot be rebound, or a player could lock themselves out of both the game
and the screen that would let them fix it.

While the binding screen is up over a stage or the tutorial, the game's clock stops
(`RunLoop.hold`), so no zombie walks or attacks while the player reads. When it closes,
every timer's due date moves on by the time it was held, and the stage carries on where
it was. Over a menu the clock keeps running.

Escape pauses a stage, the same as P, and on the pause panel it resumes, the same as the
Continue row, as the developers decided on 2026-09-22, so Escape no
longer throws away the run and its coin. On the panel after a mission or a death it does
nothing, and the Main menu row leaves. In the tutorial it still goes back to the menu,
because the stop button there skips the tutorial.

### The binding screen speaks, the game does not
The game is self-voicing from 269 recorded WAVs, which `SoundList.plist` names by number
in 371 entries, and none of them can say a key name —
the only letters or digits in the bundle are `zero`..`nine`, for the number reader. So
the binding screen uses a synthesiser (`platform/speech.py`), and so do the few menu
lines no recording covers. Before every line, the first of these that can speak says it:

* NVDA, through its own controller client.
* Any other screen reader, through Prism (the `prismatoid` package): JAWS, ZDSR,
  ZoomText, System Access, PC-Talker, Boy PC Reader, Sense Reader, Window-Eyes, and
  Narrator, which is used only while `narrator.exe` is running.
* A plain Windows voice, SAPI 5 or OneCore, also through Prism, for a player with no
  screen reader at all.
* Nothing, if none of them can.

A player with NVDA never loads Prism. With voice over on, everything else in the game
speaks through its own recordings; with it off, the menus speak through the same layer
(see below).

### A screen reader mode, for the menus and the result panel
Built for the opening screen, the main menu, the shop, the inventory and the stage's
pause and result panel on 2026-09-22. The tutorial and the announcements during play
deliberately keep their recordings in both modes, because their timing follows the
recordings: the tutorial, for one, waits out each prompt before its zombie comes.

The original has two modes, and the main menu's voice over row switches between them
(`-[MainController ModeChageAction:]`, 0xb830). With voice over on, the game speaks
for itself through its own recordings. With it off, the original shows its standard
screens, which the iPhone's own screen reader, VoiceOver, reads instead. That second
mode is also why the ranking row, which the port leaves out, only opened its page while
VoiceOver was running (`-[MainController RankingAction:]`, 0xaef4).

The port has no standard screens to switch to, so turning voice over off hands the
menus' words to the Windows screen reader instead, through the same speech layer as the
binding screen: NVDA, any other screen reader through Prism, or a Windows voice when none
is running.
- Each row is one line: a button is "<name>, Button", such as "Back, Button", a weapon's
  picture is "Shotgun, Image", and a number is read whole with its label, such as
  "Price, 7,000", in place of the digit recordings one second apart.
- Each screen says its name before its first row, such as "Store." or "Shotgun.".
- Home and End go to the first row and the last, as a screen reader's own lists do, in
  the main menu, the shop, the inventory, the opening screen and the panel. With voice
  over on they keep their old meaning: the main menu's Home goes to row 1, and End,
  like any other key, repeats the row you are on (added 2026-09-23).
- What a choice says back, such as "Gold is lacking." or "Equipped.", is spoken too.
  "Gold is lacking." is heard in both modes: the original only played its recording in
  the self-voiced mode (0x1bbee) and left VoiceOver to read the label.
- The opening screen reads its welcome text and skips the earphone reminder, which the
  welcome text already says.
- The panel reads "Paused", "Mission success" or "Game over", each result with its
  number, such as "Score, 1,250", and its three buttons. The score row says the
  score, which it never does with voice over on: the reader it queues, `ReadScore`,
  only works the score out. Choosing a result row rereads that row, rather than the original's
  off-by-one reader (see "The result panel's double tap is off by one"), which stays
  as it was with voice over on. The panel's voice lines, "mission success", "game
  over", "paused" and "no coin", are spoken too (`Stage_1_E.PANEL_MESSAGE_TEXT`).
- The click every button makes, and the menu music, still play as recordings.
- The tutorial keeps its recordings, and once each one finishes the screen reader adds
  the keys for the gesture it described, from the player's own bindings, such as
  "Press A or Left Arrow to shoot toward 9 o'clock." Every recording ends before the
  beat's zombie comes, so the hint never talks over it (`stage_tutorial.KEY_HINTS`,
  added 2026-09-23).

The words are each screen's `ROW_TEXT` and `row_text`, and `MESSAGE_TEXT` in
`blind_screen.py`, rather than one table at `-[AppDelegate
playSound:Gain:Pos:z:reprats:]`, because a row's words carry what it is as well as its
name.

**New players start with voice over on.** The choice is saved under `EYEMODE`, the key
the voice over row already writes. The original fell back to `DEFAULTEYEMODE`, which
nothing writes, so a new save started in mode 0 (`AppDelegate.saved_mode`).

**The voice over row says what choosing it does,** as the original does: 332 "voice
over off button" while voice over is on (0xa2b8), and "Voice over on, Button" while it
is off. Choosing it plays the recording of the mode it switched to, 22 "voice over
off" (0xb990) or 21 "voice over on" (0xbb6e); turning it off used to be spoken by the
screen reader instead, until 2026-09-23. The port named the current mode instead from
2026-09-22 to 2026-09-23, and went back to the original's at tunmi13productions' word.

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

`game/sounds/unused/` holds 26 files that are not the original's own, laid out in the
same sub-folders they came from. Eleven are extra copies of a sound already in its
folder: one more `ui_select` in `sfx/misc`, and five more each of `gun_att_sound_1`
(the `*hit` files) and `weapon_nonbullets` (the `*empty` files) in `sfx/weapons`. The
other fifteen never came from the original: the eight character `hurt` sounds,
`grenadereload`, `yes`, `no`, `question`, `GameStart` (an edited cut of
`Game Start Button`), `welcome`, and `main menu.wav`, a trimmed cut of
`main menu button` that says only "main menu". Nothing in the port uses them, so the
sound lookup never looks in `game/sounds/unused/`.

`main menu button` (355), which the pause panel's last row reads, was one of those
trimmed cuts until 2026-09-22, when the original recording turned up and tsatria03 put
it in `used/`. The trimmed one stays in `unused/` under the name it had.

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

The order is the original's too, since 2026-09-23. Each action only counts once every
beat before it is done (`stage_tutorial.REQUIRES`): a reload needs One to FiveHalf
(0x84cfa), a weapon change One to Six (0x853c0), and shaking free One to Seven
(0x8b420). Then `NextTutorial` (0x8c89c) stops the prompts and starts the first beat
not yet done: at once after a kill or a reload, 1.5 s after a weapon change or an
escape (`NEXT_DELAY`). `CheckTutorial` (0x8c678) only nags One to Six, so Seven, Eight
and Nine each play once. Before that the port counted a reload or a weapon change
pressed during any beat, which finished those lessons before they were taught, and its
once-a-second check both nagged every beat and started the next one itself.

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
