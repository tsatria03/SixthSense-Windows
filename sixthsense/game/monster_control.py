"""``MonsterControl`` - one monster.  Ported from 0x10618..0x12b7d.

A monster has no grid position: it lives on a *bearing and a range*.  ``MonsterMoving:``
turns ``monsterChangeAngle`` (degrees) and ``monsterRange`` (cm) into the Cartesian
``Pos`` the OpenAL source is placed at, and closes the range by ``comingRange`` cm on
every footstep.

Two nested timers drive it (``-[MonsterControl MonsterStart:]`` 0x10dac and
``-[MonsterControl MonsterComing:]`` 0x11920):

    MainMonsterTimer         every  comingSoundTime                 -> MonsterComing:
    MonsterMovingAngleTimer  every  (comingSoundTime - 0.1) / comingSoundInWalk
                                                                    -> MonsterMoving:

so one cycle of the walk sample is ``comingSoundInWalk`` steps.  The sample itself is
started once, looping, by ``MonsterStart:``; each step then moves that playing source to
the monster's new position and scales its gain by 1.1 (0x11442), which is how a monster
gets louder as it closes (``-[oalPlayback startSound:Postion:soundGain:]``).

The headshot window is the gap in the monster's breathing.  ``MonsterComing:`` either
performs ``headShot:`` after ``headShotTimeStart`` seconds, or, when the plist gave a
comma-separated list of times ("0.3,1.3" in type71.plist), walks that list with
``headShotTimer``.  ``headShot:`` raises ``headShotFlag`` and schedules ``headShotEnd:``
``headShotTimeEndHowLong`` seconds later - the player has exactly that long to fire.

``comingMonsterStopSoundNumber`` is the note ``AppDelegate`` handed out for this monster's
``comingSound``.  Two monsters that were given the same sound number therefore share one
OpenAL source, which is why ``-[Stage_1_E MonsterInit:]`` hands out three different sound
numbers per zombie kind (``SoundList`` has each zombie sample listed three times).
"""
from __future__ import annotations

import logging
import math
import plistlib

from .. import paths
from ..platform.runloop import RunLoop
from ..platform.defaults import UserDefaults

log = logging.getLogger('monster')


def _f(v, default=0.0):
    """``-[NSString floatValue]``"""
    if v is None:
        return default
    s = str(v).strip()
    out, dot = '', False
    for i, ch in enumerate(s):
        if ch in '+-' and i == 0:
            out += ch
        elif ch.isdigit():
            out += ch
        elif ch == '.' and not dot:
            dot = True
            out += ch
        else:
            break
    try:
        return float(out)
    except ValueError:
        return default


def _i(v, default=0):
    return int(_f(v, default))


# -[MonsterControl MonsterMoving:] 0x11050..0x11318
# MovingType -> (NSUserDefaults key, default bearing in degrees)
MOVING_TYPE_ANGLE = {
    1: ('WZ', 180),     # 0x110a4 / 0x110d2
    2: ('WNZ', 123),    # 0x11138 / 0x11166
    3: ('NZ', 90),      # 0x111cc / 0x111fa
    4: ('ENZ', 57),     # 0x11260 / 0x1128c
    5: ('EZ', 0),       # 0x112f2 / 0x1160e
}

# -[MonsterControl initWithMonsterPatern:...] 0x10b7a..0x10ca4 - where a monster comes in.
# Every lane starts 1000 cm out; the tail then sets monsterRange to 1000.0 (0x10c20:
# movt r2, #0x447a) and calls MonsterStart:.  Note these bearings are not quite the ones
# MonsterMoving: walks on - 120/60 here against 123/57 there - which is the original's
# own inconsistency, kept.
START_POS = {
    1: (-1000.0, 0.0), 11: (-1000.0, 0.0),
    2: (-500.0, 866.0), 22: (-500.0, 866.0),
    3: (0.0, 1000.0), 33: (0.0, 1000.0),
    4: (500.0, 866.0), 44: (500.0, 866.0),
    5: (1000.0, 0.0), 55: (1000.0, 0.0),
}
START_RANGE = 1000.0

