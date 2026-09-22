"""``Stage_1_E`` - the stage itself.  Ported from 0x2c4d0..0x3f4d1.

How the game actually works, established from the binary:

**The world.**  A 701 x 42 grid (``MakeMaps``), of which only column 20 is walkable: the
player starts at ``(20, 680)`` (0x2cf04, 0x2cf1a) and walks *down* in Y.  One cell is
40 cm (``-[Stage_1_E soundFunction:...]`` multiplies squared cell distance by 1600).

**The clock.**  ``MotionSamplingTimer`` fires ``MainControl`` once a second
(0x2e092: ``vmov.f64 d16, #1.0``).  Each tick is one step forward, one breath, one
spawn check, one round of monster attacks.

**Monsters do not live on the grid.**  A monster has a *lane* and a *range*.  Five lanes,
by compass bearing, from ``MovingType`` in its plist:

        MovingType  1  WZ    180 deg     west, hard left
                    2  WNZ   123 deg
                    3  NZ     90 deg     straight ahead
                    4  ENZ    57 deg
                    5  EZ      0 deg     east, hard right

Only one monster per lane at a time (``checkMonsterArray:`` 0x36458 rejects a type whose
``id % 10`` lane is taken).  Each footstep closes the range by ``comingRange`` cm and
makes the sound 1.1x louder.  At 25 cm it is on top of you.

**Fighting.**  A swipe (``MovingShot:`` 0x2ec98) is ``atan2`` of the accumulated pan,
in degrees, quantised into the same five lanes; the result is ``shotMonster`` 1..5.
``monsterHitHeadFind`` (0x3ab88) then takes the nearest monster whose ``MovingPosAngle``
falls in that lane's band and is inside the weapon's ``Range``:

        shotMonster 1   157..202 deg        4    23..62
                    2   113..155            5     0..22 or 338..360
                    3    63..112

A hit lands for ``weapon.Damage``; a hit taken while the monster's ``headShotFlag`` is up -
the pause in its breathing - lands for ``Damage * 2`` and counts as a headshot
(0x3a1dc: ``HP - (damage << 1)``).

**Progress.**  Reaching Y == 23 ends the level: ``ChangeLevel:`` (0x322e0) puts the player
back at 680, multiplies ``monsterHPGain`` by 1.5 and flips the environment between cave
and forest.  The action layer of the map (``a_CH1_E.txt``) sets the spawn tier along the
way: values 1..7 raise ``monster_num``, 8/9/10 drive the girl, the ambience and the music.
"""
from __future__ import annotations

import logging
import math
import random
import time

from .. import paths
from ..platform.defaults import UserDefaults
from ..platform.runloop import RunLoop
from .app_delegate import AppDelegate
from .make_maps import MakeMaps
from .monster_control import MonsterControl
from .moving_accelerometer import MovingAccelerometer
from .player_control import PlayerControl
from .weapon_control import WeaponControl, WEAPON_FILES, WEAPON_SLOTS

log = logging.getLogger('stage')


def arc4random():
    return random.getrandbits(32)


# -[Stage_1_E viewDidLoad] 0x2c7e4 - the 50 monster type ids, five lanes per kind.
#   index i  ->  kind = i // 5 + 1,  lane = i % 5 + 1
MONSTER_ARRAY = (
    ['1', '2', '3', '4', '5'] +
    ['%d%d' % (k, l) for k in range(1, 10) for l in range(1, 6)]
)

# -[Stage_1_E MakeMonster:] 0x36100, through the tbh table at 0x36134.
#   tier -> (modulus, offset) for the index into MONSTER_ARRAY
MAKE_MONSTER_TIER = {
    1: (10, 0),     # 0x36142
    2: (20, 0),     # 0x36194
    3: (30, 0),     # 0x36240
    4: (25, 10),    # 0x3629a, falls into the `add r2, r0, #0xa` at 0x36346
    5: (30, 10),    # 0x362f0
    6: (25, 20),    # 0x3634c
    7: (20, 30),    # 0x363a2
}

# -[Stage_1_E monsterHitHeadFind] 0x3ab88, the tbb at 0x3aca6.
#   shotMonster -> the bearing band it can hit
SHOT_BANDS = {
    1: [(157, 202)],
    2: [(113, 155)],
    3: [(63, 112)],
    4: [(23, 62)],
    5: [(0, 22), (338, 360)],
}

# -[Stage_1_E MovingShot:] 0x2ec98 - the swipe angle quantiser.  The bands are the
# float literals compared against ``shotAngle``; anything not covered falls through to
# the final else, which is ``shotMonster = 3`` (0x2f99e).
SWIPE_BANDS = [
    (112.5, 155.5, 2),      # 0x2f172 / 0x2f3a8
    (22.5, 62.5, 4),        # 0x2f4ae / 0x2f596
    (62.5, 112.5, 3),       # 0x2f698 / 0x2f718
    (156.5, 222.5, 1),      # 0x2f828 (melee)
    (156.5, 242.5, 1),      # 0x2f862 (guns)
]

# -[Stage_1_E MonsterInit:] 0x36524 - the sound numbers each monster kind may use.
# One entry is one OpenAL voice, so a kind can have at most as many live monsters as it
# has spare numbers.  Extracted from the arrayWithObjects: blocks at 0x3658e..0x37190.
MONSTER_SOUNDS = {
    #        coming (cave)      coming (forest)    damage           die              hit player
    1:  ([93, 94, 95], [96, 97, 98], [99, 100, 101], [102, 103, 104], [105, 106, 107]),
    2:  ([108, 109, 110], [111, 112, 113], [114, 115, 116], [117, 118, 119], [120, 121, 122]),
    3:  ([123, 124, 125], [126, 127, 128], [129, 130], [132, 133], [135, 136, 137]),
    4:  ([138, 139, 140], [141, 142, 143], [144, 145], [147, 148], [121, 122]),
    5:  ([150, 151, 152], [153, 154, 155], [156, 157, 158], [159, 160, 161], [135]),
    6:  ([165, 166, 167], [168, 169, 170], [171, 172, 173], [174, 175, 176], [177, 178, 179]),
    7:  ([180, 181, 182], [183, 184, 185], [186, 187, 188], [189, 190, 191], [137]),
    8:  ([192, 313, 314], [193, 315, 316], [194, 317, 318], [195, 319, 320], [196, 321, 322]),
    9:  ([199, 200, 201], [202, 203, 204], [205, 206, 207], [208, 209, 210], [211, 212]),
    10: ([214, 215, 216], [217, 218, 219], [206, 207], [210], [220, 221, 222]),
    11: ([292, 293, 294], [295, 296, 297], [301, 302, 303], [310, 311, 312], [298, 299, 300]),
    12: ([304, 305, 306], [304, 305, 306], [301, 302, 303], [310, 311, 312], [307, 308, 309]),
    21: ([267], [268], [205], [269], [270]),          # the girl
    22: ([271], [272], [274], [273], [274]),          # the girl's escort
}
# zombie_8 is the one that grabs you; it needs two more (0x36e96 / 0x36ec4).
SHAKE_SOUNDS = {8: ([197, 323, 324], [198, 325, 326])}

SOUND_HEADSHOT = 330        # headshot_4
SOUND_PLAYER_DAMAGE = 83
SOUND_PLAYER_DIE = 84
SOUND_ZOMBIES_COMING = 328
SOUND_WARNING = 285
SOUND_NO_BULLETS = 78
SOUND_GAME_OVER = 354
SOUND_MISSION_SUCCESS = 227
SOUND_MISSION_FAIL = 228    # stopped by StopElseSpeak; Stage_1_E never plays it
SOUND_BGM_GAME_END = 89     # what -[Stage_1_E playerDie:] plays, 0x3bcaa


