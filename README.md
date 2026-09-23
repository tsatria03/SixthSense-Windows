# SixthSense-Windows
A Windows port of SixthSense, recovered from the iOS binary.

## What this is

A Python port of **SixthSense** (`kr.co.bitbee.sixsense` 1.2, Bitbee, 2013), an iPhone
audio game for blind players: you walk down a corridor in the dark and shoot what you
hear coming.

The port runs off the original app bundle's own data — the binary plists and the three
map layers, unconverted, and the original's recorded sounds, sorted into folders under
their own names — and drives OpenAL Soft with the same calls and the same values the
iOS build used. Nothing about the game's numbers was invented here;
where the original's data is malformed, the port reproduces the malformed result and
`docs/DIVERGENCES.md` says why.

**Wear headphones.** The game says so itself (`SoundList.plist` 234,
"you must use earphone") and none of it works on speakers.

---

## Requirements

64-bit Python 3.12 or newer on Windows 10 or later, and two packages to play:

    pip install -r requirements.txt

| package | what needs it |
|---|---|
| `pygame` | the window, the keyboard and the frame loop (`SixthSense.py`, `ui/`). It must be `pygame`, not `pygame-ce`: the two cannot be installed side by side, and the port is written against `pygame` |
| `prismatoid` | Prism, which speaks the few lines no recording covers through any screen reader other than NVDA, or through a Windows voice when none is running (`platform/speech.py`). Without it the game still runs, but only NVDA speaks |

Everything else is the standard library — the audio is OpenAL Soft through `ctypes`,
and the WAVs, plists and map files are read with `wave` and `plistlib`. OpenAL Soft
(`vendor/openal/soft_oal.dll`) ships with the repository, so there is nothing to install
for it and no system OpenAL is used.

`vendor/nvda/nvdaControllerClient64.dll` ships too, so NVDA can speak those few lines:
the key-binding screen and a few menu messages. The game itself speaks entirely through
its own recorded WAVs and needs no screen reader.

One more package is needed only to redo the reverse engineering, never to play:

    pip install capstone

| package | what needs it |
|---|---|
| `capstone` | the armv7 Thumb-2 disassembler (`tools/dz.py`, `tools/dc.py`, `tools/digest.py`) |

`tools/mb.py`, `tools/objc.py`, `tools/rows.py`, `tools/bands.py` and
`tools/pan_check.py` are standard library only — `pan_check.py` drives the same
vendored OpenAL Soft the game does.

## Running it

```bash
python SixthSense.py
```

That opens on the splash and the warning, as the original does, and then the menu.
**Up** and **Down** walk the eight rows and **Enter** chooses; each row reads itself
with the game's own recording. A game costs a coin. A new player starts with ten, and
coins come back one every thirty minutes up to five, even while the game is closed,
which is what the original does too.

The **Store** row opens the shop — the weapon list, a page per weapon with its four
numbers read aloud, and the inventory, where what you equip is what the stage hands
you. Gold comes out of your runs: twelve a kill and two a headshot.

`--stage` and `--tutorial` skip the menu, `--no-intro` skips the opening. Other
options: `--no-window` (headless), `--game DIR` (another copy of the bundle), `-v`.

`Stage_1_E` will not start its walk timer until `TUTORIAL` is set (0x2e08e), so until
you have finished the tutorial once, Start Game takes you to the tutorial instead, and
spends no coin. `--skip-tutorial` writes the key the tutorial writes, if you would rather
skip it.

The save file lives in `%APPDATA%\SixthSense\defaults.json` — the `NSUserDefaults`
keys the original writes, under their own names.

## Controls

The tutorial teaches the five lanes as **clock positions** — 9, 10:30, 12, 1:30, 3 —
and 6 o'clock for reload. The arrow keys are a clock face, so that is where they sit:

| clock | arrows | letter | |
|---|---|---|---|
| 9:00 | **←** | **A** | attack hard left (180°) |
| 10:30 | **← + ↑** | **Q** | attack half left (123°) |
| 12:00 | **↑** | **W** | attack straight ahead (90°) |
| 1:30 | **→ + ↑** | **E** | attack half right (57°) |
| 3:00 | **→** | **D** | attack hard right (0°) |
| 6:00 | **↓** | **S** or **R** | reload — the game's own 6 o'clock swipe |

Both sets are live at once, so either hand position works. The diagonals are real
chords: hold both keys together.

| | |
|---|---|
| **,** / **.** | turn 10° (Left and Right are lanes now) |
| **Tab** / **Shift+Tab** | next / previous weapon |
| **Space** | shake free when something has hold of you (ten presses) |
| **P** | pause — the original's stop button, which has no key of its own |
| **F1** | key bindings — see below |
| **Esc** | back to the menu from a stage, or quit from the menu |

When the pause or result panel is up, the keyboard belongs to it: **Up** and **Down**
walk its rows, **Enter** chooses. The same goes for the menu, the shop and the
inventory. You can pause as often as you like: continue and restart both let the next
pause through, as in the original.