#: The five zig-zag walks, from the ``tbb``-free chain at 0x1155e..0x1187c.
#:
#: ``MovingType`` 1..5 walk straight down one lane.  11, 22, 33, 44 and 55 sweep
#: across four bearings instead, one per footstep, and turn round at each end:
#: ``MovingAngleTurn`` says which way they are going and flips when ``MovingCount``
#: reaches 4.  Half of the shipped ``typeN.plist`` files - fifty of them - use one of
#: these, so this is not a corner case.
#:
#: Read in ``MovingCount`` order while ``MovingAngleTurn`` is 0, and backwards while
#: it is 1.  The angles are the literals the branches pass to ``setMovingPosAngle:``:
#: 0x11702/0x11740 (185, 120), 0x1177c/0x117ce (125, 90), 0x117dc/0x1184e (90, 55),
#: 0x1185c/0x11838 (55, 1) and so on.
ZIGZAG_ANGLE = {
    11: (185, 160, 140, 120),        # about lane 1, 180 degrees
    22: (125, 110, 100, 90),         # about lane 2, 123
    33: (90, 80, 65, 55),            # about lane 3, 90
    44: (55, 40, 15, 1),             # about lane 4, 57
    55: (1, 15, 40, 55),             # about lane 5, 0 - the same ladder, other phase
}


#: PORT DIVERGENCE: the woman zombie's two walk sounds, and how far into each her growl
#: starts, in seconds (a tenth early, so its start is not clipped).  Both are quiet
#: footsteps with the growl at the end: 16 steps of 50 cm every 6 s, and she keeps
#: that speed on every level (``MonsterInit:`` builds her with an HPGain of 1.0,
#: 0x39034).  A new woman starts at the top of the sample, as in the original, and
#: growls 3.5 to 4.5 m out.  After a pause the original starts the sample again from
#: the top wherever she is, so she could reach you before the growl; the port starts
#: it far enough in that the growl lands when she is ``GROWL_AT`` away.
WOMAN_GROWL = {
    271: 3.6,       # woman_coming_cave_monster1, 5.23 s long
    272: 4.5,       # woman_coming_forest_Monster, 6.29 s long
}
#: How far away she is when the growl starts, in cm - where the original's level 1 has it.
GROWL_AT = 350.0


def lane_bearing(lane):
    """The bearing a straight walker in ``lane`` takes (0x11050..0x1133e): the
    NSUserDefaults key if it is set, the built-in default if not, 0 for anything else
    (0x1160e)."""
    key_default = MOVING_TYPE_ANGLE.get(lane)
    if key_default is None:
        return 0
    key, default = key_default
    s = UserDefaults.standardUserDefaults().stringForKey_(key)
    return _i(s) if s else default


