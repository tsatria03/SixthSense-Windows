# SixthSense — how the game works

Everything here was read out of `Payload/sixsense.app/sixsense`, an **unencrypted**
armv7 Mach-O (`LC_ENCRYPTION_INFO cryptid = 0`), plus the data files shipped beside it.
Addresses are file offsets in the thin armv7 slice (fat offset `0x1000`), the same
numbers the listings in `analysis/disasm/` use.

* `CFBundleIdentifier` `kr.co.bitbee.sixsense`, version 1.2, built against iOS SDK 6.1.
* 67 Objective-C classes; the game is 13 of them, the rest are Facebook SDK and JSON.
* Audio is OpenAL plus two `AVAudioPlayer`s. Orientation is `UIAccelerometer`.

---

## 1. The classes that matter

| Class | Size | What it is |
|---|---|---|
| `AppDelegate` | 0x84 | Global state **and the whole sound dispatch** |
| `oalPlayback` | 0x1580 | 128 OpenAL buffers, 122 sources, listener, two music streams |
| `MakeMaps` | 0x10 | The three-layer grid |
| `MovingAccelerometer` | 0x1c | Which way the player faces |
| `PlayerControl` | 0x5c | HP, weapon, kill tallies, grid position |
| `WeaponControl` | 0x7c | One weapon, loaded from its plist |
| `MonsterControl` | 0xd0 | One monster: lane, range, sounds, timers |
| `Stage_1_E` | 0x288 | The stage — 262 methods |
| `Stage_Tutorial` | 0x278 | The tutorial, a near-copy of `Stage_1_E` |
| `Stage_1_TEST` | | The weapon test range, opened from the Try button on a weapon's page in the shop |
| `angleTest` | | A development build that nothing references |
| `MainController` | 0x140 | Main menu and stage select |
| store / ranking / Facebook | | Shop, leaderboards, IAP — all server-backed |

---

## 2. The world

`MakeMaps` holds `maps[y][x]`, each cell a dictionary of four strings:

```
"X"  column      "G"  ground layer   g_CH1_E
"Y"  row         "A"  action layer   a_CH1_E.txt
                 "V"  sound layer    s_CH1_E.txt
```

`-[MakeMaps initWithMapGroundFileString:soundPosFileName:actionPosFileName:]` (0xf6b0)
splits each file by `"\n"` and each row by `" "`.

The shipped map is **701 rows x 42 columns** (41 values plus the empty component the
trailing space produces). It is a corridor one cell wide:

* ground `21` at column 20, rows 21..679 — walkable
* ground `23` at (20, 387) and (20, 388)
* everything else `0` — wall
* the sound layer `s_CH1_E.txt` is entirely `0`: no ambient point sources are placed

`stage1ground` / `stage1sound` are a second, unused 400x400 map read by the other
initialiser (0xf3bc), which indexes by character instead of splitting on spaces. Both
are all zeros.

A cell is **40 cm**: `-[Stage_1_E soundFunction:yPlot:data:addSound:]` (0x31428) computes
`dx*dx + dy*dy` in cells and multiplies by 1600 to get cm², then drops anything at or
beyond `577601` (760 cm, i.e. 19 cells — exactly the 40x40 window
`-[MakeMaps MovingPlotX:PlotY:]` returns).

Inside that radius it walks a ladder of squared distances, multiplying the gain the
layer gives the source by a constant that grows as the source gets closer, and hands
the result to `-[oalPlayback queueNote:gain:sourcePos:defaultZ:repeats:]` with
`repeats` set:

| squared distance | that is | gain × | `defaultZ` | at |
|---|---|---|---|---|
| ≥ 577601 | > 760 cm | — nothing is placed — | | 0x31522 |
| ≥ 518400 | 720 cm | 1.0 | 40 | 0x3155c |
| ≥ 462400 | 680 cm | 1.2 | 40 | 0x315c8 |
| ≥ 360000 | 600 cm | 1.32 | 40 | 0x315ec |
| ≥ 313600 | 560 cm | 1.48 | 40 | 0x31608 |
| ≥ 270400 | 520 cm | 1.6 | 20 | 0x31624 |
| ≥ 230400 | 480 cm | 1.72 | 40 | 0x3166a |
| ≥ 193600 | 440 cm | 1.88 | 40 | 0x31712 |
| < 193600 | closer | 1.2 above 40 cm, doubled below | 40 | 0x31770 |