Keyboard only — no mouse. The lane keys replace the swipe rather than simulating it:
`MovingShot:` quantises its angle into five bands and a reload sector anyway, so a key
hands the game the band directly.

### Rebinding

**F1** opens the key-binding screen, which reads itself aloud — through NVDA if it is
running, otherwise through any other screen reader by way of Prism (JAWS, ZoomText,
System Access, Narrator and more), or a Windows voice if none is running. It has to:
the game's own voice is 269 recorded WAVs and none of them can say "Left Arrow".

    Up / Down   move          Enter   rebind        A   add a second binding
    Delete      unbind        R R     reset all     Escape / F1   back

Binding captures a chord — hold the keys together and let go. **F1 and Escape are not
rebindable**, so there is always a way back in. Bindings live in
`%APPDATA%\SixthSense\keys.json`, stored by key name so a pygame update cannot
scramble them.

## How to play

Monsters do not walk on the map; they walk down one of **five lanes** toward you, and
each footstep brings them 40-ish cm closer and makes them louder. Listen for which lane
a monster is in and attack that lane before it reaches 25 cm.

Every monster **breathes**, and there is a gap in the breathing. A hit landed in that
gap is a headshot and does double damage. That is the whole skill of the game, and it is
what the loading screen tells you: *"You can shoot head when zombies stop breathing."*

Your own breathing tells you your health: three hearts is `player_breath_1`, two is
`player_breath_2`, one is `player_breath_3`.

---

## Layout

```
SixthSense.py            entry point
sixthsense/
  paths.py               where the bundle's data lives
  platform/
    openal.py            ctypes binding for OpenAL Soft
    music.py             the two AVAudioPlayer streams
    runloop.py           NSTimer and performSelector:afterDelay:
    defaults.py          NSUserDefaults
    keymap.py            PORT ADDITION: bindings, including chords
    speech.py            PORT ADDITION: NVDA, Prism or a Windows voice, for what no WAV says
    volume.py            PORT ADDITION: the volume knobs, in decibels
  game/
    app_delegate.py      global state + the sound dispatch
    oal_playback.py      oalPlayback
    make_maps.py         MakeMaps
    moving_accelerometer.py
    player_control.py    weapon_control.py    monster_control.py
    sound_list_control.py
    stage_1_e.py         Stage_1_E, including the pause and result panel
    stage_tutorial.py    Stage_Tutorial
    main_controller.py   MainController - the menu
    intro.py             startIntroPage - the splash and the warning
    blind_screen.py      the shape every self-voiced screen shares
    store.py             the shop: front menu, weapon list, weapon page
    inventory.py         the eight slots, and equipping them
  ui/
    input.py             the keyboard, resolved through the keymap
    keybind_screen.py    the self-voiced rebinding screen (F1)
    menu_input.py        Up/Down/Enter for the menu
    screen_input.py      ...and for the shop and the inventory
game/                    the original app bundle, its sounds sorted into folders (see below)
vendor/                  OpenAL Soft and NVDA's controller client, with their licenses
analysis/                the binary, and the disassembly this was written from
tools/                   the Mach-O / Objective-C / Thumb tooling that produced it
docs/                    GAME_STRUCTURE.md, DIVERGENCES.md, PORTING_STATUS.md
tests/                   the tests, and level_tester.py for starting at any level
compiler.py              builds the game into an executable with PyInstaller
requirements.txt         the two packages it needs
```

`docs/GAME_STRUCTURE.md` is the useful one: it is the mechanism of the game as read out
of the binary, with addresses.

### `game/` — the original's data

`game/` holds the contents of `Payload/sixsense.app` as the IPA shipped them: the binary
plists, the three map layers, the nibs, the PNGs, `Info.plist`, `iTunesArtwork`, the
Facebook resource bundle, `_CodeSignature/` and the `sixsense` binary itself. The port
never writes to it — the save file lives in `%APPDATA%\SixthSense`.

The one thing that is not where the original kept it is the sounds. The original keeps
its 269 WAVs in one flat folder; here every sound the game uses sits in
`game/sounds/used/`, sorted into folders by what it is — zombies, weapons, menus, the
tutorial and so on — and each keeps its original file name, so `SoundList.plist` still
finds it. Each file was matched to the original by comparing its audio. They came back
through a compressed copy, so they carry faint codec noise, but they are 16-bit PCM,
like the originals; six are the original files themselves. `game/sounds/unused/` holds
26 files that are not the original's own, which the game never uses.
`docs/DIVERGENCES.md` has the details.

The port reads from there, so the data it runs on is the original's data. `--game PATH`
(or `SIXTHSENSE_GAME`) points at another copy; an untouched original bundle, with its
WAVs all in one folder, works too.

`analysis/bin/sixsense_armv7` is the thin armv7 slice cut out of `game/sixsense`, which
is what `tools/` disassembles. The game never reads it; it is there so the analysis is
reproducible without the IPA.

## Tests

