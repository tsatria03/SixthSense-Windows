# SixthSense-Windows

A Python port of **SixthSense** (`kr.co.bitbee.sixsense` 1.2, Bitbee, 2013), an iPhone
audio game for blind players: you walk down a corridor in the dark and shoot what you
hear coming.

The port runs off the original app bundle's own data — the binary plists and the three
map layers, unconverted, and the original's recorded sounds, sorted into folders under
their own names — and drives OpenAL Soft with the same calls and the same values the
iOS build used. Nothing about the game's numbers was invented here;
where the original's data is malformed, the port reproduces the malformed result and
`aidocks/DIVERGENCES.md` says why.

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

`vendor/nvda/nvdaControllerClient64.dll` ships too, so NVDA can speak what no recording
covers: the key-binding screen and a few messages. With voice over on, the main menu's
default, the game speaks through its own recorded WAVs and needs no screen reader. With
voice over off, your screen reader reads the menus, the shop, the inventory and the
pause and result panel instead, and names the keys during the tutorial.

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

That opens on the publisher's logo and its sound, then the splash and the warning, as
the original does, and then the menu. Enter skips the logo, and Escape skips straight
to the menu. The opening screen's third row tells the game's story, which the original
recorded but never played.
**Up** and **Down** walk the six rows and **Enter** chooses; each row reads itself
with the game's own recording. A game costs a coin. A new player starts with ten, and
coins come back one every thirty minutes up to five, even while the game is closed,
which is what the original does too.

The **Store** row opens the shop — the weapon list, a page per weapon with its four
numbers read aloud, and the inventory, where what you equip is what the stage hands
you. Gold comes out of your runs: twelve a kill and two a headshot.

`--stage` and `--tutorial` skip the menu, `--no-intro` skips the opening. Other
options: `--no-window` (headless), `--game DIR` (another copy of the bundle), `-v`.

`--debug` is for trying things out: a zombie that reaches you just dies, nothing takes a heart and
you cannot die, and no kill, headshot, score or gold counts. A stage says "Debug mode"
as it starts. Tab reaches every weapon, bought or not, and no gun or grenade runs out.
Starting or restarting a game needs no coin and spends none.
Seven keys are added, which the F1 screen lists and rebinds: F2 next section of the
corridor, Shift+F2 next level (after 8, back to 1), F5 spawn a zombie in the lane you
last attacked, Shift+F5 choose what F5 spawns, F6 hold the zombies in place, F7 let
zombies hit you without taking a heart, F11 say where they are.

Until you have finished the tutorial once, Start Game spends a coin and takes you to the
tutorial first, as the original does; pressing P at its end counts 3, 2, 1 and starts
the real game. Finished once, by either route, Start Game goes straight into the game.
`--skip-tutorial` writes the key the tutorial writes, if you would rather skip it.

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
| **Tab** / **Shift+Tab** | next / previous weapon |
| **Space** | shake free when the animal zombie grabs you: one to five separate presses, a new number each grab, and holding Space down counts as one |
| **P** | pause — the original's stop button, which has no key of its own |
| **F1** | key bindings — see below |
| **Esc** | pause a stage, and resume it from the pause panel; back to the menu from the tutorial; quit from the menu |

When the pause or result panel is up, the keyboard belongs to it: **Up** and **Down**
walk its rows, **Enter** chooses. The same goes for the menu, the shop and the
inventory. With voice over turned off, **Home** and **End** also go to the first row and
the last, and **Left** and **Right** move to the previous row and the next, like
VoiceOver's flicks. You can pause as often as you like: continue and restart both let the next
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
    stage_1_test.py      Stage_1_TEST - the weapon test range behind Try
    main_controller.py   MainController - the menu
    intro.py             startIntroPage - the logo, the splash, the warning and the story
    blind_screen.py      the shape every self-voiced screen shares
    store.py             the shop: front menu, weapon list, weapon page
    inventory.py         the eight slots, and equipping them
    debug.py             PORT ADDITION: the --debug keys
  ui/
    input.py             the keyboard, resolved through the keymap
    keybind_screen.py    the self-voiced rebinding screen (F1)
    menu_input.py        Up/Down/Enter for the menu
    screen_input.py      ...and for the shop and the inventory
    focus.py             switching away from the window pauses a stage
game/                    the original app bundle, its sounds sorted into folders (see below)
vendor/                  OpenAL Soft and NVDA's controller client, with their licenses
analysis/                the binary, and the disassembly this was written from
tools/                   the Mach-O / Objective-C / Thumb tooling that produced it
aidocks/                 GAME_STRUCTURE.md, DIVERGENCES.md, PORTING_STATUS.md, and
                         the notes for AI-assisted work (see CLAUDE.md)