class Stage_1_E:
    """One playthrough of the stage."""

    def __init__(self, isTutorial=False):
        self.app = AppDelegate.shared()
        self.stage = None                  # MakeMaps
        self.gamePlayer = PlayerControl()
        self.facing = MovingAccelerometer()
        self.weaponSource = [None] * WEAPON_SLOTS
        self.MonsterBuffer = []
        self.monsterArray = list(MONSTER_ARRAY)

        self.walk_sound_number = 0
        self.walkXFlag = False
        self.breathCount = 0
        self.brearhFlag = False
        self.breathNumber = 0
        self.first = False
        self.shotMonster = 0
        self.shotFlag = False
        self.MotionSamplingTimer = None
        self.posX = 0.0
        self.posY = 0.0
        self.screatchX = 0.0
        self.screatchY = 0.0
        self.shakeCount = 0
        self.shakeFlag = 0
        self.shakeMonsterNumber = 0
        self.shakeMonsterTimer = None
        self.gameState = 0
        self.bStop = False          # set by the three panel openers, never cleared
        self.selectMenu = 0
        self.checkTutorialTimer = None
        self.killZombiesLabel = '0'
        self.HeadShotLabel = '0'
        self.ScoreLabel = '0'
        self.GoldLabel = '0'
        self.TopScoreLabel = '0'
        self.RankLabel = '-'
        self.tapCount_ = 0
        self.pauseFlag = False
        self.stopWalkingFlag = False
        self.shotAngle = 0.0
        self.shotgunShot = False
        self.isShake = False
        self.missionCompletSounding = False
        self.LVCount = 0
        self.monster_num = 0
        self.monsterHPGain = 1.0
        self.LVUP = 1
        self.bBOSS = False
        self.gameMode = 1
        self.isTutorial = isTutorial
        self.isTutorialEnd = 0
        self.GirlMonsterNumber = 0
        self.DieFlag = False
        self.reloadWeaponNumber = 0
        self.noAtt = False
        self.groundMapData = None
        self.soundMapData = None
        self.actionMapData = None
        self.running = False
        self.score = 0
        # Stage_Tutorial legitimately runs with TUTORIAL == 0; only Stage_1_E itself
        # standing still is worth a warning.
        self.warn_if_not_walking = True

    # ================================================================ loading
    # -[Stage_1_E viewDidLoad] 0x2c784
    def viewDidLoad(self):
        d = UserDefaults.standardUserDefaults()
        self.app.BGMusicStop()
        self.app.weaponHave()
        self.weaponInit()
        # 0x2cd52: isTutorial is the raw NSUserDefaults value, and the name is the wrong
        # way round - "TUTORIAL" is written as "1" when the tutorial is *finished*
        # (-[Stage_1_E tutorialEnd:] 0x33fc8).  So isTutorial != 0 means "past the
        # tutorial", which is why that is the case that starts the walk timer
        # (0x2e08e: cmp r0, #0 ; beq - skip) and the case that spends ammunition
        # (0x2f41a).  A save with TUTORIAL unset never walks; the tutorial comes first.
        self.isTutorial = d.intForKey_('TUTORIAL')
        if self.isTutorial == 0:                     # 0x2cd56
            self.isTutorialEnd = 1

        self.gamePlayer = PlayerControl()
        self.gamePlayer.HP = 3                      # 0x2cdc6
        self.startWeapon()
        self.gamePlayer.playerXplot = 20            # 0x2cf04
        self.gamePlayer.playerYplot = 680           # 0x2cf1a
        self.monsterHPGain = 1.0                    # 0x2cf38
        self.LVUP = 1                               # 0x2cf48
        self.MonsterBuffer = []
        self.monsterArray = list(MONSTER_ARRAY)
        # 0x2d360: gameMode = arc4random() % 3 + 1
        self.gameMode = arc4random() % 3 + 1
        self.changeGameMode()
        self.app.playSound_Gain_Pos_z_reprats_(46, 0.2, (0.0, 0.0), 0, False)  # Now Loading
        self.MapInitInBundle()

    # -[Stage_1_E MapInitInBundle] 0x2dbbc
    def MapInitInBundle(self):
        def read(name, ext=None):
            p = paths.path_for_resource(name, ext)
            with open(p, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        self.actionMapData = read('a_CH1_E', 'txt')
        self.groundMapData = read('g_CH1_E')
        self.soundMapData = read('s_CH1_E', 'txt')
        self.stage = MakeMaps().initWithMapGroundFileString_soundPosFileName_actionPosFileName_(
            self.groundMapData, self.soundMapData, self.actionMapData)

        # The rain is the whole of gameMode 3's ambience, on the ambience player - not
        # the music player, which action cell 9 stops at the first corridor segment.
        # The other two play at 0.2: movw/movt r4, 0x3e4ccccd at 0x2ddfa/0x2de08.
        pb = self.app.playback
        if self.gameMode == 3:                                   # 0x2dd96
            pb.startAMBPlayer_type_soundGain_Loop_(
                'effect_forest_rainng', 'wav', 0.5, True)       # 0x2ddc8: 0x3f000000
        elif self.gameMode == 2:                                 # 0x2dd6c
            pb.startAMBPlayer_type_soundGain_Loop_('bgm_forest_amb', 'wav', 0.2, True)
        elif self.gameMode == 1:                                 # 0x2ddce
            pb.startAMBPlayer_type_soundGain_Loop_('bgm_cave_amb', 'wav', 0.2, True)

        self.app.playback.setListenerRotation_(self.facing.radians)
        self.running = True
        # 0x2e08e: the 1.0 s walk timer only exists once the tutorial has been cleared.
        if self.isTutorial:
            self.MotionSamplingTimer = RunLoop.main().scheduledTimer(
                1.0, self, 'MainControl', None, True)
        elif self.warn_if_not_walking:
            log.warning('TUTORIAL is 0, so -[Stage_1_E MapInitInBundle] does not start '
                        'MotionSamplingTimer and the player never walks. Play the '
                        'tutorial first (it is what sets the key).')

    # -[Stage_1_E changeGameMode] 0x2d64c
    def changeGameMode(self):
        pass

    # -[Stage_1_E weaponInit] 0x35008
    def weaponInit(self):
        for i in range(WEAPON_SLOTS):            # 0x3512c: `cmp r4, 8`
            w = WeaponControl()
            w.loadWeaponForGun_fileType_(WEAPON_FILES[i], 'plist')
            self.weaponSource[i] = w

    # -[Stage_1_E startWeapon] 0x35708
    def startWeapon(self):
        use = self.app.useWeapon
        if len(use) > 2 and use[2] != '0':       # 0x3572a: COLTUSE
            self.gamePlayer.useWepon = 2
        else:
            w = self.gamePlayer.useWepon
            while w < WEAPON_SLOTS:
                if w < len(use) and int(use[w] or 0) > 0:
                    break
                w += 1
            self.gamePlayer.useWepon = min(w, WEAPON_SLOTS - 1)
        weapon = self.weaponSource[self.gamePlayer.useWepon]
        if weapon:
            weapon.BulletCount = weapon.ReloadGun()

    # ============================================================== the clock
    # -[Stage_1_E MainControl] 0x3182c
    def MainControl(self, timer=None):
        if self.walkXFlag:                                        # 0x31848
            return
        if self.isShake:                                          # 0x3185e
            return

        # ---- breathing, 0x3186e..0x31974 -------------------------------
        self.breathCount += 1
        if self.breathCount >= 2:
            self.breathCount = 0
            if not self.brearhFlag:
                self.brearhFlag = True
                hp = self.gamePlayer.HP
                if hp >= 3:
                    self.breathNumber = 80          # player_breath_1
                elif hp >= 2:
                    self.breathNumber = 81
                elif hp >= 1:
                    self.breathNumber = 82
                self.app.playSound_Gain_Pos_z_reprats_(
                    self.breathNumber, 0.5, (0.0, 0.0), 0, False)
                RunLoop.main().perform(self, 'breath_', None, 1.0)

        # ---- walking, 0x319e0..0x31e32 ---------------------------------
        px = self.gamePlayer.playerXplot
        py = self.gamePlayer.playerYplot
        groundAhead = self.stage.movePlayGroundState_PlotY_(px, py - 1)   # 0x31a32
        actionHere = self.stage.movePlayActionState_PlotY_(px, py)        # 0x31a68

        if groundAhead >= 1:                                              # 0x31a70
            if py >= 23:                                                  # 0x31a80
                self.gamePlayer.playerYplot = py - 1
                y2 = self.gamePlayer.playerYplot
                if y2 == 29:                                              # 0x31ab2
                    self.app.playSound_Gain_Pos_z_reprats_(
                        SOUND_WARNING, 0.2, (0.0, 0.0), 0, False)
                elif y2 == 23:                                            # 0x31cfc
                    self._level_transition()
            else:
                if self.checkBoosDie():
                    self._level_transition()

        # ---- the action layer, 0x31e32..0x31f16 -------------------------
        if 1 <= actionHere <= 7:
            self.monster_num = actionHere
        elif actionHere == 8:                                             # 0x31e72
            if self.isTutorialEnd > 0:
                self.GirlMonsterNumber += 1
                if self.GirlMonsterNumber == 2:
                    self.MonsterInit_(10003)
                elif self.GirlMonsterNumber == 1:
                    self.MonsterInit_(10002)
        elif actionHere == 9:                                             # 0x31e4c
            self.app.playback.backgroundSoundStop()
        elif actionHere == 10:                                            # 0x31ec0
            # 0.02, well under the monsters: movw/movt r4, 0x3ca3d70a at 0x321d4/0x321dc
            pb = self.app.playback
            if self.gameMode >= 2:
                pb.startBGPlayer_type_soundGain_Loop_('bgm_forest', 'wav', 0.02, True)
            else:
                pb.startBGPlayer_type_soundGain_Loop_('bgm_cave', 'wav', 0.02, True)

        # ---- spawn, attack, upkeep, 0x31f16..0x31f94 --------------------
        self.MakeMonster_(self.monster_num)
        self.MonsterAttPlayer()
        self.HPImageCount()
        RunLoop.main().perform(self, 'timerLeft', None, 0.0)

        # ---- death, 0x31fa8..0x320da ------------------------------------
        if not self.DieFlag and self.gamePlayer.HP <= 0:
            self.DieFlag = True
            self.app.playSound_Gain_Pos_z_reprats_(
                SOUND_GAME_OVER, 1.0, (0.0, 0.0), 0, False)
            # 0x320bc/0x320ce: the delay is 0x3FF4CCCCC0000000, which is 1.3 s.
            RunLoop.main().perform(self, 'playerDie_', None, 1.3)

    # -[Stage_1_E timerLeft] 0x31818
    def timerLeft(self, *_):
        self.walkXFlag = False

    # -[Stage_1_E breath:] 0x325e0
    def breath_(self, *_):
        self.brearhFlag = False

    # -[Stage_1_E checkBoosDie] 0x3604c
    def checkBoosDie(self):
        """Whether the level is allowed to end.

            if (MonsterBuffer.count < 1) return YES;
            for (i = 0; i < count; i++) {
                m  = MonsterBuffer[i];
                r2 = gameMode - 2;                       // 0x360c4
                if ((unsigned)r2 < 2)      r1 = m.monsterNumber;   // gameMode 2 or 3
                else if (gameMode == 1)    r1 = m.monsterNumber;
                else                       continue;
                if (r1 == r2) return NO;                 // 0x360ec
            }
            return YES;

        The comparison is against ``gameMode - 2``, not against a boss id, so it only
        ever bites in gameMode 3, where it blocks the level on a live kind-1 zombie;
        gameMode 2 compares against 0, which nothing is, and gameMode 1 compares
        against -1.  Almost certainly not what was meant, but it is what runs -
        see docs/DIVERGENCES.md.  ``bBOSS`` is declared and never touched anywhere in
        the binary.
        """
        if len(self.MonsterBuffer) < 1:
            return True
        r2 = self.gameMode - 2
        for m in self.MonsterBuffer:
            if 0 <= r2 < 2 or self.gameMode == 1:
                if m.monsterNumber == r2:
                    return False
        return True

    def _level_transition(self):
        pb = self.app.playback
        pb.backgroundSoundStop()
        RunLoop.main().perform(self, 'ChangeLevel_', None, 1.0)
        if self.MotionSamplingTimer is not None and self.MotionSamplingTimer.isValid():
            self.MotionSamplingTimer.invalidate()
        self.MotionSamplingTimer = None

    # -[Stage_1_E ChangeLevel:] 0x322e0
    def ChangeLevel_(self, *_):
        self.gamePlayer.playerYplot = 680               # 0x32302
        self.monsterHPGain = self.monsterHPGain * 1.5   # 0x32314
        self.LVUP += 1
        self.gameMode = 1 if self.gameMode != 1 else 2  # 0x32350
        self.changeGameMode()
        self.app.playSound_Gain_Pos_z_reprats_(
            SOUND_ZOMBIES_COMING, 1.0, (0.0, 0.0), 0, False)
        self.MotionSamplingTimer = RunLoop.main().scheduledTimer(
            1.0, self, 'MainControl', None, True)

    # ============================================================== monsters
    # -[Stage_1_E MakeMonster:] 0x36100
    def MakeMonster_(self, tier):
        self.LVCount += 1
        if not (1 <= tier <= 7):                        # 0x3611a
            return
        cap = self.LVUP + 2                             # 0x3612e
        if self.LVCount < 3:                            # 0x36144
            return
        if len(self.MonsterBuffer) >= cap:              # 0x36168
            return
        mod, off = MAKE_MONSTER_TIER[tier]
        idx = (arc4random() % mod) + off
        if self.checkMonsterArray_(idx) == -1:          # 0x361ec
            return
        self.LVCount = 0
        type_id = int(self.monsterArray[idx])
        self.MonsterInit_(type_id)

    # -[Stage_1_E checkMonsterArray:] 0x36458
    def checkMonsterArray_(self, idx):
        """-1 when the lane this type walks in already has a monster in it."""
        if not (0 <= idx < len(self.monsterArray)):
            return -1
        lane = int(self.monsterArray[idx]) % 10
        for m in self.MonsterBuffer:
            if m.MovingType == lane:
                return -1
        return idx

    # -[Stage_1_E MonsterInit:] 0x36524
    def MonsterInit_(self, type_id):
        """Pick this monster's voices, then build it.

        The original builds, per kind, the list of sound numbers the live monsters are
        already using and takes the first candidate that is free (0x37638..0x376a4).
        """
        kind = self._kind_for_type(type_id)
        table = MONSTER_SOUNDS.get(kind)
        if table is None:
            log.warning('no sound table for monster kind %d (type%d)', kind, type_id)
            return
        cave, forest, damage, die, hitp = table
        coming_list = cave if self.gameMode == 1 else forest      # 0x36562

        in_use = {m.comingSound for m in self.MonsterBuffer}
        coming = self._first_free(coming_list, in_use)
        if coming is None:
            return                                   # every voice for this kind is busy
        hit = self._first_free(damage, {m.hitSound for m in self.MonsterBuffer}) or damage[0]
        dies = self._first_free(die, {m.dieSound for m in self.MonsterBuffer}) or die[0]
        php = self._first_free(hitp, {m.playerHitSound for m in self.MonsterBuffer}) or hitp[0]

        approach = push = 0
        if kind in SHAKE_SOUNDS:
            al_, pl = SHAKE_SOUNDS[kind]
            approach = self._first_free(al_, {m.shakeMonsterApproachSound
                                              for m in self.MonsterBuffer}) or al_[0]
            push = self._first_free(pl, {m.shakeMonsterPushSound
                                         for m in self.MonsterBuffer}) or pl[0]

        m = MonsterControl()
        if m.initWithMonsterPatern(type_id, self.app, coming, hit, php, dies,
                                   approach, push, self.monsterHPGain) is None:
            return
        # -[MonsterControl initWithMonsterPatern:...] already called MonsterStart:
        # (0x10c3e), so MonsterInit: only has to keep the monster (0x392da).
        self.MonsterBuffer.append(m)

    @staticmethod
    def _first_free(candidates, in_use):
        for c in candidates:
            if c not in in_use:
                return c
        return None

    @staticmethod
    def _kind_for_type(type_id):
        """``몬스터종류`` without opening the plist.

        The 50 ids in ``monsterArray`` are ``kind*10 + lane`` with the first kind written
        bare (1..5), so kind = id // 10 + 1.  The scripted ids are their own kinds.
        """
        if type_id >= 10000:
            return 21 if type_id in (10001, 10002) else 22
        if type_id >= 5000:
            return 12
        if type_id >= 100:
            return min(12, type_id // 10)
        return type_id // 10 + 1

    # -[Stage_1_E MonsterAttPlayer] 0x3b040
    def MonsterAttPlayer(self):
        for i, m in enumerate(list(self.MonsterBuffer)):
            if m.monsterRange > 25.0:                  # 0x3b104: vmov.f32 d8, #25.0
                continue
            if m.shakeMonsterFlag:                     # 0x3b27e - it grabs you
                self._grabbed_by(i, m)
                return
            if m.monsterNumber == 21:                  # 0x3b28e - the girl heals
                if self.gamePlayer.HP <= 3:
                    self.gamePlayer.HP += 1
                m.DieMonster()
                self._remove(m)
                continue
            self.gamePlayer.HP -= 1                    # 0x3b2f4
            m.hitPlayer()
            self._remove(m)
            self.playerDamage_(None)

    def _grabbed_by(self, index, m):
        """-[Stage_1_E MonsterAttPlayer] 0x3b5ee - zombie_8 takes hold.

            shakeMonsterNumber = i;
            shakeFlag = 1;  isShake = YES;
            if (isTutorial == 0) noAtt = YES;                     // 0x3b632
            [m shakeMonster];
            shakeMonsterTimer = [NSTimer scheduledTimerWithTimeInterval:0.1
                                    target:self selector:@selector(shakingFind)
                                    userInfo:nil repeats:YES];
            [self performSelector:@selector(NonShaking) withObject:nil
                       afterDelay:m.shakeMonsterApproachTime];

        From here you have ``shakeMonsterApproachTime`` seconds to shake free, which
        takes ten shakes.  Free in time and the monster dies; too slow and it hits you.
        """
        self.shakeMonsterNumber = index
        self.shakeFlag = 1
        self.isShake = True
        self.shakeCount = 0
        if self.isTutorial == 0:                       # 0x3b640
            self.noAtt = True
        m.shakeMonster()
        loop = RunLoop.main()
        self._invalidate_shake_timer()
        self.shakeMonsterTimer = loop.scheduledTimer(
            0.1, self, 'shakingFind', None, True)      # 0x3b656: 0.1 s, repeating
        loop.perform(self, 'NonShaking', None, m.shakeMonsterApproachTime)

    def _remove(self, m):
        if m in self.MonsterBuffer:
            self.MonsterBuffer.remove(m)

    # -[Stage_1_E MonsterDealloc] 0x3bd3c
    def MonsterDealloc(self):
        for m in list(self.MonsterBuffer):
            m.dealloc()
        self.MonsterBuffer = []

    # -[Stage_1_E MonsterStop] 0x3af58 / -[Stage_1_E MonsterReStart] 0x3afcc
    def MonsterStop(self):
        for m in self.MonsterBuffer:
            m.StopPlayGame()

    def MonsterReStart(self):
        for m in self.MonsterBuffer:
            m.ReplayGame()

    # ============================================================= attacking
    # -[Stage_1_E MovingShot:] 0x2ec98 - the pan gesture, reduced to its angle.
    def MovingShot_(self, angle_degrees):
        """``angle_degrees`` is the swipe's ``atan2`` bearing, exactly the value the
        original computes at 0x2efc8..0x2f060 and stores in ``shotAngle``."""
        if self.missionCompletSounding:
            return
        self.shotAngle = float(angle_degrees) % 360.0
        if self.shotFlag:                                      # 0x2f07e
            return
        self.posX = self.posY = 0.0
        self.shotFlag = True
        if self.isShake:                                       # 0x2f0b4
            self.shotFlag = False
            return
        if self.noAtt:                                         # 0x2f0ca
            return

        w = self.gamePlayer.useWepon
        weapon = self.weaponSource[w]
        self.app.stopSoundBufNumber_(weapon.ShotSoundNumber)   # 0x2f130

        if w == 0:
            self._throw_grenade(weapon)
            return

        lane = self._lane_for_angle(self.shotAngle, melee=(w in (1, 7)))
        if lane == 'reload':
            # 0x2f9e4 - a gun swiped to 6 o'clock reloads instead of firing, and the
            # attack ends there (`b 0x2fdc2`).
            self.GunReloadAction_()
            return
        self.shotMonster = lane

        if weapon.BulletCount <= 0:                            # 0x2f3f6
            self.app.playSound_Gain_Pos_z_reprats_(
                SOUND_NO_BULLETS, 0.5, (0.0, 0.0), 0, False)
            RunLoop.main().perform(self, 'stopShot_', None, weapon.ShotTime)
            return

        # 0x2f41a: ammunition is only spent once the tutorial has been cleared.
        if self.isTutorial and w not in (1, 7):
            weapon.BulletCount -= 1

        self.app.playSound_Gain_Pos_z_reprats_(
            weapon.ShotSoundNumber, weapon.ShotSoundgain, (0.0, 0.0), 40, False)

        if w in (1, 7):
            RunLoop.main().perform(self, 'MonsterDamageKnife', None, 0.0)
        else:
            RunLoop.main().perform(self, 'MonsterDamage', None, 0.0)
        RunLoop.main().perform(self, 'stopShot_', None, weapon.ShotTime)

    def _throw_grenade(self, weapon):
        """0x2f1bc - the grenade comes out of GRENADECOUNT, not a magazine."""
        d = UserDefaults.standardUserDefaults()
        n = d.intForKey_('GRENADECOUNT')
        if n <= 0:
            self.app.playSound_Gain_Pos_z_reprats_(
                SOUND_NO_BULLETS, 0.5, (0.0, 0.0), 0, False)
            RunLoop.main().perform(self, 'stopShot_', None, weapon.ShotTime)
            return
        self.app.playSound_Gain_Pos_z_reprats_(
            weapon.ShotSoundNumber, weapon.ReloadSoundGain, (0.0, 0.0), 40, False)
        if self.isTutorial:                        # 0x2f288
            d.setObject_forKey_(str(n - 1), 'GRENADECOUNT')
            d.synchronize()
        RunLoop.main().perform(self, 'MonsterDamage', None, 0.0)
        RunLoop.main().perform(self, 'stopShot_', None, weapon.ShotTime)

    @staticmethod
    def _lane_for_angle(a, melee=False):
        """0x2f16e..0x2fa34.  The five bands, and what the gap between them means.

        The tutorial teaches these as clock positions, which is what they are:

            9 o'clock  180 deg   lane 1        1:30   57 deg   lane 4
            10:30      123 deg   lane 2        3      0 deg    lane 5
            12          90 deg   lane 3        6    270 deg    reload

        A gun swiped into the gap - roughly 242.5..300.5, which is 6 o'clock - does not
        attack at all: 0x2f9e4 calls ``GunReloadAction:``.  That is the reload gesture,
        and ``tutorialSix`` ("if you make your finger 6") is the beat that teaches it.
        A melee weapon in the same gap falls through to lane 3 instead (0x2f99e).

        Returns the lane, or ``'reload'``.
        """
        if 112.5 < a < 155.5:
            return 2
        if 22.5 < a < 62.5:
            return 4
        if 62.5 < a < 112.5:
            return 3
        hi = 222.5 if melee else 242.5          # 0x2f838 / 0x2f872
        if 156.5 < a < hi:
            return 1
        wrap = 320.5 if melee else 300.5        # 0x2f982 / 0x2f9c6
        if (0 <= a < 22.5) or (wrap < a <= 360):
            return 5
        return 3 if melee else 'reload'

    # -[Stage_1_E stopShot:] 0x36038
    def stopShot_(self, *_):
        self.shotFlag = False

    # -[Stage_1_E monsterHitHeadFind] 0x3ab88
    def monsterHitHeadFind(self):
        """The nearest monster in the aimed lane that is inside the weapon's range."""
        weapon = self.weaponSource[self.gamePlayer.useWepon]
        if weapon is None:
            return None
        bands = SHOT_BANDS.get(self.shotMonster, [])
        best = None
        for m in self.MonsterBuffer:
            a = m.MovingPosAngle
            if not any(lo <= a <= hi for lo, hi in bands):
                continue
            if float(weapon.Range) < m.monsterRange:            # 0x3ad82
                continue
            if best is None or m.monsterRange < best.monsterRange:
                best = m
        return best

    # -[Stage_1_E MonsterDamage] 0x3a0d8
    def MonsterDamage(self, *_):
        if self.isShake:                                        # 0x3a0f4
            self.shotFlag = False
            return
        weapon = self.weaponSource[self.gamePlayer.useWepon]
        if self.gamePlayer.useWepon != 0:
            m = self.monsterHitHeadFind()
            if m is None:
                return
            m.MonsterHitSoundDealloc()
            if m.headShotFlag:                                  # isHeadShot, 0x3a174
                m.isHeadShot = False
                m.HP -= weapon.Damage * 2                       # 0x3a1dc
                self.gamePlayer.HeadShotCount += 1
                self.app.playSound_Gain_Pos_z_reprats_(
                    SOUND_HEADSHOT, 0.1, m.Pos, 40, False)
            else:
                m.HP -= weapon.Damage
            m.MonsterHitSound_(None)
            if m.HP <= 0:
                self.gamePlayer.killMonsterCount += 1        # 0x39cee
                self.MonsterKillCount_(m)
                self._remove(m)
        else:
            # the grenade hits every live monster
            for m in list(self.MonsterBuffer):
                m.HP -= weapon.Damage
                m.MonsterHitSound_(None)
                if m.HP <= 0:
                    self.gamePlayer.killMonsterCount += 1    # 0x3a3ae
                    self.MonsterKillCount_(m)
                    self._remove(m)

    # -[Stage_1_E MonsterDamageKnife] 0x392fc
    def MonsterDamageKnife(self, *_):
        """Melee: the attack sound first, then the same damage resolution."""
        weapon = self.weaponSource[self.gamePlayer.useWepon]
        if weapon and weapon.att1SoundNumber:
            self.app.playSound_Gain_Pos_z_reprats_(
                weapon.att1SoundNumber, weapon.att1SoundGain, (0.0, 0.0), 40, False)
        self.MonsterDamage()

    # -[Stage_1_E MonsterKillCount:] 0x39e00
    #   A chain of `cmp monsterNumber, N` that bumps the matching per-kind tally.
    #   It does NOT touch killMonsterCount and keeps no score: every call site does
    #   `setKillMonsterCount:+1` first (0x39cee, 0x3a3ae, 0x3aad4), and the score is
    #   derived in ReadScore.
    def MonsterKillCount_(self, m):
        p = self.gamePlayer
        n = m.monsterNumber
        if 1 <= n <= 11:
            setattr(p, 'killMonster%dcount' % n, getattr(p, 'killMonster%dcount' % n) + 1)
        elif n >= 5000:
            p.killMonster5000count += 1
        self.ReadScore()

    # -[Stage_1_E ReadScore] 0x3bf38
    #
    #   score = kill5000 * 2000                      (0x3c144: mov.w r1, #0x7d0)
    #         + (kill9  + kill10) * 300              (0x3c14c: #0x12c)
    #         + (kill7  + kill8 ) * 250              (0x3c148: #0xfa)
    #         + (kill5  + kill6 ) * 225              (0x3c162: #0xe1)
    #         + (kill3  + kill4 ) * 175              (0x3c16e: #0xaf)
    #         + (kill1  + kill2 + kill11) * 150      (0x3c17a: #0x96)
    #
    #   and then, if there was at least one headshot, scaled by a multiplier the
    #   original builds as a *string* and parses back (0x3bf82..0x3c02a):
    #
    #       hs >= 100 : [NSString stringWithFormat:@"%d.%d", hs/100 + 1, hs % 100]
    #       hs >=  10 : @"1.%d"  % hs
    #       else      : @"1.0%d" % hs
    #
    #   so 5 headshots is x1.05, 42 is x1.42, 150 is x2.50.
    def ReadScore(self):
        p = self.gamePlayer
        score = (p.killMonster5000count * 2000
                 + (p.killMonster9count + p.killMonster10count) * 300
                 + (p.killMonster7count + p.killMonster8count) * 250
                 + (p.killMonster5count + p.killMonster6count) * 225
                 + (p.killMonster3count + p.killMonster4count) * 175
                 + (p.killMonster1count + p.killMonster2count
                    + p.killMonster11count) * 150)
        hs = p.HeadShotCount
        if hs >= 1:
            score = int(float(score) * self.headshot_multiplier(hs))
        self.score = score
        return score

    @staticmethod
    def headshot_multiplier(hs):
        if hs >= 100:
            s = '%d.%d' % (hs // 100 + 1, hs % 100)
        elif hs >= 10:
            s = '1.%d' % hs
        else:
            s = '1.0%d' % hs
        return float(s)

    # -[Stage_1_E MonsterDie:] 0x3ae84
    def MonsterDie_(self, index):
        if 0 <= index < len(self.MonsterBuffer):
            m = self.MonsterBuffer[index]
            m.DieMonster()
            self._remove(m)

    # ================================================================ player
    # -[Stage_1_E playerDamage:] 0x3bc44
    def playerDamage_(self, *_):
        self.app.playSound_Gain_Pos_z_reprats_(
            SOUND_PLAYER_DAMAGE, 1.0, (0.0, 0.0), 0, False)

    # -[Stage_1_E playerDie:] 0x3bc74
    def playerDie_(self, *_):
        """The end-of-game music, and the result panel eleven seconds behind it.

        0x3bd2c stores 0x4026000000000000 as the delay - 11.0 s, which is how long
        ``bgm_game_end`` runs.  The run is not over until ``missionFailTell:`` fires.
        """
        self.app.playSound_Gain_Pos_z_reprats_(
            SOUND_BGM_GAME_END, 1.0, (0.0, 0.0), 0, False)   # 0x3bcaa
        self.walkXFlag = True                                 # 0x3bcc6
        self.missionCompletSounding = True                    # 0x3bcd4
        if self.MotionSamplingTimer is not None and self.MotionSamplingTimer.isValid():
            self.MotionSamplingTimer.invalidate()
        self.MotionSamplingTimer = None
        RunLoop.main().perform(self, 'missionFailTell_', None, 11.0)   # 0x3bd30

    # -[Stage_1_E HPImageCount] 0x3c668
    def HPImageCount(self):
        pass

    # -[Stage_1_E SuccessOrFailMission] 0x34778
    #   Stops the clock and the monsters, fills the panel's labels and works out
    #   whether the run beat either stored top score.  Which sound plays was decided
    #   by its callers, -[Stage_1_E MissionSuccessTell] (0x32c10) and
    #   -[Stage_1_E missionFailTell:] (0x32760).
    def SuccessOrFailMission(self):
        if self.MotionSamplingTimer is not None and self.MotionSamplingTimer.isValid():
            self.MotionSamplingTimer.invalidate()
        self.MotionSamplingTimer = None
        self.walkXFlag = True                                 # 0x347dc
        self.brearhFlag = True                                # 0x347ea
        self.MonsterStop()                                    # 0x347f0
        self._fill_result_labels()                            # 0x34826..0x34bd0
        score = self.score

        d = UserDefaults.standardUserDefaults()
        top = d.intForKey_('TOPSCORE')                        # 0x34c2c
        week = d.intForKey_('TOPSCOREWEEK')                   # 0x34c4e
        if score > top:                                       # 0x34c56
            d.setObject_forKey_('%d' % score, 'TOPSCORE')     # 0x34ca4
            d.synchronize()
        if score > week:                                      # 0x34cc0
            # 0x34cce..0x34e24 expires WEEKTIME first, then stores the week's best and
            # uploads it when the account keys are set.  There is no server left to
            # upload to, so the key is kept and the send is not made.
            d.setObject_forKey_('%d' % score, 'TOPSCOREWEEK')  # 0x34e7c
            d.synchronize()
        raw = d.stringForKey_('TOPSCORE')                     # 0x34f00
        self.TopScoreLabel = raw if raw else '0'              # 0x34f46
        self.selectMenu = 0

    # -[Stage_1_E MissionSuccessTell] 0x32c10
    def MissionSuccessTell(self, *_):
        self.missionCompletSounding = False                   # 0x32c34
        self.bStop = True                                     # 0x32c3a
        if self.gameMode == 1:                                # 0x32c5c
            self.app.stopSoundBufNumber_(88)                  # bgm_cave_amb
        gold = self.ObtainedGold()
        self.app.haveGold += gold                             # 0x32e70
        d = UserDefaults.standardUserDefaults()
        d.setObject_forKey_('%d' % self.app.haveGold, 'GOLD')  # 0x32ee8
        if self.app.stage <= 11:                              # 0x32efe
            d.setObject_forKey_('11', 'STAGE')                # 0x32f44
            self.app.stage = 11                               # 0x32f58
        d.synchronize()                                       # 0x32f7a
        self.gameState = 2                                    # 0x32f9c
        self.app.playSound_Gain_Pos_z_reprats_(
            SOUND_MISSION_SUCCESS, 0.5, (0.0, 0.0), 0, False)  # 0x32fac
        self.updateTopscoreRank()                             # 0x32fbe
        self.SuccessOrFailMission()                           # 0x32fca

    # -[Stage_1_E missionFailTell:] 0x32760
    def missionFailTell_(self, *_):
        """The game-over panel.  It plays 354 ``game over``, not 228 ``mission fail``
        - 228 is only ever silenced, never played, by this class."""
        self.missionCompletSounding = False                   # 0x32788
        self.bStop = True                                     # 0x3278e
        if self.gameMode == 1:                                # 0x327b0
            self.app.stopSoundBufNumber_(88)                  # bgm_cave_amb
        self.gameState = 3                                    # 0x32802
        self.app.playSound_Gain_Pos_z_reprats_(
            SOUND_GAME_OVER, 0.5, (0.0, 0.0), 0, False)       # 0x32814
        gold = self.ObtainedGold()
        self.app.haveGold += gold                             # 0x32ad2
        d = UserDefaults.standardUserDefaults()
        d.setObject_forKey_('%d' % self.app.haveGold, 'GOLD')  # 0x32b4c
        # 0x32aa8 sends the score to Game Center; there is no Game Center here.
        self.updateTopscoreRank()                             # 0x32b5e
        self.SuccessOrFailMission()                           # 0x32b70
        d.setObject_forKey_(                                  # 0x32be6
            '%d' % (d.intForKey_('REVIEWCOUNT') + 1), 'REVIEWCOUNT')
        d.synchronize()

    # =============================================================== weapons
    # -[Stage_1_E gunChangeAction:] 0x35a08 / -[Stage_1_E doubleTapChangeWeapon:] 0x2ec70
    def gunChangeAction_(self, step=1):
        """Cycle to the next owned-and-equipped weapon."""
        use = self.app.useWeapon
        w = self.gamePlayer.useWepon
        for _ in range(WEAPON_SLOTS):
            w = (w + step) % WEAPON_SLOTS
            if w < len(use) and use[w] == '1':
                break
        self.gamePlayer.useWepon = w
        weapon = self.weaponSource[w]
        if weapon:
            # No reload here: gunChangeAction: never calls ReloadGun or setBulletCount,
            # so each weapon keeps the rounds it had (a full magazine from weaponInit).
            self.app.playSound_Gain_Pos_z_reprats_(
                weapon.weaponChangeSoundNumber, weapon.weaponChangeSoundGain,
                (0.0, 0.0), 0, False)

    def doubleTapChangeWeapon_(self, *_):
        self.gunChangeAction_(1)

    def threeTapChangeWeapon_(self, *_):
        self.gunChangeAction_(-1)

    # -[Stage_1_E GunReloadAction:] 0x3516c
    def GunReloadAction_(self, *_):
        weapon = self.weaponSource[self.gamePlayer.useWepon]
        if weapon is None:
            return
        self.app.playSound_Gain_Pos_z_reprats_(
            weapon.ReloadSoundnumber, weapon.ReloadSoundGain, (0.0, 0.0), 0, False)
        RunLoop.main().perform(self, 'reloadGun_', None, weapon.ReloadTime)

    # -[Stage_1_E reloadGun:] 0x35ef0
    def reloadGun_(self, *_):
        weapon = self.weaponSource[self.gamePlayer.useWepon]
        if weapon:
            weapon.BulletCount = weapon.ReloadGun()

    # ================================================================ facing
    def turn_left(self):
        self.facing.rotationLeftEight()
        self.app.playback.setListenerRotation_(self.facing.radians)

    def turn_right(self):
        self.facing.rotationRightEight()
        self.app.playback.setListenerRotation_(self.facing.radians)

    # -[Stage_1_E accelerometer:didAccelerate:] 0x3c84c - the shake-free struggle.
    def shake_step(self):
        """-[Stage_1_E accelerometer:didAccelerate:] 0x3c84c

            if (isShake != 1)            return;
            if (shakeFlag == 0)          return;      // already free
            if (acceleration.x < 1.0)    return;
            if (++shakeCount >= 10)      shakeFlag = 0;

        Clearing ``shakeFlag`` is all it does; ``shakingFind``, polling every 0.1 s,
        is what notices and performs the escape.
        """
        if not self.isShake:
            return
        if self.shakeFlag == 0:
            return
        self.shakeCount += 1
        if self.shakeCount >= 10:                   # 0x3c8b0
            self.shakeFlag = 0

    # -[Stage_1_E shakingFind] 0x3b95c - the 0.1 s poll; the escape.
    def shakingFind(self, timer=None):
        if self.shakeFlag != 0:                     # 0x3b976, still held
            return
        self.shakeFlag = 1
        loop = RunLoop.main()
        loop.cancelPerform(self, 'NonShaking')      # 0x3b9ae
        self._invalidate_shake_timer()
        if not (0 <= self.shakeMonsterNumber < len(self.MonsterBuffer)):
            self.isShake = False
            return
        m = self.MonsterBuffer[self.shakeMonsterNumber]
        m.stopShakeMonsterSound_(None)
        self.app.playSound_Gain_Pos_z_reprats_(
            m.shakeMonsterPushSound, m.shakeMoneterPushGain, m.Pos, 40, False)
        # shaking free kills it (0x3baa0..0x3bad8)
        self.gamePlayer.killMonsterCount += 1
        self.MonsterKillCount_(m)
        del self.MonsterBuffer[self.shakeMonsterNumber]
        self.isShake = False                        # 0x3bb6c

    # -[Stage_1_E NonShaking] 0x3b6f8 - the time ran out; the grab lands.
    def NonShaking(self, *_):
        if self.shakeFlag == 0:                     # 0x3b714, already escaped
            self.isShake = False
            return
        self._invalidate_shake_timer()
        if not (0 <= self.shakeMonsterNumber < len(self.MonsterBuffer)):
            self.isShake = False
            return
        m = self.MonsterBuffer[self.shakeMonsterNumber]
        if self.isTutorial:                         # 0x3b79e
            self.gamePlayer.HP -= 1
        m.hitPlayer()
        if self.gamePlayer.HP >= 0:                 # 0x3b8bc
            RunLoop.main().perform(self, 'playerDamage_', None, 0.0)
        del self.MonsterBuffer[self.shakeMonsterNumber]
        self.isShake = False                        # 0x3b91a

    def _invalidate_shake_timer(self):
        if self.shakeMonsterTimer is not None and self.shakeMonsterTimer.isValid():
            self.shakeMonsterTimer.invalidate()
        self.shakeMonsterTimer = None

    # ================================================================== misc
    def teardown(self):
        """Leaving the stage, however it happens - the menu button, Escape, closing
        the window.  UINavigationController tore the whole view down and its sounds
        with it; here the looping footsteps and the two players have to be stopped by
        hand, or they play on under the menu."""
        self.running = False
        self._invalidate_shake_timer()
        if self.MotionSamplingTimer is not None and self.MotionSamplingTimer.isValid():
            self.MotionSamplingTimer.invalidate()
        self.MotionSamplingTimer = None
        self.MonsterStop()                      # each monster's walking loop
        self.MonsterDealloc()
        pb = self.app.playback
        if pb is not None:
            pb.AMBSoundStop()                   # the ambience or the rain
            pb.backgroundSoundStop()            # the level music
        RunLoop.main().cancelPerform(self)

    # ============================================ the pause and result screen
    #
    # One panel serves three states, which ``gameState`` names:
    #
    #     0   playing
    #     1   paused             -[Stage_1_E StopPlayAction:]    0x34168
    #     2   mission complete   -[Stage_1_E MissionSuccessTell] 0x32f9c
    #     3   dead               -[Stage_1_E missionFailTell:]   0x32802
    #
    # ``-[Stage_1_E selectTapPointSoundStart]`` (0x30168) maps the finger's Y to one
    # of ten bands, stores the band in ``selectMenu``, plays that row's label and then
    # schedules the row's reader 2 s later (0x3097c and its copies).  A double tap
    # runs ``-[Stage_1_E tapCount]`` (0x2fec8), whose ``tbb`` table decides what the
    # row does.  There is no finger here, so Up and Down walk the same ten rows in the
    # same order and Enter is the double tap - the shape the main menu was ported in.

    #: The rows top to bottom, by the Y bands at 0x308b6..0x311ec.
    PAUSE_ROWS = (1, 2, 3, 4, 5, 9, 10, 6, 7, 8)

    #: Rows whose label does not depend on the state (0x30930..0x311c2).
    PAUSE_ROW_SOUND = {2: 230, 3: 231, 4: 232, 5: 233, 9: 357, 10: 356,
                       7: 224, 8: 355}

    #: ...and the reader each one schedules behind its label.
    PAUSE_ROW_READER = {2: 'ReadNumberOfZombies', 3: 'ReadNumberOfHeadshot',
                        4: 'ReadScore', 5: 'ReadObtainedGold',
                        9: 'ReadRank', 10: 'ReadTopScore'}

    #: 0x3097c, ``mov.w r6, #0x40000000`` - the high half of 2.0.
    READ_DELAY = 2.0

    # -[Stage_1_E StopElseSpeak] 0x30018
    def StopElseSpeak(self):
        """Silence the panel: every label it can speak, the number reader, and any
        reader still queued behind a label."""
        for num in (229, 230, 231, 232, 233, 223, 224, 225, 227, 228, 226,
                    354, 355, 356, 357):
            self.app.stopSoundBufNumber_(num)
        self.app.readStop()
        loop = RunLoop.main()
        for sel in ('ReadNumberOfZombies', 'ReadNumberOfHeadshot',
                    'ReadScore', 'ReadObtainedGold'):
            loop.cancelPerform(self, sel)

    # -[Stage_1_E blindModeOff] / -[Stage_1_E blindModeSelectedMenu] 0x2d9e0
    # Both are UIKit: one clears every button's highlight, the other rounds the
    # corners of the selected one (``round10``).  Nothing to draw here.
    def blindModeOff(self):
        pass

    def blindModeSelectedMenu(self):
        pass

    def pause_rows(self):
        """The rows the panel offers in the state it is in.

        Row 6 returns before it speaks when ``gameState == 3`` (0x30efe), so there is
        no continue and no next stage after a death - and ``missionFailTell:`` hides
        the continue button itself at 0x327de.
        """
        return tuple(n for n in self.PAUSE_ROWS
                     if not (n == 6 and self.gameState == 3))

    def pause_select(self, row):
        """One band of ``selectTapPointSoundStart``: name the row, then read it.

        Each band in the original guards on its own flag (``pauseFlag``,
        ``killZombiesFlag``, ...) so a finger resting on a row does not say it twice.
        Moving between rows on a keyboard is one event, so the move is the guard.
        """
        self.selectMenu = row
        self.StopElseSpeak()

        if row == 1:                                          # 0x308b6
            if self.gameState == 3:
                sound = 354                                   # game over
            elif self.gameState == 1:
                sound = 229                                   # paused
            else:
                sound = None                                  # silent after a success
        elif row == 6:                                        # 0x30ede
            if self.gameState == 2:
                sound = 226                                   # next stage button
            elif self.gameState == 1:
                sound = 223                                   # continue button
            else:
                sound = None
        else:
            sound = self.PAUSE_ROW_SOUND.get(row)

        if sound is not None:
            self.app.playSound_Gain_Pos_z_reprats_(sound, 0.2, (0.0, 0.0), 0, False)
        reader = self.PAUSE_ROW_READER.get(row)
        if reader is not None:
            RunLoop.main().perform(self, reader, None, self.READ_DELAY)
        return sound

    def pause_move(self, step):
        """Up and Down in place of dragging a finger up and down the panel."""
        rows = self.pause_rows()
        if self.selectMenu in rows:
            row = rows[(rows.index(self.selectMenu) + step) % len(rows)]
        else:
            row = rows[0] if step > 0 else rows[-1]
        self.pause_select(row)
        return row

    # -[Stage_1_E tapCount] 0x2fec8
    def pause_activate(self):
        """The double tap.  The dispatch is the ``tbb`` table at 0x2ff32, read out of
        the binary byte for byte (04 25 61 30 3b 4b 51 57):

            selectMenu  1 -> 0x2ff3a   play 229 again
                        2 -> 0x2ff7c   ReadNumberOfZombies
                        3 -> 0x2fff4   nothing
                        4 -> 0x2ff92   ReadNumberOfHeadshot
                        5 -> 0x2ffa8   ReadObtainedGold
                        6 -> 0x2ffc8   continueAction:
                        7 -> 0x2ffd4   gameReplayAction:
                        8 -> 0x2ffe0   GameEndAction:

        Rows 9 and 10 fall past the ``cmp r0, 7``, so the rank and the top score
        cannot be re-read; rows 3 and 4 are off by one against their labels.  Both are
        in ``docs/DIVERGENCES.md``.
        """
        self.StopElseSpeak()
        row = self.selectMenu
        if row == 1:
            self.app.playSound_Gain_Pos_z_reprats_(229, 0.2, (0.0, 0.0), 40, False)
        elif row == 2:
            self.ReadNumberOfZombies()
        elif row == 4:
            self.ReadNumberOfHeadshot()
        elif row == 5:
            self.ReadObtainedGold()
        elif row == 6:
            self.continueAction_()
        elif row == 7:
            self.gameReplayAction_()
        elif row == 8:
            self.GameEndAction_()
        self.tapCount_ = 0                                    # 0x2fffe
        self.posX = 0.0                                       # 0x3000e
        self.posY = 0.0                                       # 0x30012
        return row

    # -[Stage_1_E spaekMenu] 0x34745
    def spaekMenu(self):
        self.app.playSound_Gain_Pos_z_reprats_(229, 0.2, (0.0, 0.0), 0, False)

    # -[Stage_1_E StopPlayAction:] 0x33df8
    def StopPlayAction_(self, *_):
        """The stop button.  While the tutorial is still running it ends the tutorial
        instead.

        ``bStop`` is set here and **never cleared anywhere in the binary**, so pausing
        works exactly once in the life of a stage - see ``docs/DIVERGENCES.md``.
        """
        if self.missionCompletSounding:                       # 0x33e16
            return False
        if not self.isTutorial:                               # 0x33e30 -> L_33ea4
            self.tutorial_skip()
            return False
        if self.bStop:                                        # 0x33e40
            return False
        self.bStop = True                                     # 0x33e48
        self.app.playSound_Gain_Pos_z_reprats_(10, 0.2, (0.0, 0.0), 0, False)
        if self.gameMode == 2:                                # 0x33e8c
            self.app.stopSoundBufNumber_(87)                  # bgm_forest_amb
        elif self.gameMode == 1:                              # 0x340c4
            self.app.stopSoundBufNumber_(88)                  # bgm_cave_amb
        if self.gameMode in (1, 2, 3):                        # L_340e4
            self.app.stopSoundBufNumber_(92)                  # bgm_cave
        if self.MotionSamplingTimer is not None and self.MotionSamplingTimer.isValid():
            self.MotionSamplingTimer.invalidate()
        self.MotionSamplingTimer = None
        self.gameState = 1                                    # 0x34168
        self.walkXFlag = True                                 # 0x34296
        self.brearhFlag = True                                # 0x342a4
        self.MonsterStop()                                    # 0x342aa
        self._fill_result_labels()                            # 0x34302..0x34574
        self.selectMenu = 0
        return True

    def tutorial_skip(self):
        """``StopPlayAction:`` 0x33ea4 - the branch taken while the tutorial is still
        running.  It stops the tutorial, writes the key that says it is finished and
        plays ``tutorial success``."""
        self.isTutorial = True                                # 0x33fec
        d = UserDefaults.standardUserDefaults()
        d.setObject_forKey_('1', 'TUTORIAL')                  # 0x33fc8
        d.synchronize()
        RunLoop.main().cancelPerform(self)                    # tutorialTimer, 0x33ff4
        self.app.playSound_Gain_Pos_z_reprats_(327, 0.2, (0.0, 0.0), 0, False)

    # -[Stage_1_E continueAction:] 0x33941
    def continueAction_(self, *_):
        if not self.bStop:                                    # 0x3395a
            return False
        self.app.playSound_Gain_Pos_z_reprats_(10, 0.2, (0.0, 0.0), 0, False)
        self.blindModeOff()
        if self.gameState != 1:                               # 0x339b2
            return False                                      # nothing to resume
        if self.isTutorial:                                   # 0x33a02
            self.MotionSamplingTimer = RunLoop.main().scheduledTimer(
                1.0, self, 'MainControl', None, True)
        else:
            # 0x33a3a schedules the stage's own inline tutorial check.  Stage_Tutorial
            # carries the tutorial in this port, so there is nothing to restart.
            self.checkTutorialTimer = None
        self.gameState = 0                                    # 0x33a7c
        self.walkXFlag = False                                # 0x33a8c
        self.brearhFlag = False                               # 0x33a9a
        self.MonsterReStart()                                 # 0x33aa0
        # ...and the ambience StopPlayAction: silenced comes back, 0x33b22.
        pb = self.app.playback
        if pb is not None:
            if self.gameMode == 3:
                pb.startBGPlayer_type_soundGain_Loop_(
                    'effect_forest_rainng', 'wav', 0.5, True)
            elif self.gameMode == 2:
                pb.startBGPlayer_type_soundGain_Loop_(
                    'bgm_forest_amb', 'wav', 0.2, True)
            elif self.gameMode == 1:
                pb.startBGPlayer_type_soundGain_Loop_(
                    'bgm_cave_amb', 'wav', 0.2, True)
            if self.gamePlayer.playerYplot < 396:             # 0x33b9c
                if self.gameMode == 2:
                    pb.startAMBPlayer_type_soundGain_Loop_(
                        'bgm_forest', 'wav', 0.02, True)
                elif self.gameMode == 1:
                    pb.startAMBPlayer_type_soundGain_Loop_(
                        'bgm_cave', 'wav', 0.02, True)
        self.selectMenu = 0
        return True

    # -[Stage_1_E gameReplayAction:] 0x330ed
    def gameReplayAction_(self, *_):
        """Restart.  It costs a coin, the way starting a game from the menu does."""
        if not self.bStop:                                    # 0x33106
            return False
        if self.app.Coin <= 0:                                # 0x33128
            self.app.playSound_Gain_Pos_z_reprats_(358, 0.2, (0.0, 0.0), 0, False)
            self._reset_run_flags()                           # L_337b6 runs either way
            return False
        self.app.Coin -= 1                                    # 0x33146
        d = UserDefaults.standardUserDefaults()
        d.setObject_forKey_('%d' % self.app.Coin, 'COIN')     # 0x331bc
        d.synchronize()
        self._coin_timer_start()                              # 0x33218
        self.app.playSound_Gain_Pos_z_reprats_(10, 0.2, (0.0, 0.0), 0, False)
        self.blindModeOff()
        self.gameState = 0                                    # 0x3326c
        if self.MotionSamplingTimer is not None and self.MotionSamplingTimer.isValid():
            self.MotionSamplingTimer.invalidate()
        self.MotionSamplingTimer = None
        self.MonsterDealloc()
        self.MonsterBuffer = []                               # 0x332f4
        self.gamePlayer = PlayerControl()                     # 0x3333e
        self.gamePlayer.HP = 3                                # 0x33368
        self.startWeapon()                                    # 0x3337a
        p = self.gamePlayer
        p.killMonsterCount = 0                                # 0x33392
        for i in range(1, 12):                                # 0x333a8..0x33492
            setattr(p, 'killMonster%dcount' % i, 0)
        p.killMonster5000count = 0                            # 0x3349a
        p.HeadShotCount = 0                                   # 0x334b0
        p.playerXplot = 20                                    # 0x334c6
        p.playerYplot = 680                                   # 0x334de
        self.monsterHPGain = 1.0                              # 0x334fc
        self.LVUP = 1                                         # 0x3350c
        self.DieFlag = False                                  # 0x3351a
        self.score = 0
        self.MapInitInBundle()                                # 0x335b8
        self._reset_run_flags()
        # The panel is gone and the run is new, so the one pause it allows comes back.
        self.bStop = False
        self.selectMenu = 0
        self.running = True
        return True

    def _reset_run_flags(self):
        """0x337b6..0x33902 - the tail both branches of ``gameReplayAction:`` run.

        The nine ``tutorialN`` flags and the nine ``NFlag`` flags it clears belong to
        the stage's inline tutorial, which is Stage_Tutorial here; what is left is the
        run state the restart shares.
        """
        self.walkXFlag = False                                # 0x338ca
        self.brearhFlag = False                               # 0x338d8
        self.noAtt = False                                    # 0x338e6
        self.isShake = False                                  # 0x338f4
        self.shotFlag = False                                 # 0x33902

    def _coin_timer_start(self):
        """0x33218 posts ``coinTiemrControlStart``, which ``MainController`` observes
        (0xbe01) while it sits under the stage in the navigation stack.  The port's
        screen loop keeps one screen at a time, so there is no menu listening; what
        the observer would have written is written here instead, and the menu picks
        the clock up from the defaults when it comes back.
        """
        from .app_delegate import COIN_MAX
        if self.app.Coin >= COIN_MAX:                         # 0xbff6
            return
        d = UserDefaults.standardUserDefaults()
        if d.stringForKey_('COIN_TIMER_START') == '1':        # 0xbe3a: already
            return                                             # counting down
        d.setObject_forKey_('1', 'COIN_TIMER_START')
        d.setObject_forKey_(time.strftime('%Y-%m-%d %H:%M:%S'), 'COIN_TIMER')
        d.synchronize()

    # -[Stage_1_E GameEndAction:] 0x32fe1
    def GameEndAction_(self, *_):
        """The main-menu button: drop everything and pop back to the menu."""
        self.app.playSound_Gain_Pos_z_reprats_(10, 0.2, (0.0, 0.0), 0, False)
        if self.MotionSamplingTimer is not None and self.MotionSamplingTimer.isValid():
            self.MotionSamplingTimer.invalidate()
        self.MotionSamplingTimer = None
        self.MonsterDealloc()
        self.MonsterBuffer = []                               # 0x33082
        self.running = False                                  # popViewControllerAnimated:
        if self.app.playback is not None:
            self.app.playback.AMBSoundStop()                  # 0x330ce
        return True

    # -------------------------------------------------------- the readouts
    # -[Stage_1_E ReadNumberOfZombies] 0x3bdd0
    def ReadNumberOfZombies(self, *_):
        n = self.gamePlayer.killMonsterCount
        self.killZombiesLabel = '%d' % n
        self.app.TTSNumber_type_(n, 1)
        return n

    # -[Stage_1_E ReadNumberOfHeadshot] 0x3be7c
    def ReadNumberOfHeadshot(self, *_):
        n = self.gamePlayer.HeadShotCount
        self.HeadShotLabel = '%d' % n
        self.app.TTSNumber_type_(n, 1)
        return n

    # -[Stage_1_E ReadObtainedGold] 0x3c3f4
    def ReadObtainedGold(self, *_):
        n = self.ObtainedGold()
        self.GoldLabel = '%d' % n
        self.app.TTSNumber_type_(n, 1)
        return n

    def ObtainedGold(self):
        """0x3c616: ``add.w r3, sl, sl, lsl #1`` / ``lsls r6, r6, #1`` /
        ``add.w r4, r6, r3, lsl #2`` - the gold a run pays is
        ``12 * killMonsterCount + 2 * HeadShotCount``.

        Everything above that in ``ReadObtainedGold`` - the headshot multiplier string
        and all twelve per-kind tallies - is computed into ``r0`` and then clobbered
        by the next selector load.  See ``docs/DIVERGENCES.md``.
        """
        p = self.gamePlayer
        return 12 * p.killMonsterCount + 2 * p.HeadShotCount

    # -[Stage_1_E ReadTopScore] 0x3c214
    def ReadTopScore(self, *_):
        d = UserDefaults.standardUserDefaults()
        raw = d.stringForKey_('TOPSCORE')
        self.TopScoreLabel = raw if raw else '0'
        n = d.intForKey_('TOPSCORE')
        self.app.TTSNumber_type_(n, 1)
        return n

    # -[Stage_1_E ReadRank] 0x3c300
    def ReadRank(self, *_):
        d = UserDefaults.standardUserDefaults()
        raw = d.stringForKey_('NOWRANK')
        self.RankLabel = raw if raw else '-'
        n = d.intForKey_('NOWRANK')
        self.app.TTSNumber_type_(n, 1)
        return n

    # -[Stage_1_E updateTopscoreRank] 0x3261c
    def updateTopscoreRank(self):
        """Both label fields, from the defaults, with the original's fallbacks."""
        d = UserDefaults.standardUserDefaults()
        top = d.stringForKey_('TOPSCORE')
        rank = d.stringForKey_('NOWRANK')
        self.TopScoreLabel = top if top else '0'              # 0x326c2
        self.RankLabel = rank if rank else '-'                # 0x3274a

    def _fill_result_labels(self):
        """The fill both ``StopPlayAction:`` (0x34302) and ``SuccessOrFailMission``
        (0x34826) do before the panel goes up."""
        p = self.gamePlayer
        self.killZombiesLabel = '%d' % p.killMonsterCount
        self.HeadShotLabel = '%d' % p.HeadShotCount
        self.ScoreLabel = '%d' % self.ReadScore()
        self.GoldLabel = '%d' % self.ObtainedGold()