```bash
python tests/test_data.py       # the port's tables against game/
python tests/test_paths.py      # where the game finds its sounds, plists and maps
python tests/test_gameplay.py   # a headless playthrough (~35 s, opens the audio device)
python tests/test_input.py      # the keyboard mapping
python tests/test_tutorial.py   # the ten tutorial beats
python tests/test_menu.py       # the menu rows and the coin economy
python tests/test_digits.py     # numbers spoken digit by digit, in the right order
python tests/test_pause.py      # the pause and result panel
python tests/test_store.py      # the shop, buying, and the inventory
python tests/test_intro.py      # the splash, the warning and skipping them
python tests/test_speech.py     # who speaks what no WAV covers (stand-ins, silent)
python tests/test_volume.py     # the decibel knobs, and the binary's mix left alone
python tests/test_monster_sound.py  # zombie sounds read back from OpenAL (audio device)
python tests/test_focus.py      # switching away from the window pauses a stage
```

`test_data` checks the port against the original data rather than against itself: the
map shape and the action layer, every weapon's stats, every monster type's kind and
lane, that every sound number the monster tables use resolves to a WAV in
`game/sounds/used`, and that everything meant to be positional is mono (OpenAL will not
spatialise stereo, and the game relies on that).

**For now, the tests write to your real save** in `%APPDATA%\SixthSense`, and
`test_gameplay` plays audio. Until that is fixed, run them with `APPDATA` pointed at a
scratch folder, and with `ALSOFT_DRIVERS=null` so nothing is heard.

### Starting at any level

`tests/level_tester.py` is not a test. It opens the real game at the level you choose,
so a bug on level 3 does not take three levels of play to reach. Opened on its own, it
asks for the level, the area (cave, forest or rain) and whether to start just before
the boss. It also takes them on the command line:

```bash
python tests/level_tester.py                    # asks
python tests/level_tester.py 2                  # level 2
python tests/level_tester.py 3 --mode forest    # level 3, in the forest
python tests/level_tester.py 2 --boss           # level 2, two steps before the siren
python tests/level_tester.py 1 --row 300        # level 1, from row 300 of the corridor
```

A level is what walking there would give you: monsters 1.5 times tougher and faster per
level, one more of them out at a time, and the area alternating between the cave and
the forest. It plays on its own save in `%APPDATA%\SixthSense\level_tester`, so your
own save is never touched, and it copies your key bindings in each time it starts.

## Where this came from

The armv7 slice of `sixsense` ships **unencrypted** (`LC_ENCRYPTION_INFO
cryptid = 0`), so the whole thing could be read directly. The
tooling in `tools/` parses the Mach-O, walks the Objective-C metadata (67 classes,
~2900 methods, ivar offsets, selector and class references, the dyld bind table), and
disassembles Thumb-2 with selector, string, ivar and float-literal resolution. Its
output is in `analysis/disasm/`; every ported method carries the address it came from.

## The tutorial

Ten beats, in the original's order. Five teach the lanes as clock positions — 9, 10:30,
12, 1:30, 3 — which is where the A/Q/W/E/D keys come from; one teaches 6 o'clock, which
is the reload; the rest teach the weapon switch, the grab and the three-finger tap. Each
beat plays its instruction, sends in the monster it is about, and nags once a second
until you do it. When the last one lands the walk starts and the real game begins.

## Status

The opening, the menu, the tutorial, the stage, the monsters, the weapons, the
fighting, the pause and result panel, the shop and the inventory are ported, along with
the whole audio path. What is left is the weapon test range behind the shop's Try
button (`Stage_1_TEST`, which is its own stage rather than a variant of the real one),
the ambient sound layer the shipped map does not use, and everything that needed the
publisher's server or the App Store. `docs/PORTING_STATUS.md` has the full list, and
`docs/DIVERGENCES.md` has the original's own bugs that the port keeps.

## Credits

**[lbk2907](https://github.com/lbk2907)** started the port. They found that the iOS
binary ships unencrypted, extracted it, and wrote the tooling in `tools/` that reads it
and the disassembly in `analysis/`. Then they wrote the Python port itself from that
disassembly, method by method, along with its docs, its tests and the first version of
this README.

Contributors, in the order they joined:

- **[tsatria03](https://github.com/tsatria03)** publishes and maintains the repository,
  and carries the port on. That has meant sorting the sounds into folders, adapting the
  build script to the game, fixing gameplay bugs, and adding speech through
  Prism for screen readers other than NVDA.
- **[tunmi13productions](https://github.com/tunmi13productions)** fixed the coin
  economy, and the order spoken numbers are read in.

SixthSense itself is Bitbee's game, from 2013.

## Licence

The port's code is in `LICENSE`. Everything under `game/`, and the binary and
disassembly under `analysis/`, are Bitbee's and are not covered by it.

The third-party pieces keep their own licenses. OpenAL Soft's and NVDA's controller
client's sit beside their DLLs in `vendor/`, and a build copies them, along with
Prism's and pygame's, into a `licenses` folder beside the game.