docks/                   readme.txt, changelog.txt and todo list.txt, which ship in a docks folder
tests/case/              the tests, one plain script each
tests/interact/          level_chooser.py and tutorial_chooser.py, which start the real
                         game at any level, or the tutorial at any lesson, to play
compiler.py              builds the game with PyInstaller
releaser.py              sets the version, files the changelog, builds, zips, tags and uploads a release
requirements.txt         the two packages it needs
```

`aidocks/GAME_STRUCTURE.md` is the useful one: it is the mechanism of the game as read out
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
like the originals; six are the original files themselves. `game/sounds/used/` holds
only what the game plays, 236 files. `game/sounds/unused/` holds 126 the game never
plays: the original's sounds for things the port leaves out, such as the ranking and
the coin store, extra copies, the sounds that are not the original's own, and a blooper.
One entry of `SoundList.plist` follows a renamed file.
`aidocks/DIVERGENCES.md` has the details.

The port reads from there, so the data it runs on is the original's data. `--game PATH`
(or `SIXTHSENSE_GAME`) points at another copy; an untouched original bundle, with its
WAVs all in one folder, works too.

`analysis/bin/sixsense_armv7` is the thin armv7 slice cut out of `game/sixsense`, which
is what `tools/` disassembles. The game never reads it; it is there so the analysis is
reproducible without the IPA.

## Tests

`tests/` has two folders:

- **`tests/case/`** holds the tests: 22 plain scripts, each checking one part of the
  game against the original and printing `ok` or `FAIL` for every check, then a total.
  Run any of them on its own; there is nothing to install beyond what the game needs.
- **`tests/interact/`** holds two tools you play rather than tests: `level_chooser.py`
  and `tutorial_chooser.py`, which open the real game at any level or the tutorial at
  any lesson, for checking something by ear. See "Starting at any level" and "Starting
  the tutorial at any lesson" below.

The tests, one line each:

```bash
python tests/case/data.py           # the port's tables against game/
python tests/case/paths.py          # where the game finds its sounds, plists and maps
python tests/case/gameplay.py       # a headless playthrough (~35 s, opens the audio device)
python tests/case/input.py          # the keyboard mapping
python tests/case/tutorial.py       # the ten tutorial beats
python tests/case/menu.py           # the menu rows and the coin economy
python tests/case/digits.py         # numbers spoken digit by digit, in the right order
python tests/case/pause.py          # the pause and result panel
python tests/case/store.py          # the shop, buying, and the inventory
python tests/case/inventory.py      # equipping through the inventory's screens, step by step
python tests/case/weapon_range.py   # the weapon test range behind the shop's Try button
python tests/case/intro.py          # the logo, the splash, the warning, the story, skipping
python tests/case/speech.py         # who speaks what no WAV covers (stand-ins, silent)
python tests/case/volume.py         # the decibel knobs, and the binary's mix left alone
python tests/case/monster_sound.py  # zombie sounds read back from OpenAL (audio device)
python tests/case/focus.py          # switching away from the window pauses a stage
python tests/case/window.py         # the window's close button and the screen loop
python tests/case/release.py        # the releaser's version, changelog and names (builds nothing)
python tests/case/save.py           # a damaged save is kept and the backup carries on (temp folders only)
python tests/case/music_memory.py   # changing the music and ambience frees the old files (audio device)
python tests/case/audio_device.py   # a lost audio device is reopened (fake device, then OpenAL's null driver)
python tests/case/runloop.py        # timers and delayed calls: once each, in time order, on a fine clock
```

`case/data.py` checks the port against the original data rather than against itself: the
map shape and the action layer, every weapon's stats, every monster type's kind and
lane, that every sound number the monster tables use resolves to a WAV in
`game/sounds/used`, and that everything meant to be positional is mono (OpenAL will not
spatialise stereo, and the game relies on that).

**The tests never touch your save, and make no sound.** Each one imports
`tests/case/_scratch_save.py` first, which points `SIXTHSENSE_USER_DIR` at a throwaway
folder and deletes it afterwards, sets `SIXTHSENSE_SILENT` so nothing is ever sent to your
screen reader or a Windows voice, and sends the audio to OpenAL Soft's null driver with no
window, whatever your shell has set. `case/paths.py` fails if a test file leaves that out.
`_scratch_save.py` is not a test; skip files starting with `_` when running them all.

## Building and releasing

Both scripts open a numbered menu when double-clicked, and wait for Enter at the end.
Building needs PyInstaller (`pip install pyinstaller`); releasing also needs the GitHub
CLI, signed in with `gh auth login`.

`compiler.py` only builds. It never zips and never changes the repository. Everything
lands in `dist\SixthSense`.

- **Folder build:** the game in a folder, with its sounds and data beside the
  executable in `game\`.
- **Single exe** (`--embed`): the sounds and the game's data inside one executable.
  It unpacks them at every launch, so it starts a few seconds slower.

Either way, the readme, the changelog and the todo list go in a `docks` folder beside
the executable, as in the repository, and `VERSION`, the license and the third-party
licenses sit beside it too, where a player can open them. `docks/readme.txt` is the player's own readme: plain text, one sentence a line,
with none of this file's developer parts.

`releaser.py` does the rest. Its full release goes through each step and asks Y or N
before each one:

1. **Check** that everything is committed and pushed, `gh` is signed in, and the
   changelog has between 5 and 100 changes under `unrelease:`. Fewer than 5 do not make
   a release.
2. **Prepare:** `VERSION` becomes today's date and that day's release number, such as
   `26.09.23-1`, and the unreleased lines are filed under it in `docks/changelog.txt`.
3. **Build** with the compiler, as a folder or a single exe. A failed build puts
   `VERSION` and the changelog back.
4. **Zip** `dist\SixthSense` into `dist\SixthSense-Win-26.09.23-1.zip`. It only zips a
   build made for this version.
5. **Commit and push** `VERSION` and `docks/changelog.txt` as "Release 26.09.23-1".
6. **Tag** it `V26.09.23-1`, and push the tag.
7. **Upload** the zip to GitHub as the release "SixthSense V26.09.23-1", with that
   version's changelog lines as its notes.

It never moves or replaces a tag or a release that already exists.

### Starting at any level

`tests/interact/level_chooser.py` is not a test. It opens the real game at the level you choose,
so a bug on level 3 does not take three levels of play to reach. Opened on its own, it
asks for the level, the area (cave, forest or rain) and whether to start just before
the boss. It also takes them on the command line:

```bash
python tests/interact/level_chooser.py                    # asks
python tests/interact/level_chooser.py 2                  # level 2
python tests/interact/level_chooser.py 3 --mode forest    # level 3, in the forest
python tests/interact/level_chooser.py 2 --boss           # level 2, two steps before the siren
python tests/interact/level_chooser.py 1 --row 300        # level 1, from row 300 of the corridor
```

A level is what walking there would give you: monsters 1.5 times tougher and faster per
level, one more of them out at a time, and the area alternating between the cave and
the forest. It plays on its own save in `%APPDATA%\SixthSense\level_chooser`, so your
own save is never touched, and it copies your key bindings in each time it starts.

### Starting the tutorial at any lesson

`tests/interact/tutorial_chooser.py` is not a test either. It opens the real tutorial at the
lesson you choose, with the ending you choose, so neither needs a deleted save or a
replay of the lessons before it. Opened on its own, it asks three things:

- **The ending:** `start`, where P counts 3, 2, 1 into the real game as after a
  first Start, or `menu`, where P goes back to the main menu as from the Tutorial
  button.
- **The lesson,** 1 to 10: the five clock positions, the stronger zombie, reloading,
  changing weapon, shaking off the animal zombie, and ending the tutorial with P.
- **Voice over on or off.** The recordings play either way; with it off, your screen
  reader also names the keys for each lesson.

```bash
python tests/interact/tutorial_chooser.py                              # asks
python tests/interact/tutorial_chooser.py --lesson 9                   # the animal zombie
python tests/interact/tutorial_chooser.py --ending start --lesson 10   # P, then into the game
python tests/interact/tutorial_chooser.py --voice off                  # with the key hints
```

The lessons before the one you choose count as done, so the tutorial carries on from
there as it would have. It plays on its own save in
`%APPDATA%\SixthSense\tutorial_chooser`, so your own save is never touched.

## Where this came from

The armv7 slice of `sixsense` ships **unencrypted** (`LC_ENCRYPTION_INFO
cryptid = 0`), so the whole thing could be read directly. The
tooling in `tools/` parses the Mach-O, walks the Objective-C metadata (67 classes,
~2900 methods, ivar offsets, selector and class references, the dyld bind table), and
disassembles Thumb-2 with selector, string, ivar and float-literal resolution. Its
output is in `analysis/disasm/`; every ported method carries the address it came from.

## The tutorial

Ten lessons, in the original's order. Five teach the lanes as clock positions — 9,
10:30, 12, 1:30, 3 — which is where the A/Q/W/E/D keys come from; one sends a stronger
zombie; one teaches 6 o'clock, which is the reload; the rest teach the weapon switch,
shaking off the animal zombie, and ending the tutorial, the original's three-finger tap,
which is **P** here. Each lesson plays its instruction and sends in the monster it is
about, and each only counts once the ones before it are done.

P ends the tutorial once the first eight lessons are done. Reached from Start Game on
your first go, it then counts 3, 2, 1 and the real game begins; from the Tutorial row,
it goes back to the main menu.

## Status

The opening, the menu, the tutorial, the stage, the monsters, the weapons, the
fighting, the pause and result panel, the shop and the inventory are ported, along with
the whole audio path, and so is the weapon test range behind the shop's Try button
(`Stage_1_TEST`). What is left is the ambient sound layer the shipped map does not use, and everything that needed the
publisher's server or the App Store. `aidocks/PORTING_STATUS.md` has the full list, and
`aidocks/DIVERGENCES.md` has the original's own bugs that the port keeps.

## Credits

**[lbk2907](https://github.com/lbk2907)** started the port. They found that the iOS
binary ships unencrypted, extracted it, and wrote the tooling in `tools/` that reads it
and the disassembly in `analysis/`. Then they wrote the Python port itself from that
disassembly, method by method, along with its docs, its tests and the first version of
this README.

Contributors, in the order they joined:

- **[tsatria03](https://github.com/tsatria03)** publishes and maintains the repository,
  and carries the port on:
  - **Publishing:** put the port on GitHub, restored this README, and keeps the
    license, the credits, the changelog and the todo list. Made the first releases,
    26.09.23-1 and 26.09.23-2, and gave players a readme of their own, in a `docks`
    folder beside the game.
  - **Sounds:** sorted every sound into folders under its original name, then set apart
    every sound the game never plays, and found the real "main menu button" recording.
  - **The original, checked again:** the publisher's logo at launch, the story on the
    opening screen's third row (tunmi13productions' idea), "paused" when pausing, the tutorial's reload lesson
    saying its instruction once, the weapon change sound at the original's volume,
    gunshots and empty clicks placed where the original places them, a grenade scoring
    every zombie it hurts, a zombie's blow heard in the middle of your head, the coin
    row's pauses, and the menu's missing clicks.
  - **Speech and keys:** speech through Prism for every screen reader and a Windows
    voice. Rebinding keys that works, a reset that asks first, and rolling from one
    attack key to the next.
  - **The mix:** the music and ambience as quiet as the original's, loud gunshots, the
    kill sound, the rain that keeps falling, silent exits, the menu music on decibel
    knobs, carrying on where it was, and no longer filling memory.
  - **Play:** weapons that keep their own ammo, the girl and the woman zombie walking
    straight in along their lanes, the woman's growl timed by her distance, and the
    turn keys removed.
  - **The menus and the panel:** the shop refusing weapons you have not bought, each
    screen saying its name, Home, End, Left and Right with voice over off, the score
    row reading your score, result rows that reread themselves, the coin store and
    purchase all weapons rows removed, a coin clock that starts again when a save has
    none, and unequipped starting weapons that stay unequipped.
  - **Debug mode:** its second set of keys, a tutorial it can finish, and F7 in the
    window's list of keys.
  - **Tools:** the build script with its single-exe build, the releaser and its
    five-to-a-hundred rule, the level and tutorial choosers, the tests folder split into
    `case` and `interact`, tests that never touch your save or make a sound, and a run
    loop that keeps time in order.
- **[tunmi13productions](https://github.com/tunmi13productions)** has fixed and ported
  a great deal of the game:
  - the coin economy, and the order spoken numbers are read in
  - zombies that move in their lanes, the boss and the end of each level, the girl who
    heals you and the woman zombie
  - reloading and headshots as in the original, with shots that take time to land
  - pausing as often as you like, and pausing when the window loses focus
  - pausing that pauses the ambience and the music, and holds a level change until you
    continue
  - the screen reader mode for the menus and the result panel, and Escape as pause
  - debug mode
  - the weapon test range behind the shop's Try button
  - the tutorial's order, its ending with P, and its spoken key hints
  - shaking free in one to five presses
  - stopping recordings from talking over each other
  - removing the ranking, Game Center and restore purchases rows, and quitting from the
    window's close button on any screen
  - the voice over row saying what it does, the coin row and the earphone warning no
    longer talking over other rows, and "no coin" said alone
  - a damaged save kept aside, with the game carrying on from a backup
  - the sound following your audio device when headphones are unplugged or plugged in
  - saying aloud why the game could not start, or stopped
  - the bloopers folder

SixthSense itself is Bitbee's game, from 2013.

## Licence

The port's code is in `LICENSE`. Everything under `game/`, and the binary and
disassembly under `analysis/`, are Bitbee's and are not covered by it.

The third-party pieces keep their own licenses. OpenAL Soft's and NVDA's controller
client's sit beside their DLLs in `vendor/`, and a build copies them, along with
Prism's and pygame's, into a `licenses` folder beside the game.