class MonsterControl:
    def __init__(self):
        self.frozen = False            # not in the original: --debug's F6 holds it still
        self.MainMonsterTimer = None
        self.comingBreathTimer = None
        self.monsterCount = 0
        self.MovingCount = 0
        self.MonsterSoundNumberInWalk = 0
        self.MonsterMovingAngleTimer = None
        self.MovingAngleTurn = False
        self.comingMonsterStopSoundNumber = 0
        self.headShotTimer = None
        self.monsterHeadShotArrayCount = 0
        self.monsterHeadShotTimeCount = 0
        self.monsterFlag = False
        self.Pos = (0.0, 0.0)
        self.workingSoundTime = 0.0
        self.MovingType = 0
        self.HP = 0
        self.Damage = 0
        self.comingSound = 0
        self.comingSoundGain = 0.0
        self.comingSoundTime = 0.0
        self.comingSoundInWalk = 0
        self.comingRange = 0
        self.hitSound = 0
        self.hitSoundTime = 0.0
        self.hitSoundGain = 0.0
        self.dieSound = 0
        self.dieSoundTime = 0.0
        self.dieSoundgain = 0.0
        self.playerHitSound = 0
        self.playerHitSoundGain = 0.0
        self.playerHitSoundtimer = 0.0
        self.headShotTimeStart = 0.0
        self.headShotTimeEndHowLong = 0.0
        self.headShotFlag = False
        self.monsterNumber = 0
        self.shakeMonsterFlag = False
        self.shakeMonsterNumber = 0
        self.shakeMonsterSoundGain = 0.0
        self.shakeMonsterApproachSound = 0
        self.shakeMonsterApproachTime = 0.0
        self.shakeMonsterApproachGain = 0.0
        self.shakeMonsterPushSound = 0
        self.shakeMonsterPushTime = 0.0
        self.shakeMoneterPushGain = 0.0
        self.monsterPi = 0.0
        self.monsterRange = 0.0
        self.MovingPosAngle = 0
        self.monsterHeadShotArray = []
        self.isHeadShot = False
        self.monsterChangeAngle = -1
        # not in the original: the port needs a handle on the app for playSound:.
        self.app = None

    # =================================================================== init
    # -[MonsterControl initWithMonsterPatern:soundController:comingSound:hitSound:
    #   damageSound:diesound:shakeApproach:shakwPush:HPGain:]  0x10618
    def initWithMonsterPatern(self, patern, soundController, comingSound, hitSound,
                              damageSound, diesound, shakeApproach, shakwPush, HPGain):
        self.app = soundController
        path = paths.path_for_resource('type%d' % patern, 'plist')
        if path is None:
            log.error('monster plist missing: type%d.plist', patern)
            return None
        with open(path, 'rb') as f:
            a = plistlib.load(f)
        if not a:
            return None

        self.MovingType = _i(a[1])                             # 0x106d2
        self.HP = int(float(_i(a[3])) * HPGain)                # 0x10704, * HPGain
        self.Damage = _i(a[5])                                 # 0x10738
        # 0x1076a: the note is allocated here, from the sound number the caller passed.
        self.comingMonsterStopSoundNumber = \
            soundController.playSoundBufNumber_(comingSound)
        self.comingSound = comingSound
        self.comingSoundGain = _f(a[9]) + 0.2                  # 0x107ae, + 0.2
        self.comingSoundTime = _f(a[11])
        self.comingSoundInWalk = int(_f(a[13]))
        self.comingRange = int(float(_i(a[15])) * HPGain)      # 0x10832, * HPGain
        self.hitSound = hitSound
        self.hitSoundGain = _f(a[19]) * 0.5                    # 0x1087c, * 0.5
        self.hitSoundTime = _f(a[21])
        self.dieSound = diesound
        self.dieSoundgain = _f(a[25])
        self.dieSoundTime = _f(a[27])
        self.playerHitSound = damageSound
        self.playerHitSoundGain = _f(a[31])
        self.playerHitSoundtimer = _f(a[33])

        # 0x1097e: "몬스터 숨소리 시작 시간(해드샷구간)" may be a comma list.
        head = str(a[35])
        parts = head.split(',')
        if len(parts) >= 2:
            self.monsterHeadShotArray = list(parts)
            self.headShotTimeStart = _f(parts[0])
        else:
            self.monsterHeadShotArray = []
            self.headShotTimeStart = _f(a[35])

        self.headShotTimeEndHowLong = _f(a[37])
        self.shakeMonsterFlag = bool(_i(a[39]))
        self.monsterNumber = _i(a[41])

        # 0x10a86: the shake block only exists when shakeMonsterFlag is set.
        if self.shakeMonsterFlag and len(a) > 53:
            self.shakeMonsterApproachSound = shakeApproach
            self.shakeMonsterApproachTime = _f(a[45])
            self.shakeMonsterApproachGain = _f(a[47])
            self.shakeMonsterPushSound = shakwPush
            self.shakeMonsterPushTime = _f(a[51])
            self.shakeMoneterPushGain = _f(a[53])

        # 0x10b48..0x10ca4: place it on its lane, 1000 cm out, and set it walking.
        self.monsterChangeAngle = -1
        self.monsterFlag = True
        self.Pos = START_POS.get(self.MovingType, (0.0, 1000.0))
        self.monsterRange = START_RANGE
        self.MonsterStart_(None)
        return self

    # ============================================================= lifecycle
    def _invalidate(self, name):
        t = getattr(self, name)
        if t is not None and t.isValid():
            t.invalidate()
        setattr(self, name, None)

    # -[MonsterControl MonsterStart:] 0x10dac
    def MonsterStart_(self, timer=None):
        self.MonsterComing_(None)                       # 0x10dda, performSelector:
        pb = self.app.playback
        pb.stopSound_(self.comingMonsterStopSoundNumber)
        # 0x10e7e: z = 0, reprats = YES - the walk sample loops.
        self.app.playSound_Gain_Pos_z_reprats_(
            self.comingSound, self.comingSoundGain, self.Pos, 0, True)
        offset = self._growl_offset()
        if offset:
            pb.setSoundOffset_(self.comingMonsterStopSoundNumber, offset)
        self.MainMonsterTimer = RunLoop.main().scheduledTimer(
            self.comingSoundTime, self, 'MonsterComing_', None, True)

    def _growl_offset(self):
        """How far into the woman zombie's sample to start it, so the growl lands as she
        comes within ``GROWL_AT``; 0 for every other monster.  Called just after
        ``MonsterComing:`` took its first step, so the steps still to come are one
        ``MonsterMoving:`` interval apart.  After a pause it counts from where she is."""
        growl = WOMAN_GROWL.get(self.comingSound)
        if growl is None or self.comingRange <= 0:
            return 0.0
        interval = self.comingSoundTime - 0.1
        if self.comingSoundInWalk:
            interval = interval / float(self.comingSoundInWalk)
        steps = max(0, math.ceil((self.monsterRange - GROWL_AT) / float(self.comingRange)))
        return max(0.0, growl - steps * interval)

    # -[MonsterControl MonsterComing:] 0x11920
    def MonsterComing_(self, timer=None):
        loop = RunLoop.main()
        # 0x1194c: the first step of each cycle is taken at once, so a new monster is on
        # its lane from the moment it appears instead of reading as bearing 0.
        self.MonsterMoving_(None)
        interval = self.comingSoundTime - 0.1
        if self.comingSoundInWalk:
            interval = interval / float(self.comingSoundInWalk)
        # The original leaves any earlier timer running; it has always stopped itself
        # by now, and cancelling it here just makes sure.
        self._invalidate('MonsterMovingAngleTimer')
        self.MonsterMovingAngleTimer = loop.scheduledTimer(
            max(0.01, interval), self, 'MonsterMoving_', None, True)

        self.monsterHeadShotArrayCount = len(self.monsterHeadShotArray)
        if len(self.monsterHeadShotArray) >= 2:                # 0x11a18
            if self.headShotTimer is None or not self.headShotTimer.isValid():
                self.monsterHeadShotTimeCount = 0
                t = _f(self.monsterHeadShotArray[self.monsterHeadShotTimeCount])
                self.headShotTimer = loop.scheduledTimer(
                    max(0.01, t), self, 'headShot_', None, False)
                self.monsterHeadShotArrayCount -= 1
                self.monsterHeadShotTimeCount += 1
        else:                                                  # 0x11ada
            loop.perform(self, 'headShot_', None, self.headShotTimeStart)

    # -[MonsterControl MonsterMoving:] 0x10f38
    def MonsterMoving_(self, timer=None):
        self.MovingCount += 1

        # 0x10fb0: monsterRange = sqrtf(Pos.x*Pos.x + Pos.y*Pos.y)
        self.monsterRange = math.sqrt(self.Pos[0] * self.Pos[0] +
                                      self.Pos[1] * self.Pos[1])
        # 0x10fee: while further than 25 cm, close by comingRange; otherwise it stops
        # 20 cm out (0x11032: movs r2, #0 / movt r2, #0x41a0), still in its lane.
        # PORT DIVERGENCE: the original lets that last step overshoot, to 0 or past
        # you, so the monster passed through the centre or crossed to the other side
        # before the next step put it back out at 20 cm - heard as a step sideways.
        # A step stops at 20 cm here, which is where it ends up anyway; it still
        # arrives within 25 cm on the same step.
        if self.frozen:
            pass
        elif self.monsterRange > 25.0:
            self.monsterRange = max(20.0,
                                    self.monsterRange - float(self.comingRange))
        else:
            self.monsterRange = 20.0

        # 0x11050..0x1133e: the five straight lanes pick their bearing once, from
        # NSUserDefaults if the key is set and from the built-in default if not.
        # 0x112a4 sends everything else - the zig-zag types - to 0x1155e instead,
        # which sets MovingPosAngle itself, every step, and never touches
        # monsterChangeAngle.
        if self.MovingType in ZIGZAG_ANGLE:
            self._zigzag_step()
        else:
            if self.monsterChangeAngle == -1:
                self.monsterChangeAngle = lane_bearing(self.MovingType)
            self.MovingPosAngle = self.monsterChangeAngle

        # 0x11362..0x113e0
        rad = self.MovingPosAngle * math.pi / 180.0
        self.Pos = (self.monsterRange * math.cos(rad),
                    self.monsterRange * math.sin(rad))
        self.monsterPi = self.MovingPosAngle * math.pi / 180.0      # 0x113f2
        if not self.frozen:
            self.comingSoundGain = self.comingSoundGain * 1.1       # 0x11442

        self.app.playback.startSound_Postion_soundGain_(
            self.comingMonsterStopSoundNumber, self.Pos, self.comingSoundGain)

        # 0x114f4: one full sample is comingSoundInWalk steps; then stop stepping until
        # MonsterComing: re-arms the timer.
        if self.MovingCount >= self.comingSoundInWalk:
            self.MovingCount = 0
            self._invalidate('MonsterMovingAngleTimer')

    def _zigzag_step(self):
        """One footstep of a zig-zag walk (0x1155e..0x1187c).

        ``MovingCount`` outside 1..4 falls through to 0x1187c without touching the
        angle, so the monster keeps the bearing it had.
        """
        ladder = ZIGZAG_ANGLE.get(self.MovingType)
        mc = self.MovingCount
        if ladder is None or not 1 <= mc <= 4:
            return self.MovingPosAngle
        if self.MovingAngleTurn:
            self.MovingPosAngle = ladder[4 - mc]         # backwards
        else:
            self.MovingPosAngle = ladder[mc - 1]
        if mc == 4:                                      # 0x11740, 0x116f4 and friends
            self.MovingAngleTurn = not self.MovingAngleTurn
        return self.MovingPosAngle

    # -[MonsterControl headShot:] 0x11b30
    def headShot_(self, timer=None):
        self._invalidate('headShotTimer')
        loop = RunLoop.main()
        if self.monsterHeadShotArrayCount >= 1 and self.headShotTimer is None:
            # 0x11bbc: the next window opens after the gap between consecutive entries.
            cur = _f(self.monsterHeadShotArray[self.monsterHeadShotTimeCount])
            prev = _f(self.monsterHeadShotArray[self.monsterHeadShotTimeCount - 1])
            self.headShotTimer = loop.scheduledTimer(
                max(0.01, cur - prev), self, 'headShot_', None, False)
            self.monsterHeadShotArrayCount -= 1
            self.monsterHeadShotTimeCount += 1
        self.headShotFlag = True                                    # 0x11c74
        loop.perform(self, 'headShotEnd_', None, self.headShotTimeEndHowLong)

    # -[MonsterControl headShotEnd:] 0x11ccc
    def headShotEnd_(self, timer=None):
        self.headShotFlag = False

    # -[MonsterControl shakeMonster] 0x11ce0
    def shakeMonster(self):
        self._invalidate('comingBreathTimer')
        self.app.playback.stopSound_(self.comingMonsterStopSoundNumber)
        self._invalidate('MonsterMovingAngleTimer')
        self._invalidate('MainMonsterTimer')
        self.app.playSound_Gain_Pos_z_reprats_(
            self.shakeMonsterApproachSound, self.shakeMonsterApproachGain,
            (0.0, 0.0), 0, False)
        if self.app.bDevice:
            self.app.vibrate()

    # -[MonsterControl stopShakeMonsterSound:] 0x11e44
    def stopShakeMonsterSound_(self, timer=None):
        self.app.stopSoundBufNumber_(self.shakeMonsterApproachSound)

    # -[MonsterControl hitPlayer] 0x11e7c
    def hitPlayer(self):
        self._invalidate('comingBreathTimer')
        self.app.playback.stopSound_(self.comingMonsterStopSoundNumber)
        self._invalidate('MonsterMovingAngleTimer')
        self._invalidate('MainMonsterTimer')
        # 0x11f92..0x11fa2: gain 1.0 at (0, 0), z 40 - in the middle of your head, not at
        # the monster: x and y are both stored from a zeroed r0.  This is the zombie's
        # blow, or the girl's thank you (270); the port had played it at self.Pos.
        self.app.playSound_Gain_Pos_z_reprats_(
            self.playerHitSound, 1.0, (0.0, 0.0), 40, False)
        RunLoop.main().perform(self, 'MonsterHitAndDead', None, self.dieSoundTime)

    # -[MonsterControl MonsterHitAndDead] 0x11fec
    def MonsterHitAndDead(self, *_):
        self.app.playback.stopSound_(self.comingMonsterStopSoundNumber)
        self.app.stopSoundBufNumber_(self.playerHitSound)

    # -[MonsterControl stopMonsterComingSound:] 0x12054
    def stopMonsterComingSound_(self, timer=None):
        self.app.playback.stopSound_(self.comingMonsterStopSoundNumber)

    # -[MonsterControl MonsterHitSoundDealloc] 0x12090
    def MonsterHitSoundDealloc(self, *_):
        self.app.stopSoundBufNumber_(56)          # weapon_gun_att1, the hit
        self.app.stopSoundBufNumber_(self.hitSound)

    # -[MonsterControl MonsterHitSound:] 0x120d4
    def MonsterHitSound_(self, timer=None, impact=True):
        """Taking a hit.  Above 0 HP it plays the impact plus the monster's damage
        sound; at 0 it plays the impact and dies.

        PORT DIVERGENCE (tsatria03, 2026-09-25): ``impact=False`` leaves out the impact,
        56, ``weapon_gun_att1``, for the knife and the sword.  The original plays it on
        every hit whatever the weapon (0x1217a, 0x12208), so a blade made a gun's hit
        sound under its own; the blade's att1 or att2 is its hit sound now."""
        # 0x12110: the impact uses playerHitSoundGain * 2.5
        gain = self.playerHitSoundGain * 2.5
        if impact:
            self.app.playSound_Gain_Pos_z_reprats_(56, gain, self.Pos, 40, False)
        if self.HP >= 1:
            self.app.playSound_Gain_Pos_z_reprats_(
                self.hitSound, self.hitSoundGain, self.Pos, 40, False)
        else:
            self.DieMonster()

    # -[MonsterControl DieMonster] 0x1222c
    def DieMonster(self):
        self._invalidate('comingBreathTimer')
        self.app.playback.stopSound_(self.comingMonsterStopSoundNumber)
        self._invalidate('MonsterMovingAngleTimer')
        self._invalidate('MainMonsterTimer')
        self.app.stopSoundBufNumber_(self.comingSound)
        self.app.stopSoundBufNumber_(self.dieSound)
        self.app.playSound_Gain_Pos_z_reprats_(
            self.dieSound, self.dieSoundgain, self.Pos, 40, False)
        RunLoop.main().perform(self, 'MonsterDead', None, self.dieSoundTime)

    # -[MonsterControl MonsterDead] 0x12428
    def MonsterDead(self, *_):
        """``dieSoundTime`` after the death: the monster is marked no longer alive.

        It stops nothing.  The raw instructions are ``[self dieSound]`` with the result
        dropped (0x1243c), then ``[self setMonsterFlag:NO]`` as a tail call (0x12454), so
        the death sound always plays to its end.  The port used to stop it here, which
        cut a death short wherever the plist's ``dieSoundTime`` is shorter than the
        recording: zombie 2's type10 lost two of its 3.56 seconds (tsatria03 heard it,
        2026-09-25)."""
        self.monsterFlag = False

    # -[MonsterControl StopPlayGame] 0x10ca8
    def StopPlayGame(self):
        self._invalidate('MainMonsterTimer')
        self._invalidate('comingBreathTimer')
        self._invalidate('MonsterMovingAngleTimer')
        self.app.playback.stopSound_(self.comingMonsterStopSoundNumber)

    # -[MonsterControl ReplayGame] 0x10d98
    def ReplayGame(self):
        self.MonsterStart_(None)

    # -[MonsterControl dealloc] 0x12458
    def dealloc(self):
        self._invalidate('MainMonsterTimer')
        self._invalidate('comingBreathTimer')
        self._invalidate('MonsterMovingAngleTimer')
        self._invalidate('headShotTimer')
        RunLoop.main().cancelPerform(self)

    def __repr__(self):
        return '<Monster #%d type=%d HP=%d range=%.0f angle=%d>' % (
            self.monsterNumber, self.MovingType, self.HP, self.monsterRange,
            self.MovingPosAngle)
