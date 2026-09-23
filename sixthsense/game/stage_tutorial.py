"""``Stage_Tutorial`` - the ten scripted beats that teach the game.

``Stage_Tutorial`` (0x7d7cc..0x8d2b1) is a near-copy of ``Stage_1_E``: 252 methods
against 262, and only ``testWeapon``/``setTestWeapon:`` are its own.  What differs is
that the walk never starts - ``MapInitInBundle`` (0x7ddcc) loads the same three map
files, then calls ``tutorialOne`` directly and arms

    checkTutorialTimer = [NSTimer scheduledTimerWithTimeInterval:1.0 target:self
                             selector:@selector(CheckTutorial) userInfo:nil repeats:YES];

and the player stands still until every beat is done.

Each beat is five methods in the original (``tutorialOne``, ``...SoundStop``,
``...End``, ``...Restart``, ``...RestartFinger``), spelled out ten times over.  The
shape is always the same:

    tutorialN            play the instruction; hide every hint; show this beat's
                         finger and arrow
    tutorialNSoundStop   9.5 s later (6.5 for beat eight): stop the instruction and
                         spawn the monster the beat is about, if it has one
    CheckTutorial        every second, call ``...End`` on the first *unfinished* beat
    tutorialNEnd         if the flag is still clear, slide the finger back and
                         re-prompt through ``...RestartFinger`` / ``...Restart``

So the tutorial nags once a second until you do the thing, then moves on by itself.

What the beats teach, and what marks each one done:

    beat        prompt                                  spawns   done by
    One    275  "if you make your finger 9"     9:00    type 1   killing it
    Two    276  "if you make your finger 10_30" 10:30   type 2   killing it
    Three  277  "if you make your finger 12"    12:00   type 3   killing it
    Four   278  "if you make your finger 1_30"  1:30    type 4   killing it
    Five   279  "if you make your finger 3"     3:00    type 5   killing it
    Five+  361  "stamina of zomblies increasingly"      type 63  killing it
    Six    280  "if you make your finger 6"     6:00    -        reloading
    Seven  281  "if you tab the screen with two"        -        changing weapon
    Eight  282  "if an animal zombie approaches"        type 73  shaking free
    Nine   284  "if you tab the screen using three finger twice"  -  the stop button

The clock positions *are* the five lanes, which is where the port's A/Q/W/E/D keys
come from, and beat six is the reload swipe (see ``Stage_1_E._lane_for_angle``).

Killing sets the flag by the dead monster's lane: ``-[Stage_Tutorial MonsterDamage]``
at 0x8a250 tests ``MovingType`` 1..5 and sets ``tutorialOne``..``tutorialFive``.

Beat Nine is the stop button itself, the three-finger double tap, which is P here.
``StopPlayAction:`` (0x83804) does nothing in the tutorial until beats One to Eight are
done (0x83926..0x8393c).  Then it ends the tutorial: ``TUTORIAL = 1``, ``tutorial
success`` (327), and 3.05 s later ``tutorialEnd:``.

Where that leads depends on how the tutorial was reached:

* From the Tutorial row, ``-[Stage_Tutorial tutorialEnd:]`` (0x83738) is
  ``GameEndAction:``, back to the menu.
* From a first Start, the original ran the tutorial inside ``Stage_1_E``, whose
  ``tutorialEnd:`` (0x33bec) reads 3, 2, 1 (``TTSNumber:321 type:1``) and 6.0 s later
  calls ``tutorialEndGameStart:`` (0x33d40): ``zombies are coming`` (328) and the 1.0 s
  walk timer - the real game, from the same standing start.  The port runs both in
  this class, and ``first_run`` picks the ending.

The port drives the ten beats from a table instead of ten copies of five methods.
Nothing about the behaviour changes; see docs/DIVERGENCES.md.
"""
from __future__ import annotations

import logging

from ..platform.defaults import UserDefaults
from ..platform.keymap import KeyMap, binding_text
from ..platform.runloop import RunLoop
from .stage_1_e import Stage_1_E

log = logging.getLogger('tutorial')

# -[Stage_Tutorial StopPlayAction:] 0x83926..0x8393c - the stop button is ignored
# until these are done.  FiveHalf and Nine are not tested.
STOP_NEEDS = ('One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight')
ENDING_DELAY = 3.05                 # 0x83ab4: 0x4008666660000000
COUNTDOWN = 321                     # 0x33c00: TTSNumber:321 type:1, "3, 2, 1"
COUNTDOWN_SECONDS = 6.0             # 0x33c28: 0x4018000000000000

