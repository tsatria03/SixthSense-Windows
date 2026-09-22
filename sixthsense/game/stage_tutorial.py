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
    Nine   284  "if you tab the screen using three finger twice"  -  three-finger tap

The clock positions *are* the five lanes, which is where the port's A/Q/W/E/D keys
come from, and beat six is the reload swipe (see ``Stage_1_E._lane_for_angle``).

Killing sets the flag by the dead monster's lane: ``-[Stage_Tutorial MonsterDamage]``
at 0x8a250 tests ``MovingType`` 1..5 and sets ``tutorialOne``..``tutorialFive``.

When the last beat lands, ``tutorialEndGameStart:`` (0x8374c) clears ``noAtt`` and
``shotFlag``, sets ``isTutorial = 1``, plays ``zombies are coming`` (328) and starts the
1.0 s walk timer - the real game, from the same standing start.

The port drives the ten beats from a table instead of ten copies of five methods.
Nothing about the behaviour changes; see docs/DIVERGENCES.md.
"""
from __future__ import annotations

import logging

from ..platform.defaults import UserDefaults
from ..platform.runloop import RunLoop
from .stage_1_e import Stage_1_E

log = logging.getLogger('tutorial')

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

SOUND_TUTORIAL_SUCCESS = 327        # 'tutorial success'
SOUND_ZOMBIES_COMING = 328          # 'zombies are coming'

# -[Stage_Tutorial MonsterDamage] 0x8a250 - a kill in lane N finishes beat N.
LANE_BEAT = {1: 'One', 2: 'Two', 3: 'Three', 4: 'Four', 5: 'Five'}


class Stage_Tutorial(Stage_1_E):
    """The tutorial run.  Same stage, same monsters, no walking until it is over."""

    def __init__(self):
        super().__init__()
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
        if spawn is not None:
            self.MonsterInit_(spawn)

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
        else:
            self.tutorialEndGameStart_(None)
            return
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
        if all(self.beat_done.values()):
            self.tutorialEndGameStart_(None)

    # ================================================== what finishes a beat
    # -[Stage_Tutorial MonsterDamage] 0x8a250 - by the dead monster's lane
    def MonsterKillCount_(self, m):
        super().MonsterKillCount_(m)
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

    # -[Stage_Tutorial threeTapChangeWeapon:]
    def threeTapChangeWeapon_(self, *a):
        super().threeTapChangeWeapon_(*a)
        self._complete('Nine')

    # -[Stage_Tutorial StopPlayAction:] 0x8392a - P, while the tutorial is still
    # running.  Stage_1_E.tutorial_skip writes TUTORIAL and plays tutorial success,
    # but never silences CheckTutorial, so the prompts kept nagging afterward.
    def tutorial_skip(self):
        if self.checkTutorialTimer is not None and self.checkTutorialTimer.isValid():
            self.checkTutorialTimer.invalidate()
        self.checkTutorialTimer = None
        if self.current_beat is not None:
            _n, sound, _delay, _spawn = self._beat(self.current_beat)
            self.app.stopSoundBufNumber_(sound)
        super().tutorial_skip()

    # ================================================================== end
    # -[Stage_Tutorial tutorialEndGameStart:] 0x8374c
    def tutorialEndGameStart_(self, *_):
        if self.finished:
            return
        self.finished = True
        if self.checkTutorialTimer is not None and self.checkTutorialTimer.isValid():
            self.checkTutorialTimer.invalidate()
        self.checkTutorialTimer = None
        RunLoop.main().cancelPerform(self, 'tutorial_sound_stop')

        self.noAtt = False                     # 0x83774
        self.shotFlag = False                  # 0x83782
        self.isTutorial = 1                    # 0x83786
        self.app.playSound_Gain_Pos_z_reprats_(
            SOUND_ZOMBIES_COMING, 0.2, (0.0, 0.0), 0, False)   # 0x837ae
        self.MotionSamplingTimer = RunLoop.main().scheduledTimer(
            1.0, self, 'MainControl', None, True)              # 0x837ea
        self.tutorialEnd_(None)

    # -[Stage_Tutorial StopPlayAction:] 0x839d4 writes the key; the port writes it
    # here, when the beats are actually finished.
    def tutorialEnd_(self, *_):
        d = UserDefaults.standardUserDefaults()
        d.setObject_forKey_('1', 'TUTORIAL')
        d.synchronize()
        self.app.playSound_Gain_Pos_z_reprats_(
            SOUND_TUTORIAL_SUCCESS, 1.0, (0.0, 0.0), 0, False)
        log.info('tutorial finished; TUTORIAL = 1')

    def teardown(self):
        if self.checkTutorialTimer is not None and self.checkTutorialTimer.isValid():
            self.checkTutorialTimer.invalidate()
        self.checkTutorialTimer = None
        # Escape (or any other way out) used to leave whatever beat's prompt was
        # still playing to run out on its own, right over the menu.
        if self.current_beat is not None:
            _n, sound, _delay, _spawn = self._beat(self.current_beat)
            self.app.stopSoundBufNumber_(sound)
        super().teardown()