The last row is where the transcription stops being certain: below 440 cm the compiler
reuses `d8` and `s16` for both the gain and the converted coordinates, and there is no
way to check the reading by running it, because the shipped layer is empty. That is
why the method is not ported — see `PORTING_STATUS.md`.

### The action layer

Reading down column 20 (the direction the player walks):

```
y=680  9      y=601  9      y=500  9      y=400  9  ...
y=675  8      y=596  8      y=495  8      y=395  8
y=669 10      y=590 10      y=489 10      y=389 10
y=664  1      y=585  2      y=484  3      y=384  4
                                          ...  y=284  5, y=184  6, y=83/22  7
```

`-[Stage_1_E MainControl]` reads the action under the player each tick:

| value | effect |
|---|---|
| 1..7 | sets `monster_num`, the spawn tier, until the next action cell |
| 8 | sends one of 10001..10010 at random (0x320e6..0x322da): 10001..10005 are the girl who heals you, 10006..10010 the woman zombie. Straight after the tutorial the first two are 10008, then 10003 |
| 9 | `[playback backgroundSoundStop]`, and stores 9 as `monster_num` (0x31f06), which spawns nothing: each section opens with a quiet stretch |
| 10 | starts `bgm_cave` or `bgm_forest` depending on `gameMode` |

So the difficulty ramps 1 → 7 as the player descends, and the music comes and goes.

---

## 3. The clock

`MotionSamplingTimer` is an `NSTimer` at **1.0 s**, repeating, target `MainControl`
(0x2e092). It is created at the end of `MapInitInBundle` **only when `isTutorial != 0`**
(0x2e08e), and re-created by `ChangeLevel:`.

One tick of `-[Stage_1_E MainControl]` (0x3182c):

1. return if `walkXFlag` or `isShake`
2. `breathCount++`; every second tick, if `brearhFlag` is clear, play the player's
   breath — sound 80/81/82 by HP (>=3 / >=2 / >=1) at gain 0.5 — and clear the flag
   again 3.0 s later (0x31964). That skips every other chance, so the player breathes
   once every four seconds
3. `groundAhead = movePlayGroundState(x, y-1)`, `action = movePlayActionState(x, y)`
4. if `groundAhead >= 1`:
   * `y >= 23`: step forward, `playerYplot--`
     * at `y == 29` play the alarm, `warring` (285), at 0.2
     * at `y == 23` send the boss down lane 3 — type 5008 in gameModes 2 and 3, 5003 in
       gameMode 1 — and stop the alarm (0x31d12..0x31e2e)
   * otherwise (standing at 22): if `checkBoosDie` (no live `monsterNumber` 5001, or
     5000 in gameMode 1), kill every monster left and count each one, `LVUP++`, flip
     `gameMode` between cave and forest, start that ambience at 0.3, schedule
     `ChangeLevel:` 2 s later, stop the timer and return
5. dispatch the action value (table above)
6. `MakeMonster:`, `MonsterAttPlayer`, `HPImageCount`, and schedule `timerLeft`
7. if HP has reached 0, play `player_die` (84) and `playerDie:` 1.3 s later; `game
   over` (354) comes from the panel after that

`ChangeLevel:` (0x322e0) puts the player back at y = 680, multiplies `monsterHPGain`
by **1.5**, loops the other level's ambience as a note at 0.02, and restarts the
timer. The corridor is 657 walkable
cells, so a level is about eleven minutes of walking if nothing stops you.

---

## 4. Monsters

**A monster has no grid position.** It has a *lane* (a compass bearing) and a *range*
in cm. `MovingType` in its plist chooses the lane:

| `MovingType` | `NSUserDefaults` key | bearing | starting `Pos` |
|---|---|---|---|
| 1 | `WZ` | 180° | (-1000, 0) |
| 2 | `WNZ` | 123° | (-500, 866) |
| 3 | `NZ` | 90° | (0, 1000) |
| 4 | `ENZ` | 57° | (500, 866) |
| 5 | `EZ` | 0° | (1000, 0) |