# name, prompt sound, seconds before SoundStop, the monster it spawns (or None)
BEATS = [
    ('One', 275, 9.5, 1),
    ('Two', 276, 9.5, 2),
    ('Three', 277, 9.5, 3),
    ('Four', 278, 9.5, 4),
    ('Five', 279, 9.5, 5),
    ('FiveHalf', 361, 9.5, 63),
    ('Six', 280, 9.5, None),
    ('Seven', 281, 9.5, None),
    ('Eight', 282, 6.5, 73),
    ('Nine', 284, 9.5, None),
]
BEAT_NAMES = [b[0] for b in BEATS]

#: PORT ADDITION: with voice over off, what the screen reader says once a beat's
#: recording has finished, naming the player's own keys for the gesture it teaches.
#: FiveHalf teaches no new gesture, so it has none.
KEY_HINTS = {
    'One': ('lane1', "Press {} to shoot toward 9 o'clock."),
    'Two': ('lane2', 'Press {} to shoot toward 10:30.'),
    'Three': ('lane3', "Press {} to shoot toward 12 o'clock."),
    'Four': ('lane4', 'Press {} to shoot toward 1:30.'),
    'Five': ('lane5', "Press {} to shoot toward 3 o'clock."),
    'Six': ('reload', 'Press {} to reload.'),
    'Seven': ('next_weapon', 'Press {} to change to the next weapon.'),
    'Eight': ('shake', 'Press {} a few times to shake the zombie off.'),
    'Nine': ('pause', 'Press {} to end the tutorial.'),
}

_SIDES = {'left': 'right', 'right': 'left'}
_SIDED = ('shift', 'ctrl', 'alt')


def _merge_sides(bindings):
    """Either Shift does, so a chord bound with Left Shift and again with Right Shift
    is said once, as "Shift".  Control and Alt likewise."""
    def split(k):
        side, _, key = k.partition(' ')
        return (side, key) if side in _SIDES and key in _SIDED else (None, k)

    def plain(b):
        return tuple(split(k)[1] for k in b)

    def mirror(b):
        return tuple(k if split(k)[0] is None else _SIDES[split(k)[0]] + ' ' + split(k)[1]
                     for k in b)

    return [plain(b) if mirror(b) != b and mirror(b) in bindings else b
            for b in bindings]


SOUND_TUTORIAL_SUCCESS = 327        # 'tutorial success'
SOUND_ZOMBIES_COMING = 328          # 'zombies are coming'

# -[Stage_Tutorial MonsterDamage] 0x8a250 - a kill in lane N finishes beat N.
LANE_BEAT = {1: 'One', 2: 'Two', 3: 'Three', 4: 'Four', 5: 'Five'}


