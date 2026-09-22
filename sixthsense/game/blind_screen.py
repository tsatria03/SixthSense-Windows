"""The shape every blind-mode screen in this game shares.

``MainController``, ``Stage_1_E``'s result panel, the shop, the weapon pages and the
inventory are all built the same way (see ``docs/GAME_STRUCTURE.md`` §8):

    -[X selectTapPointSoundStart]   maps the finger's Y to one of N bands, stores the
                                    band in ``selectMenu``, plays that row's WAV and
                                    sometimes schedules a number to be read behind it
    -[X tapCount]                   a ``tbb`` table on ``selectMenu - 1``: what a
                                    double tap on the row does
    -[X StopElseSpeak]              stop every WAV this screen can say, and cancel any
                                    reader still queued

Each band guards on its own flag (``go_back_flag``, ``weapon_flag``, ...) so that a
finger resting on a row does not say it twice.  A keyboard moves between rows one event
at a time, so the move is the guard, and Up/Down/Enter stand in for drag-and-double-tap
exactly as they do in ``MainController``.

Nothing about the rows, their order, their sounds or what they do is invented here;
every subclass carries the addresses it was read from.
"""
from __future__ import annotations

import logging

from ..platform.defaults import UserDefaults
from ..platform.runloop import RunLoop
from .app_delegate import AppDelegate

log = logging.getLogger('screen')

#: Every one of these screens plays its labels at this gain.
UI_GAIN = 0.2

#: ui_select, the click every button makes.
SOUND_UI_SELECT = 10

#: How far behind a label its number is read.  0x3097c in Stage_1_E, and the same
#: constant in every other screen's selectTapPointSoundStart.
READ_DELAY = 2.0


class BlindScreen:
    """One screen of the blind-mode UI, driven by Up / Down / Enter."""

    #: row numbers in the order they sit on the screen, top to bottom
    ROWS = ()
    #: row -> the SoundList entry that names it
    ROW_SOUND = {}
    #: row -> the method to run READ_DELAY behind the label
    ROW_READER = {}
    #: everything StopElseSpeak silences
    STOP_SOUNDS = ()
    #: PORT ADDITION: the recording that names this screen, played as it opens so the
    #: player knows which one they are on.  None keeps the original's silence.
    TITLE_SOUND = None
    #: how long the name is given before row 1 is read behind it.  The naming recordings
    #: run about a second; moving cancels the wait, so it is only ever heard alone.
    TITLE_DELAY = 1.5

    def __init__(self, speech=None):
        self.app = AppDelegate.shared()
        self.defaults = UserDefaults.standardUserDefaults()
        self.speech = speech
        self.selectMenu = 0
        self.next_screen = None       # ('name', arg) for a push
        self.done = False             # popViewControllerAnimated:
        self.running = True

    # ---- the sound the screen makes --------------------------------------
    def play(self, sound, gain=UI_GAIN):
        self.app.playSound_Gain_Pos_z_reprats_(sound, gain, (0.0, 0.0), 0, False)

    def ui_select(self):
        self.play(SOUND_UI_SELECT)

    def say(self, text):
        """For a row the port cannot carry out - the two in-app-purchase screens, the
        publisher's server and the weapon test range.  ``docs/DIVERGENCES.md`` says
        why this speaks."""
        log.info('%s', text)
        if self.speech is None:
            from ..platform.speech import Speech
            self.speech = Speech.shared()
        self.speech.speak(text)

    # -[X StopElseSpeak]
    def StopElseSpeak(self):
        # Every row's own name WAV, stopped unconditionally rather than by a
        # hand-kept list, the way MainController stops all of ROWS - so a row
        # whose sound a STOP_SOUNDS tuple leaves out (as row 6's did here) can
        # never again keep talking over whatever the player moves to next.
        for row in self.rows():
            sound = self.row_sound(row)
            if sound:
                self.app.stopSoundBufNumber_(sound)
        for num in self.STOP_SOUNDS:
            if num:
                self.app.stopSoundBufNumber_(num)
        self.app.readStop()
        if self.speech is not None:
            self.speech.stop()
        loop = RunLoop.main()
        for sel in set(self.ROW_READER.values()):
            loop.cancelPerform(self, sel)
        loop.cancelPerform(self, 'read_first_row')      # the name this screen opened with

    # ---- the rows --------------------------------------------------------
    def rows(self):
        return self.ROWS

    def row_sound(self, row):
        """Overridden where a row's label depends on the screen's state."""
        return self.ROW_SOUND.get(row)

    # -[X selectTapPointSoundStart], one band of it
    def select(self, row):
        self.selectMenu = row
        self.StopElseSpeak()
        sound = self.row_sound(row)
        if sound:
            self.play(sound)
        reader = self.ROW_READER.get(row)
        if reader is not None:
            RunLoop.main().perform(self, reader, None, READ_DELAY)
        return sound

    def title_sound(self):
        """Which recording names this screen, or None.  Overridden per screen."""
        return self.TITLE_SOUND

    # -[X startRead] 0x1d124 / 0x13a78 / 0x1a0ec / ...
    def startRead(self):
        """What a screen does as it comes up.

        The original stops everything and plays row 1, which on every one of these
        screens is Back, sound 13 (``-[mainStoreController startRead]`` 0x1d124 is three
        lines and 13 is the only sound in it).  On a phone the screen itself was the
        answer to "where am I": the player could feel their way down it.  Here four
        screens in a row open by saying "back button" and nothing else.

        **DIVERGENCE:** the screen says its own name first, out of the original's own
        recordings - "Store Button", "Weapon shop Button", "Inventory Button", or the
        weapon's name on a weapon's page - and then reads row 1 a moment later.  Moving
        or choosing anything cancels the wait, so it never talks over the player.
        """
        first = self.ROWS[0] if self.ROWS else 0
        title = self.title_sound()
        if not title:
            return self.select(first)
        self.selectMenu = first
        self.StopElseSpeak()
        self.play(title)
        RunLoop.main().perform(self, 'read_first_row', None, self.TITLE_DELAY)
        return title

    def read_first_row(self, *_):
        """Row 1, a moment behind the screen's name."""
        self.select(self.ROWS[0] if self.ROWS else 0)

    def move(self, step):
        rows = self.rows()
        if not rows:
            return None
        if self.selectMenu in rows:
            row = rows[(rows.index(self.selectMenu) + step) % len(rows)]
        else:
            row = rows[0] if step > 0 else rows[-1]
        self.select(row)
        return row

    # -[X tapCount]
    def activate(self):
        """Subclasses implement the ``tbb`` table."""
        raise NotImplementedError

    # ---- navigation ------------------------------------------------------
    def goBackAction_(self, *_):
        """-[X goBackAction:] - ui_select, then popViewControllerAnimated:."""
        self.ui_select()
        self.done = True
        return True

    def push(self, name, arg=None):
        self.next_screen = (name, arg)

    def teardown(self):
        self.StopElseSpeak()
        RunLoop.main().cancelPerform(self)
        self.running = False
