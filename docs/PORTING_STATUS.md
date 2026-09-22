# Porting status

What is done, what is stubbed, what has not been started. Kept honest: "done" means
ported from the disassembly method by method, with the address recorded in the code.

---

## Done

| Original | Port | Notes |
|---|---|---|
| `oalPlayback` (48 methods) | `game/oal_playback.py` | Buffers, sources, queue/start/stop, listener, the two music streams. Same AL enums and values. |
| OpenAL framework | `platform/openal.py` | ctypes binding, OpenAL Soft, HRTF explicitly off — the original had none |
| `AVAudioPlayer` (bg/amb) | `platform/music.py` | source-relative OpenAL source |
| `AppDelegate` sound dispatch | `game/app_delegate.py` | `playSound:Gain:Pos:z:reprats:`, `playSoundBufNumber:`, `CheckSoundBuf:`, `findBufFlagNO`, `stopSoundBufNumber:`, `returnFileName:` |
| `AppDelegate` spoken numbers | `game/app_delegate.py` | `TTSNumber:type:`, `readNumber:`, `readStop`, `readTimeMin/Sec` |
| `AppDelegate weaponHave` | `game/app_delegate.py` | the `NSUserDefaults` weapon keys |
| `SoundListControl` | `game/sound_list_control.py` | |
| `MakeMaps` (all 4 initialisers + 3 queries) | `game/make_maps.py` | verified against `g_CH1_E` / `a_CH1_E.txt` / `s_CH1_E.txt` |
| `MovingAccelerometer` | `game/moving_accelerometer.py` | 4-way and 8-way compass, the 10° step, the ±20° tilt threshold |
| `PlayerControl` | `game/player_control.py` | |
| `WeaponControl` | `game/weapon_control.py` | `loadWeaponForGun:fileType:` index by index, `ReloadGun` |
| `MonsterControl` (lifecycle) | `game/monster_control.py` | `initWithMonsterPatern:...`, `MonsterStart:`, `MonsterComing:`, `MonsterMoving:`, `headShot:`, `headShotEnd:`, `hitPlayer`, `MonsterHitSound:`, `DieMonster`, `MonsterDead`, `shakeMonster`, `StopPlayGame`, `ReplayGame` |
| `MonsterControl` zig-zag walks | `game/monster_control.py` | `MovingType` 11/22/33/44/55, the four-bearing sweep and the turn-round at each end (0x1155e..0x1187c). **Half the shipped monster types walk one of these** |
| `Stage_1_E` core loop | `game/stage_1_e.py` | `viewDidLoad`, `MapInitInBundle`, `MainControl`, `timerLeft`, `breath:`, `ChangeLevel:`, `checkBoosDie` |
| `Stage_1_E` monsters | `game/stage_1_e.py` | `MakeMonster:`, `checkMonsterArray:`, `MonsterInit:`, `MonsterAttPlayer`, `MonsterDealloc`, `MonsterStop`, `MonsterReStart` |
| `Stage_1_E` fighting | `game/stage_1_e.py` | `MovingShot:`, `monsterHitHeadFind`, `MonsterDamage`, `MonsterDamageKnife`, `MonsterKillCount:`, `MonsterDie:`, `stopShot:` |
| `Stage_1_E` the grab | `game/stage_1_e.py` | `MonsterAttPlayer`'s grab branch (0x3b5ee), `shakingFind`, `NonShaking`, and the shake counter from `accelerometer:didAccelerate:` |
| `Stage_1_E` weapons | `game/stage_1_e.py` | `weaponInit`, `startWeapon`, `gunChangeAction:`, `doubleTapChangeWeapon:`, `threeTapChangeWeapon:`, `GunReloadAction:`, `reloadGun:` |
| `Stage_1_E` the end of a run | `game/stage_1_e.py` | `playerDie:` (the 11 s wait), `missionFailTell:`, `MissionSuccessTell`, `SuccessOrFailMission`, the gold paid into `GOLD`, `TOPSCORE` / `TOPSCOREWEEK`, `updateTopscoreRank` |
| `Stage_1_E` pause and result panel | `game/stage_1_e.py`, `ui/input.py` | `StopPlayAction:`, `continueAction:`, `gameReplayAction:`, `GameEndAction:`, `spaekMenu`, `StopElseSpeak`, the ten rows of `selectTapPointSoundStart`, `tapCount`'s table, and the five readouts |
| `NSTimer` / `performSelector:afterDelay:` | `platform/runloop.py` | including `cancelPreviousPerformRequestsWithTarget:selector:` |
| `NSUserDefaults` | `platform/defaults.py` | |
| `Stage_Tutorial` (252 methods) | `game/stage_tutorial.py` | The ten beats, `CheckTutorial`, the per-beat spawns, and `tutorialEndGameStart:` handing over to the walk |
| `MainController` (94 methods) | `game/main_controller.py`, `ui/menu_input.py` | The eight menu rows with their own WAVs, the coin economy (30 min a coin, cap 5, one a game, catch-up for time away), the voice-over toggle, the push into the stage, the tutorial or the shop |
| `startIntroPage` (26 methods) | `game/intro.py` | The splash, the two-second wait, the saved-game load and the warning message. The story text and `shakeDevice` are there too, unreachable exactly as they are in the original |
| `mainStoreController` (53) | `game/store.py` | The shop's front menu; the gold-shop row is unreachable in the original and is not offered |
| `StoreController` (85) | `game/store.py` | The weapon list and the gold readout |
| `DetailStoreController` (70) | `game/store.py` | One weapon's page: its four numbers, and `buyAction:` spending `GOLD` |
| `InventoryController` (80) | `game/inventory.py` | The eight slots |
| `DetailInventoryController` (66) | `game/inventory.py` | One slot's page and `equipToggleAction:`, which writes the `...USE` keys the stage reads |
| the shared screen shape | `game/blind_screen.py`, `ui/screen_input.py` | `selectTapPointSoundStart` / `tapCount` / `StopElseSpeak`, on Up / Down / Enter |
| **port addition** | `platform/keymap.py`, `ui/keybind_screen.py`, `platform/speech.py` | Rebindable keys with chord support, and the self-voiced F1 screen that edits them. The original has no bindings at all — see `DIVERGENCES.md`. |
| gestures + accelerometer | `ui/input.py` | mapped to the keyboard: A Q W E D attack the five lanes, S reloads, comma/full stop turn, Space shakes, P pauses |