class Stage_Tutorial(Stage_1_E):
    """The tutorial run.  Same stage, same monsters, no walking until it is over."""

    #: Escape leaves for the menu here instead of pausing: the stop button skips the
    #: tutorial (``tutorial_skip``), so it cannot stand in for a pause.
    ESCAPE_LEAVES = True

    def __init__(self, first_run=False):
        super().__init__()
        #: Reached from a first Start, which spent a coin: the ending counts down into
        #: the real game.  From the Tutorial row it goes back to the menu.
        self.first_run = first_run
        self.ending = False                   # between P and the menu or the game
        self.checkTutorialTimer = None
        self.tutorialTimer = None
        self.beat_done = {n: False for n in BEAT_NAMES}
        self.beat_flag = {n: False for n in BEAT_NAMES}   # the oneFlag..nineFlag pair
        self.current_beat = None
        self.finished = False
        self.warn_if_not_walking = False      # standing still is the point here

    # ---- the flags, under the names the original gives them ---------------
    def __getattr__(self, name):
        if name.startswith('tutorial') and name[8:] in BEAT_NAMES:
            return self.__dict__['beat_done'][name[8:]]
        raise AttributeError(name)

    # =============================================================== loading
    # -[Stage_Tutorial MapInitInBundle] 0x7ddcc
    def MapInitInBundle(self):
        # 0x7cfd8: the original forces isTutorial to 0 here, since a tutorial run
        # is never "already finished" no matter what the save says. Without this,
        # replaying the tutorial from the menu with TUTORIAL already "1" reads as
        # finished: the parent (below) starts the walk timer instead of standing
        # still, and StopPlayAction_ (P) runs the ordinary pause instead of
        # tutorial_skip, since isTutorial is what it branches on.
        self.isTutorial = 0
        super().MapInitInBundle()
        if self.MotionSamplingTimer is not None and self.MotionSamplingTimer.isValid():
            self.MotionSamplingTimer.invalidate()
        self.MotionSamplingTimer = None

        # -[Stage_1_E viewDidLoad] already held MapInitInBundle back by
        # LOADING_SECONDS, so Now Loading has had time to finish by the time this
        # runs - beat One can start right away.
        self.tutorial_beat('One')                       # 0x7e2fa, called directly
        self.checkTutorialTimer = RunLoop.main().scheduledTimer(
            1.0, self, 'CheckTutorial', None, True)     # 0x7e338

    # ================================================================ beats
    def _beat(self, name):
        return BEATS[BEAT_NAMES.index(name)]

    # -[Stage_Tutorial tutorialN] - play the instruction, show the hint
    def tutorial_beat(self, name):
        _n, sound, delay, _spawn = self._beat(name)
        self.current_beat = name
        self.beat_flag[name] = False           # the prompt is playing again
        self.app.playSound_Gain_Pos_z_reprats_(sound, 0.2, (0.0, 0.0), 0, False)
        RunLoop.main().cancelPerform(self, 'tutorial_sound_stop')
        RunLoop.main().perform(self, 'tutorial_sound_stop', name, delay)
        self.tutorialHiddenView()
        log.info('tutorial %s: %s', name, self.app.returnFileName_(sound))

    # -[Stage_Tutorial tutorialNSoundStop] - stop the prompt, send in the monster
    def tutorial_sound_stop(self, name=None):
        name = name or self.current_beat
        if name is None:
            return
        _n, sound, _delay, spawn = self._beat(name)
        if name == 'Eight':
            # 0x8e1a8: the animal zombie is not to be shot; it is there to grab you.
            self.noAtt = True
        self.app.stopSoundBufNumber_(sound)
        self.beat_flag[name] = True            # 0x8cb4a: the prompt has finished
        hint = self.key_hint(name)
        if hint is not None:
            self._say(hint)
        if spawn is not None:
            self.MonsterInit_(spawn)

    def key_hint(self, name):
        """PORT ADDITION: the keys for this beat's gesture, with voice over off.  Every
        recording ends before its SoundStop, so the hint never talks over it."""
        if not self.app.screen_reader or name not in KEY_HINTS:
            return None
        action, text = KEY_HINTS[name]
        keys = []
        for b in _merge_sides(KeyMap.shared().bindings.get(action, [])):
            if binding_text(b) not in keys:
                keys.append(binding_text(b))
        if not keys:
            return None
        if len(keys) > 2:
            keys = [', '.join(keys[:-1]) + ',', keys[-1]]
        return text.format(' or '.join(keys))

    # -[Stage_Tutorial CheckTutorial] 0x8c678 - once a second
    def CheckTutorial(self, timer=None):
        """Nag about the first unfinished beat, then let any monster that has reached
        you act, unless one is already holding you (0x8c754..0x8c770).  That last step
        is the only place anything reaches you in the tutorial, since the stage's own
        clock does not run."""
        if self.finished:
            return
        for name in BEAT_NAMES:
            if not self.beat_done[name]:
                self.tutorial_beat_end(name)
                break
        if not self.isShake:
            self.MonsterAttPlayer()

    # -[Stage_Tutorial tutorialNEnd] - still not done, so prompt again
    def tutorial_beat_end(self, name):
        if self.beat_done[name]:               # 0x8cb76
            return
        if self.current_beat == name and not self.beat_flag[name]:
            return                             # the instruction is still playing
        if self.MonsterBuffer:
            return                             # its monster is still out there
        if self.current_beat != name or self.beat_flag[name]:
            self.tutorial_beat(name)

    # -[Stage_Tutorial tutorialNRestart] - the prompt again, and its monster after it
    def tutorial_restart(self, name):
        if not self.finished and not self.beat_done[name]:
            self.tutorial_beat(name)

    # -[Stage_Tutorial MonsterAttPlayer] 0x8a908, the tail at 0x3b3b2: no heart is
    # lost; the beat for the monster's lane starts again.
    def _tutorial_monster_reached(self, m):
        name = LANE_BEAT.get(m.MovingType)
        if m.MovingType == 3 and self.beat_done['Three']:
            name = 'FiveHalf'                  # 0x3b3de: threeFlag, then fiveHalfFlag
        if name is not None:
            self.tutorial_restart(name)

    # -[Stage_Tutorial NonShaking] 0x8b1f2 - the grab landed, so beat Eight again.
    def _tutorial_grab_landed(self):
        self.tutorial_restart('Eight')

    # -[Stage_Tutorial tutorialHiddenView] 0x3d0a8 - hides the arrows and the finger
    def tutorialHiddenView(self):
        pass

    def _complete(self, name):
        """Mark a beat done and let CheckTutorial pick up the next one."""
        if self.beat_done.get(name):
            return
        self.beat_done[name] = True
        self.beat_flag[name] = False
        log.info('tutorial %s done', name)

    # ================================================== what finishes a beat
    # -[Stage_Tutorial MonsterDamage] 0x8a250 - by the dead monster's lane.  It
    # listens on _kill_seen rather than MonsterKillCount_, which --debug skips so that
    # no kill counts; the lesson still has to see the zombie die.
    def _kill_seen(self, m):
        if self.finished:
            return
        name = LANE_BEAT.get(m.MovingType)
        if name and not self.beat_done[name]:
            self._complete(name)
        elif not self.beat_done['FiveHalf'] and all(
                self.beat_done[n] for n in ('One', 'Two', 'Three', 'Four', 'Five')):
            self._complete('FiveHalf')

    # -[Stage_Tutorial GunReloadAction:] / reloadShotgun
    def GunReloadAction_(self, *a):
        super().GunReloadAction_(*a)
        self._complete('Six')

    # -[Stage_Tutorial gunChangeAction:]
    def gunChangeAction_(self, step=1):
        super().gunChangeAction_(step)
        self._complete('Seven')

    # -[Stage_Tutorial shakingFind] - shaking the grabber off
    def shakingFind(self, timer=None):
        super().shakingFind(timer)
        if not self.isShake:
            self._complete('Eight')

    # -[Stage_Tutorial StopPlayAction:] 0x83804 - P while the tutorial is running.
    def StopPlayAction_(self, *a):
        if self.ending:
            # PORT DIVERGENCE: the original set isTutorial on the way out, so a second
            # stop during the 3.05 s wait paused a stage about to be left or started.
            return False
        return super().StopPlayAction_(*a)

    def tutorial_skip(self):
        """0x838b0..0x83aba: nothing until beats One to Eight are done.  Then stop the
        prompt, write ``TUTORIAL``, stop both timers, play ``tutorial success`` and
        call ``tutorialEnd:`` 3.05 s later.  Doing this is beat Nine."""
        if self.finished or not all(self.beat_done[n] for n in STOP_NEEDS):
            return
        self.finished = True
        self.ending = True
        self.beat_done['Nine'] = True
        if self.checkTutorialTimer is not None and self.checkTutorialTimer.isValid():
            self.checkTutorialTimer.invalidate()
        self.checkTutorialTimer = None
        RunLoop.main().cancelPerform(self, 'tutorial_sound_stop')
        if self.current_beat is not None:
            _n, sound, _delay, _spawn = self._beat(self.current_beat)
            self.app.stopSoundBufNumber_(sound)
        if self.speech is not None:
            self.speech.stop()
        d = UserDefaults.standardUserDefaults()
        d.setObject_forKey_('1', 'TUTORIAL')                   # 0x839d4
        d.synchronize()
        self.app.playSound_Gain_Pos_z_reprats_(
            SOUND_TUTORIAL_SUCCESS, 0.2, (0.0, 0.0), 0, False)   # 0x83a92
        RunLoop.main().perform(self, 'tutorialEnd_', None, ENDING_DELAY)
        log.info('tutorial finished; TUTORIAL = 1')

    # ================================================================== end
    # -[Stage_Tutorial tutorialEnd:] 0x83738, or -[Stage_1_E tutorialEnd:] 0x33bec on
    # a first run.
    def tutorialEnd_(self, *_):
        if not self.first_run:
            self.ending = False
            self.GameEndAction_()                              # back to the menu
            return
        self.app.TTSNumber_type_(COUNTDOWN, 1)                 # 0x33c0e: 3, 2, 1
        RunLoop.main().perform(self, 'tutorialEndGameStart_', None, COUNTDOWN_SECONDS)

    # -[Stage_1_E tutorialEndGameStart:] 0x33d40, the same as Stage_Tutorial's own
    # 0x8374c, which nothing calls.
    def tutorialEndGameStart_(self, *_):
        self.ending = False
        self.noAtt = False                     # 0x83774
        self.shotFlag = False                  # 0x83782
        self.isTutorial = 1                    # 0x83786
        self.app.playSound_Gain_Pos_z_reprats_(
            SOUND_ZOMBIES_COMING, 0.2, (0.0, 0.0), 0, False)   # 0x837ae
        self.MotionSamplingTimer = RunLoop.main().scheduledTimer(
            1.0, self, 'MainControl', None, True)              # 0x837ea

    def teardown(self):
        if self.checkTutorialTimer is not None and self.checkTutorialTimer.isValid():
            self.checkTutorialTimer.invalidate()
        self.checkTutorialTimer = None
        # Escape (or any other way out) used to leave whatever beat's prompt was
        # still playing to run out on its own, right over the menu.
        if self.current_beat is not None:
            _n, sound, _delay, _spawn = self._beat(self.current_beat)
            self.app.stopSoundBufNumber_(sound)
        if self.speech is not None:            # ...and its key hint
            self.speech.stop()
        if self.ending:
            self.app.readStop()                # the 3, 2, 1
        super().teardown()