(The starting positions are 180/120/90/60/0°, the walking bearings 180/123/90/57/0° —
the original's own inconsistency.) Types 11/22/33/44/55 are zig-zag walkers that switch
bearing on `MovingCount`.

`monsterRange` starts at **1000.0** and `initWithMonsterPatern:...` ends by calling
`MonsterStart:` itself (0x10c2a, 0x10c3e).

Two timers per monster:

```
MainMonsterTimer         comingSoundTime                        -> MonsterComing:
MonsterMovingAngleTimer  (comingSoundTime - 0.1) / comingSoundInWalk -> MonsterMoving:
```

Each `MonsterMoving:` (0x10f38) is one footstep:

```
monsterRange = sqrtf(Pos.x^2 + Pos.y^2);
monsterRange = monsterRange > 25.0f ? monsterRange - comingRange : 20.0f;
rad = MovingPosAngle * M_PI / 180;
Pos = (monsterRange * cos(rad), monsterRange * sin(rad));
comingSoundGain *= 1.1f;                     // it gets louder as it closes
[playback startSound:comingMonsterStopSoundNumber Postion:Pos soundGain:comingSoundGain];
```

`MonsterComing:` takes the first step of each cycle at once (0x1194c), so a monster is on
its lane from the start. `MonsterStart:` starts the walk sample once, looping, and
`startSound:Postion:soundGain:` only moves that playing source to `(x, 40, y)` and sets
its gain; it never restarts it (0xe560).

For `zombie_1` that is `comingRange` 40 cm every `(2.7 - 0.1)/3 = 0.867 s`, so about
22 seconds from 1000 cm to contact. At `monsterRange <= 25` `MonsterAttPlayer` fires.

### The headshot window

The monster breathes. `headShotTimeStart` seconds after each cycle begins,
`headShot:` raises `headShotFlag`; `headShotTimeEndHowLong` seconds later
`headShotEnd:` drops it. A hit landed inside that window does **double damage** and
counts as a headshot (0x3a1dc: `HP - (Damage << 1)`), and plays `headshot_4` (330).
When the plist gives a comma-separated list (`"0.3,1.3"` in `type71.plist`) the monster
has two windows per cycle, walked by `headShotTimer`.

### Spawning

`-[Stage_1_E MakeMonster:]` (0x36100), once per tick:

```
LVCount++;
if (tier < 1 || tier > 7) return;
if (LVCount < 3) return;                       // at most one try per 3 seconds
LVCount = 0;                                   // every try, spawn or not
if (MonsterBuffer.count >= LVUP + 2) return;   // the live cap
idx = arc4random() % mod + off;                // by tier, see below
if ([self checkMonsterArray:idx] == -1) return;  // that lane is taken
[self MonsterInit:[monsterArray[idx] intValue]];
```

`monsterArray` is 50 type ids built in `viewDidLoad` (0x2c7e4):
`1,2,3,4,5, 11..15, 21..25, ... 91..95`. Index `i` is **kind `i/5 + 1`, lane `i%5 + 1`**,
and `checkMonsterArray:` refuses a type whose `id % 10` lane already has a monster in
it — so at most five monsters, one per lane. Every id ends in 1..5, so the zig-zag
walkers (ids ending in 6..0) never spawn.

| tier | index | kinds |
|---|---|---|
| 1 | `rand % 10` | 1–2 |
| 2 | `rand % 20` | 1–4 |
| 3 | `rand % 30` | 1–6 |
| 4 | `rand % 25 + 10` | 3–7 |
| 5 | `rand % 30 + 10` | 3–8 |
| 6 | `rand % 25 + 20` | 5–9 |
| 7 | `rand % 20 + 30` | 7–10 |

### Monster stats

`typeN.plist` is a flat Korean label/value array read by index
(`-[MonsterControl initWithMonsterPatern:...]` 0x10618):

```
 1 방향 타입      MovingType         21 맞는 소리 시간    hitSoundTime
 3 체력           HP * HPGain        23 죽는 소리        (from the caller)
 5 공격력         Damage             25 죽는 소리 크기    dieSoundgain
 7 다가오는 소리  (from the caller)  27 죽는 소리 시간    dieSoundTime
 9 소리 시작 크기 comingSoundGain+0.2 29 때리는 소리     (from the caller)
11 소리 길이      comingSoundTime    31 때리는 소리 크기  playerHitSoundGain
13 걷기 숫자      comingSoundInWalk  33 때리는 소리 시간  playerHitSoundtimer
15 접근 속도      comingRange*HPGain 35 숨소리 시작      headShotTimeStart  (may be "a,b")
17 맞는 소리      (from the caller)  37 숨소리 끝        headShotTimeEndHowLong
19 맞는 소리 크기 hitSoundGain*0.5   39 흔드는 몬스터     shakeMonsterFlag
                                    41 몬스터종류       monsterNumber
                                    43.. shake approach / push
```

The `"-"` entries are the sound numbers, which the *caller* supplies — see below.

---

## 5. Sound: one number, one voice

`AppDelegate.aSoundBufControlData` is a growing array of `SoundListControl`
(`sFileName`, `iFileNumber`, `bIsPlaying`). **The index of an entry is the OpenAL
note**: slot *i* owns `oalPlayback._buffers[i]` and `._sources[i]`.

```
-[AppDelegate playSoundBufNumber:] 0x6370
    i = CheckSoundBuf(num)              // an entry already holding this sound number?
    if (i == -1) {
        free = findBufFlagNO()          // first entry with bIsPlaying == NO
        ctl = { bIsPlaying = YES, iFileNumber = num,
                sFileName = SoundList.plist[num] }
        i = (free == -1) ? append(ctl) : replace(free, ctl) + free/free buffer
        [playback initBufferOne:i FileName:ctl.sFileName Type:@"wav"]
        [playback initSourceOne:i]
    } else entry(i).bIsPlaying = YES
    return i
```

So **a sound number is a voice**. Two monsters given the same `comingSound` share one
OpenAL source and cut each other off. That is why `SoundList.plist` lists each zombie
sample three times (93, 94, 95 are all `zombie_1_coming_cave`) and why
`-[Stage_1_E MonsterInit:]` (0x36524) is 11 KB of code picking a number no live monster
is already using, per kind, per `gameMode`:

| kind | coming (cave) | coming (forest) | damage | die | hits player |
|---|---|---|---|---|---|
| 1 | 93,94,95 | 96,97,98 | 99,100,101 | 102,103,104 | 105,106,107 |
| 2 | 108,109,110 | 111,112,113 | 114,115,116 | 117,118,119 | 120,121,122 |
| 3 | 123,124,125 | 126,127,128 | 129,130,131 | 132,133,134 | 135,136,137 |
| 4 | 138,139,140 | 141,142,143 | 144,145,146 | 147,148,149 | 120,121,122 |
| 5 | 150,151,152 | 153,154,155 | 156,157,158 | 159,160,161 | 135,136,137 |
| 6 | 165,166,167 | 168,169,170 | 171,172,173 | 174,175,176 | 177,178,179 |
| 7 | 180,181,182 | 183,184,185 | 186,187,188 | 189,190,191 | 135,136,137 |
| 8 | 192,313,314 | 193,315,316 | 194,317,318 | 195,319,320 | 196,321,322 |
| 9 | 199,200,201 | 202,203,204 | 205,206,207 | 208,209,210 | 211,212,213 |
| 10 | 214,215,216 | 217,218,219 | 205,206,207 | 208,209,210 | 220,221,222 |
| 11 | 292,293,294 | 295,296,297 | 301,302,303 | 310,311,312 | 307,308,309 |
| 12 | 304,305,306 | 304,305,306 | 301,302,303 | 310,311,312 | 307,308,309 |
| 21 (the girl) | 267 | 268 | 269 | 269 | 270 |
| 22 (the woman zombie) | 271 | 272 | 273 | 273 | 274 |
| the bosses | 286 | 290 | 205 | 289 | 288 |

kind 8 also takes `approach` 197,323,324 and `push` 198,325,326 — it is the one that
grabs you and has to be shaken off.

`gameMode` is `arc4random() % 3 + 1` at `viewDidLoad` (0x2d360): 1 = cave,
2 = forest, 3 = forest with rain.

### The OpenAL calls

```
-[oalPlayback queueNote:gain:sourcePos:defaultZ:repeats:]  0xe028
    AL_LOOPING            repeats
    AL_REFERENCE_DISTANCE 40.0          AL_MAX_DISTANCE 800.0
    AL_GAIN               gain
    AL_CONE_OUTER_ANGLE   1.0           AL_CONE_INNER_ANGLE 1.0
    AL_POSITION           (pos.x, (float)defaultZ, pos.y)
    AL_BUFFER             _buffers[note].bufferId

-[oalPlayback MonsterQueueNote:...]  0xe188   same, 100.0 / 1600.0, no inner cone

-[oalPlayback setListenerRotation:]  0xe890
    alListenerfv(AL_ORIENTATION, {cosf(r + M_PI_2), sinf(r + M_PI_2), 0, 0, 1, 1});
```

**This is not a 3D audio game in the binaural sense.** The binary imports eighteen
OpenAL symbols and every one is core AL or ALC; it touches none of Apple's `ALC_ASA_*`
spatial extensions, and the only extension string anywhere in it is
`alBufferDataStatic`. iOS's OpenAL renders plain core AL as **distance attenuation plus
amplitude panning** — there is no HRTF in it. What the game gets out of OpenAL is a
stereo field, and that is all.

The geometry it feeds that field is odd. The "at" vector lies in x/y while sources are
placed in x/z, and "up" is `(0, 1, 1)`, not a unit vector. Worked through, OpenAL's
basis comes out as right `= +X`, up `= +Z`, forward `= +Y`, so the game's *x* is
left/right, the game's *y* becomes elevation, and forward depth is the constant
`defaultZ`. Rotating the listener rotates that basis correctly.

Rendered through OpenAL Soft's loopback device with HRTF off, the same parameters
`MonsterQueueNote:` passes, listener facing 0° (`tools/pan_check.py`):

| lane | bearing | `Pos` | left | right | L/R |
|---|---|---|---|---|---|
| 1 `WZ` | 180° | (−1000, 0) | 0.043 | 0.000 | hard left |
| 2 `WNZ` | 123° | (−500, 866) | 0.043 | 0.010 | +12.5 dB |
| 3 `NZ` | 90° | (0, 1000) | 0.030 | 0.030 | centre |
| 4 `ENZ` | 57° | (500, 866) | 0.010 | 0.043 | −12.5 dB |
| 5 `EZ` | 0° | (1000, 0) | 0.000 | 0.043 | hard right |

Five distinct stereo positions, symmetric about centre, at equal total loudness.
Lanes 2 and 4 are pulled toward the middle rather than pinned to a side because their
large *y* lands as elevation, which amplitude panning folds back toward centre. That
is the whole spatial vocabulary of the game: left, half-left, centre, half-right,
right, with distance carried by volume.

Numbers are spoken digit by digit from the `zero`..`nine` WAVs, one per second
(`TTSNumber:type:` 0x5590 → `readNumber:` 0x5cbc), then the unit word: 335 hours,
336 minutes, 337 seconds, 338 "the coin is full", 339 "the coin is charged after".

---

## 6. Weapons

`-[Stage_1_E weaponInit]` (0x35008) builds
`Grenage, Knife, Colt, Shotgun, M4A1, AK47, MG80, Japanese, powersaw` and loads the
**first eight** (`cmp r4, 8` at 0x3512c) into `weaponSource[8]`. The power saw is in
the array and has a plist, but no loop iteration ever reaches it.

| # | file | damage | range cm | rounds | shot s | reload s | shot snd | reload snd |
|---|---|---|---|---|---|---|---|---|
| 0 | Grenage | 150 | 1600 | 1 | 2.0 | 2.0 | 57 | 57 |
| 1 | Knife | 30 | 200 | 1 | 0.5 | 1.0 | 58 | 58 |
| 2 | Colt | 30 | 1000 | 7 | 0.5 | 2.3 | 61 | 62 |
| 3 | Shotgun | 35 | 1000 | 10 | 0.5 | 1.5 | 63 | 64 |
| 4 | M4A1 | 40 | 1300 | 25 | 0.3 | 2.4 | 65 | 66 |
| 5 | AK47 | 40 | 1300 | 30 | 0.3 | 2.3 | 67 | 68 |
| 6 | MG80 | 45 | 1600 | 50 | 0.4 | 3.0 | 69 | 70 |
| 7 | Japanese | 100 | 300 | 1 | 0.5 | 1.0 | 71 | 71 |
| 8 | powersaw | 200 | 300 | 1 | 1.0 | 1.0 | 75 | 75 |

Ownership lives in `NSUserDefaults` (`-[AppDelegate weaponHave]` 0x4ee8): grenade,
knife and colt are always owned; `SHOTGUN`, `M4`, `AK47`, `MG80`, `JAPAN` are bought.
What is equipped is `GRENADEUSE`, `KNIFEUSE`, `COLTUSE`, `SHOTGUNUSE`, `M4USE`,
`AK47USE`, `MG80USE`, `JAPANUSE`.

The grenade comes out of `GRENADECOUNT`, not a magazine.

---

## 7. Fighting

The pan gesture accumulates into `posX`/`posY`; at the end of the gesture
`-[Stage_1_E MovingShot:]` (0x2ec98) takes `atanf(posY/posX)` in degrees, fixes the
quadrant (+180 or +360), stores it in `shotAngle`, and quantises:

The tutorial teaches these as clock positions, which is exactly what they are:

| swipe | clock | `shotMonster` |
|---|---|---|
| 156.5..222.5 (melee) / ..242.5 (guns) | 9 o'clock | 1 |
| 112.5..155.5 | 10:30 | 2 |
| 62.5..112.5 | 12 | 3 |
| 22.5..62.5 | 1:30 | 4 |
| 0..22.5, or 320.5..360 (melee) / 300.5..360 (guns) | 3 o'clock | 5 |
| the gap, about 242.5..300.5 | **6 o'clock** | **reload** for a gun (0x2f9e4), lane 3 for melee (0x2f99e) |

A gun swiped to 6 o'clock calls `GunReloadAction:` and the attack stops there — that
is the reload gesture, and `tutorialSix` ("if you make your finger 6") is the beat
that teaches it.

`-[Stage_1_E monsterHitHeadFind]` (0x3ab88) then takes the **nearest** monster whose
`MovingPosAngle` is inside that lane's band and whose `monsterRange` is within the
weapon's `Range`:

```
shotMonster 1   157..202        4    23..62
            2   113..155        5     0..22 or 338..360
            3    63..112
```

Those bands are exactly the five lane bearings, so the swipe is "attack the direction
I can hear". Damage is `weapon.Damage`, or for a gun `weapon.Damage * 2` inside the headshot
window. Melee weapons (1, 7, 8) and the grenade (0) do not spend a round; the grenade
hits everything alive. A melee swing resolves 0.1 s later in `MonsterDamageKnife`
(0x392fc): plain damage, `att2` on a hit, `att1` on a kill, and the weapon's own sound
only on a miss.

A gunshot or grenade lands 0.5 s after it is fired (0x2fd70, 0x2f32a); the headshot is
judged at the trigger. `shotFlag` blocks a second attack until `stopShot:` fires,
`weapon.ShotTime` seconds later — that is the rate of fire — and a reload holds it until
`reloadGun:`.

Ammunition is only spent when `isTutorial != 0` (0x2f41a); during the tutorial it is
free.

---

## 8. Taking damage

`-[Stage_1_E MonsterAttPlayer]` (0x3b040), each tick, for every monster within 25 cm:

* `shakeMonsterFlag` set → it grabs you: `isShake = YES` and you must shake free.
  `-[Stage_1_E accelerometer:didAccelerate:]` (0x3c84c) counts accelerations over
  1.0 g and frees you at **10**. Nothing ever resets that count, so after the first
  escape in a stage every later grab breaks on one shake. The port asks for 1 to 5
  presses of the shake key instead, drawn for each grab (see DIVERGENCES.md).
* `monsterNumber == 21` (the girl) → **HP++** if HP <= 3, and her `hitPlayer` plays 270,
  her thank you. She is a rescue, not a threat; shooting her costs a heart.
* otherwise → HP-- (only once `isTutorial` is set, 0x3b2e6), `player_damage` (83) 0.1 s
  later, a blood flash, and the monster's `hitPlayer` plays its `playerHitSound` and then
  dies. In the tutorial it re-prompts that monster's beat instead.

The monsters it is done with are removed after the loop (0x3b44e).

The player starts with **HP 3**; the on-screen hearts are `hpHeartImageView1..4`.
At HP 0: `game over` (354), then `playerDie:` and the fail screen.

---

## 9. The tutorial

`Stage_Tutorial` is a near-copy of `Stage_1_E` with nine scripted beats
(`tutorialOne` … `tutorialNine`, each with a `SoundStop`, `End`, `Restart` and
`RestartFinger` partner) driven by the same action layer. It writes
`TUTORIAL = "1"` when it finishes (0x839d4), and **`Stage_1_E` will not start its walk
timer until that key is set** (0x2e08e). The name is the wrong way round:
`isTutorial != 0` means "the tutorial has been cleared".

---

## 10. What is server-backed and therefore dead

* `-[Stage_1_E MapInit]` downloads the map from
  `https://dl.dropbox.com/u/93379123/g_CH1_E` — gone. `MapInitInBundle` is the path
  that works, and it reads the files shipped in the bundle.
* Ranking, friends and the score upload (`sendScore:`, `reqTimerMethod:`,
  `RankingViewController`, `JoinUsViewController`) post to the publisher's server.
* In-app purchases (`StoreKit`), Game Center and the whole Facebook SDK.
* `VersionCheck` (0x4635) pings the publisher on launch.