---

## Stubbed — present, body empty, call sites intact

These were entirely UIKit in the original; the port keeps the method so the flow reads
the same but there is nothing to draw.

`HPImageCount`, `changeGameMode`, `buttonSelectImage`, `blindModeOff`,
`blindModeSelectedMenu`, `lodingBar01`..`lodingBar04`, `scratch1Pos`..`scratch5Pos`,
`tutorialHiddenView`, `AppDelegate.vibrate` (`AudioServicesPlaySystemSound`).

---

## Not ported

| Original | Why |
|---|---|
| `Stage_1_TEST` (243 methods) | The weapon test range. **It is reachable** — `-[DetailStoreController testAction:]` (0x1c1c0) pushes it from the Try button on a weapon's page; it is only unreachable from the menu. It is not a thin variant of `Stage_1_E`: 38 of the 241 methods they share have different bodies, including `weaponInit` (+548 bytes), `monsterHitHeadFind` (+768) and `MainControl` (−912), and `gunChangeAction:` is gutted to a bare return. Porting it is a job the size of `Stage_1_E` itself. The port logs a line and stays on the weapon's page when Try is chosen. |
| `Stage_1_E.mapPlotSound` / `soundFunction:yPlot:data:addSound:` | The ambient point-source layer. The shipped `s_CH1_E.txt` is entirely zeros, so it can never run on the shipped map, and the tail below 440 cm reuses `d8`/`s16` in a way that could not be pinned down without being able to run it. The distance ladder that **was** recovered is in `GAME_STRUCTURE.md` §2. |
| `angleTest` (192 methods) | A development build. Nothing in the binary references the class at all. |
| `intro2storyPage` (22 methods) | The story page. Nothing in the binary ever creates one; the story text and its WAV live in `startIntroPage.shakeDevice`, which nothing calls either. |
| `AccelerometerFilter`, `LowpassFilter`, `HighpassFilter` | Apple's `AccelerometerGraph` sample code, linked in and never referenced — none of the three appears in `__objc_classrefs`, so nothing can instantiate them. |
| `GoldStoreController`, `CoinStoreController`, `getCoinListController`, `StoreController.ItemAllAction:`, `mainStoreController.restoreAction:` | StoreKit. Buying gold or coins, the *Purchase all weapons* bundle and restoring purchases were in-app purchases. The rows are kept and say they are unavailable. |
| `RankingViewController`, `FriendJoinViewController`, `JoinUsViewController`, `AddFriendViewController`, `AutoLoginController`, `buyNetworkControl`, `RankingViewControllerCells` | Leaderboards and accounts, all backed by a server that is gone. `SuccessOrFailMission` keeps the week's best score locally and does not try to upload it. |
| `mainStoreController.itemShopAction:` | Four bytes long: it returns. There is no item shop. |
| `-[oalPlayback stopSoundArea:]` | Walks the array, reads `intValue` off each entry and discards it. Nothing calls it. |
| Facebook SDK, `JSONDecoder`/`SBJSON`, `GKAchievementHandler`, `IconDownloader` | Third-party and network |

---

## Verified against the original data

* The map parses to 701 x 42 with the corridor at column 20, ground 21 for rows
  21..679 and ground 23 at rows 387..388.
* The action layer reads 9, 8, 10 then 1..7 descending, as the tables in
  `GAME_STRUCTURE.md` show.
* All eight weapons load with the damage/range/round counts in the plists.
* Every `SoundList.plist` entry that the monster tables reference resolves to a WAV in
  the bundle, and so does every row of every menu, shop and inventory screen.
* Of the 130 shipped `type*.plist` files, 80 walk a straight lane (`MovingType` 1..5)
  and 50 walk a zig-zag (11/22/33/44/55); the port's ladder reproduces the sweep and
  the turn-round for all five.
* A headless run walks one cell per second, spawns one monster per lane, closes at
  `comingRange` cm per footstep, opens and closes headshot windows, and resolves shots
  by lane and range.
* `zombie_8` grabs at 25 cm; ten shakes free you and kill it, and letting the timer run
  out costs a heart instead.
* Buying a weapon spends `GOLD`, sets its owned and equipped keys, and refuses a second
  purchase; a grenade costs 1000 and adds one to `GRENADECOUNT`.

---

## The disassembly is ready for the rest

`analysis/disasm/` holds decompiled listings for every game class, ported or not —
including `Stage_1_TEST`, `angleTest`, the ranking and account screens and the StoreKit
ones. Regenerate any of them with `tools/dc.py`; `tools/rows.py` and `tools/bands.py`
pull a blind-mode screen's rows and its double-tap table straight out of a class, which
is how the shop and the inventory were read. See `tools/README.md`.

---

## Running it

```bash
python SixthSense.py --skip-tutorial
```

Headphones. `--no-window` runs it without pygame. `--no-intro` opens on the menu.
`--game DIR` points at another copy of the bundle; the default is `game/`, which holds
the original untouched.
