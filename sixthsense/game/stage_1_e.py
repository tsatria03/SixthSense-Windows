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

**Progress.**  At Y == 29 an alarm sounds; at Y == 23 the level's boss comes down the
middle lane and the alarm stops.  The player walks one more cell and waits at 22 until
``checkBoosDie`` says the boss is dead.  Then every zombie left is killed, the ambience
changes, and ``ChangeLevel:`` (0x322e0) puts the player back at 680 with
``monsterHPGain`` 1.5 times higher, now in the other environment, cave or forest.
The action layer of the map (``a_CH1_E.txt``) sets the spawn tier along the way: values
1..7 set ``monster_num``, 8 sends the girl or the woman zombie, 9 stops the music and
starts a quiet stretch, and 10 starts the music.  A melee hit is only ever plain damage.
"""
from __future__ import annotations

import logging
import math
import random
import time

from .. import paths
from ..platform import volume
from ..platform.defaults import UserDefaults
from ..platform.runloop import RunLoop
from .app_delegate import AppDelegate
from .blind_screen import whole
from .make_maps import MakeMaps
from .monster_control import MonsterControl, lane_bearing
from .moving_accelerometer import MovingAccelerometer
from .player_control import PlayerControl
from .weapon_control import WeaponControl, WEAPON_FILES, WEAPON_SLOTS

log = logging.getLogger('stage')


#: PORT DIVERGENCE: the most presses of the shake key a grab can need; each grab
#: draws 1 to this many.  The original took ten shakes of the phone.
SHAKES_MAX = 5


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

#: The two bosses, and the ``monsterNumber`` each one's plist gives it, which is what
#: checkBoosDie looks for (0x360d4: 5001, 0x360e8: 5000).
BOSS_FOREST = 5008          # gameMode 2 and 3, 0x31d1c
BOSS_CAVE = 5003            # gameMode 1, 0x31e0a
BOSS_NUMBER = {2: 5001, 3: 5001, 1: 5000}
KIND_BOSS = 5000            # the port's key for the boss's row below

#: 0x322da: the ten scripted ids action cell 8 picks from.  10001..10005 are the girl
#: who heals you (monsterNumber 21), 10006..10010 the woman zombie (22), one per lane.
GIRL_IDS = tuple(range(10001, 10011))
MONSTER_GIRL = 21
MONSTER_WOMAN = 22

# -[Stage_1_E MonsterInit:] 0x36524 - the sound numbers each monster kind may use.
# One entry is one OpenAL voice, so a kind can have at most as many live monsters as it
# has spare numbers.  Extracted from the arrayWithObjects: blocks at 0x3658e..0x37190.
#
# Every zombie row is a full triple; the third entry of each array sits in a register
# the listings drop (0x36b62, 0x36bbe, 0x36bf0, 0x36c1e, 0x36f3a...).  Kind 11 hits the
# player with kind 12's 307..309: 298..300, zombies_11_hit_player, is never listed.
# Nothing ever spawns kinds 11 and 12, so their files are in game/sounds/unused.
MONSTER_SOUNDS = {
    #        coming (cave)      coming (forest)    damage           die              hit player
    1:  ([93, 94, 95], [96, 97, 98], [99, 100, 101], [102, 103, 104], [105, 106, 107]),
    2:  ([108, 109, 110], [111, 112, 113], [114, 115, 116], [117, 118, 119], [120, 121, 122]),
    3:  ([123, 124, 125], [126, 127, 128], [129, 130, 131], [132, 133, 134], [135, 136, 137]),
    4:  ([138, 139, 140], [141, 142, 143], [144, 145, 146], [147, 148, 149], [120, 121, 122]),
    5:  ([150, 151, 152], [153, 154, 155], [156, 157, 158], [159, 160, 161], [135, 136, 137]),
    6:  ([165, 166, 167], [168, 169, 170], [171, 172, 173], [174, 175, 176], [177, 178, 179]),
    7:  ([180, 181, 182], [183, 184, 185], [186, 187, 188], [189, 190, 191], [135, 136, 137]),
    8:  ([192, 313, 314], [193, 315, 316], [194, 317, 318], [195, 319, 320], [196, 321, 322]),
    9:  ([199, 200, 201], [202, 203, 204], [205, 206, 207], [208, 209, 210], [211, 212, 213]),
    10: ([214, 215, 216], [217, 218, 219], [205, 206, 207], [208, 209, 210], [220, 221, 222]),
    11: ([292, 293, 294], [295, 296, 297], [301, 302, 303], [310, 311, 312], [307, 308, 309]),
    12: ([304, 305, 306], [304, 305, 306], [301, 302, 303], [310, 311, 312], [307, 308, 309]),
    # 0x36790.., 0x370da..: one voice each.  Reaching you, the girl plays 270, her
    # thank you; the woman zombie's hit is 274.
    21: ([267], [268], [269], [269], [270]),          # the girl who heals you
    22: ([271], [272], [273], [273], [274]),          # the woman zombie
    KIND_BOSS: ([286], [290], [205], [289], [288]),   # 0x367ca / 0x36a30, 0x3715e..
}
# zombie_8 is the one that grabs you; it needs two more (0x36e96 / 0x36ec4).
SHAKE_SOUNDS = {8: ([197, 323, 324], [198, 325, 326])}

SOUND_HEADSHOT = 330        # headshot_4
#: 0x3a83a plays this on the hit that kills, headshot or not.  SoundList names it
#: weapon_head_shot; what it actually marks is the kill.
SOUND_KILL = 79
SOUND_PLAYER_DAMAGE = 83
SOUND_PLAYER_DIE = 84
SOUND_ZOMBIES_COMING = 328
SOUND_WARNING = 285
SOUND_NO_BULLETS = 78
SOUND_GAME_OVER = 354
SOUND_MISSION_SUCCESS = 227
SOUND_MISSION_FAIL = 228    # stopped by StopElseSpeak; Stage_1_E never plays it
SOUND_BGM_GAME_END = 89     # what -[Stage_1_E playerDie:] plays, 0x3bcaa
SOUND_NOW_LOADING = 46
#: How long a gunshot or a grenade takes to land, in seconds.  The original waits 0.5 s
#: for every gun and the grenade alike (0x2fd70, 0x2f32a: ``movt r1, #0x3fe0``); no
#: weapon's plist changes it, and ``ShotSpeed`` is never read.  The port used to land
#: the hit at once.  Kept at 0.5, the original's feel, by tsatria03 and
#: tunmi13productions on 2026-09-22; 0.0 would have shots land instantly again, and
#: nothing else would need to change.
SHOT_TRAVEL = 0.5

#: 0x31964: how long ``brearhFlag`` stays up after a breath.
BREATH_HOLD = 3.0
SOUND_SWORD_START = 329     # weapon_japen_knife_start, 0x35ec0
#: What ChangeLevel: loops at 0.02 as a note (0x32362): 88, bgm_cave_amb, going into
#: the forest, and 87, bgm_forest_amb, going into the cave - the other level's.
SOUND_FOREST_AMB = 87
SOUND_CAVE_AMB = 88
#: 0x31d92: ChangeLevel: follows the boss's death this long after.
LEVEL_CHANGE_SECONDS = 2.0
#: 0x34720: StopPlayAction: sends spaekMenu, "paused" (229), this long after the click.
PAUSED_VOICE_DELAY = 0.5
#: 0x35e80/0x35e90: gunChangeAction: plays the weapon's change sound at this, hard-coded.
WEAPON_CHANGE_GAIN = 0.2

#: How far from you a shot, an empty click or a missed swing is placed, in cm, along the
#: lane it is aimed down.
#: 40 is the reference distance, so this pans it without making it quieter.
SHOT_DISTANCE = 40.0
#: Where MovingShot: plays a gunshot, by lane, always at z 40 (0x28): each lane's branch
#: stores its own point before the one shared call at 0x2fbd2 - lane 1 at 0x2f948, 2 at
#: 0x2f4a0, 3 at 0x2f7f8, 4 at 0x2f680, 5 at 0x2fbbe (0x41c8 is 25.0, 0x4170 15.0).  So
#: the original pans a shot partly toward its lane; only the grenade is dead centre.
#: PORT DIVERGENCE: the port does not use these points.  Every shot goes off 40 cm down
#: its lane at z 0 (``_lane_pos``), in line with the zombies in that lane, which the dev
#: preferred by ear; the original's points left shots off from the zombies.
GUN_SHOT_POS = {1: (-25.0, 0.0), 2: (-15.0, 25.0), 3: (0.0, 25.0), 4: (15.0, 25.0),
                5: (25.0, 0.0)}
GUN_SHOT_Z = 40
#: Where the empty click (78) is heard, by lane, at z 40.  Each lane's ammo check branches
#: to a block that sets the point: lane 1 (0x2f8a4 -> 0x2f9fa), 3 (0x2f756 -> 0x2f952) and
#: 5 (0x2fb1a -> 0x2fcc8) use their own gunshot points, but lanes 2 and 4 (0x2f3f8 and
#: 0x2f5d8) both branch to 0x2f808, which stores lane 2's (-15, 25) - so in the original an
#: empty gun aimed at 1:30 clicks from 10:30.  PORT DIVERGENCE: not used; the click goes
#: off down the lane you aimed at, where the shot does (``_lane_pos``).
EMPTY_CLICK_POS = {1: (-25.0, 0.0), 2: (-15.0, 25.0), 3: (0.0, 25.0), 4: (-15.0, 25.0),
                   5: (25.0, 0.0)}

#: 0x2d45e (0x7d6a2 in Stage_Tutorial) - how long the original waits, after Now
#: Loading plays, before calling MapInitInBundle - so the recording has time to
#: finish before the level's own ambience and music start over it (or, for
#: Stage_Tutorial, before its first prompt does).
LOADING_SECONDS = 2.8


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
        self.shakesNeeded = SHAKES_MAX
        self.shakeFlag = 0
        self.shakeMonsterNumber = 0
        self.shakeMonsterTimer = None
        self.heldMonster = None        # not in the original, see _held_monster
        self.gameState = 0
        self.bStop = False          # set by the three panel openers, cleared by continue and restart
        self.levelChanging = False  # PORT ADDITION: ChangeLevel: is due, see _pause
        self.pausedPlayers = []     # PORT ADDITION: see _pause_players
        self.selectMenu = 0
        self.speech = None          # the screen reader, for the panel with voice over off
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
        self.monstersFrozen = False     # --debug, sixthsense/game/debug.py
        self.debugSpawn = 0
        self.debugHits = False          # --debug's F7: zombies hit you, for no heart
        self.debugSectionReady = 0.0    # --debug's F2 cools down until then
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
        # Now Loading always plays first, blocking - nothing else here touches
        # audio, including cutting the menu music, until MapInitInBundle actually
        # runs (below), well after Now Loading has had time to finish.
        self.app.playSound_Gain_Pos_z_reprats_(
            SOUND_NOW_LOADING, 0.2, (0.0, 0.0), 0, False)
        d = UserDefaults.standardUserDefaults()
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
        # Set here rather than left to MapInitInBundle's own assignment, so the frame
        # loop does not read this as an ended stage and bail to the menu while the
        # loading delay below is still running.
        self.running = True
        RunLoop.main().perform(self, 'MapInitInBundle', None, LOADING_SECONDS)

    # -[Stage_1_E MapInitInBundle] 0x2dbbc
    def MapInitInBundle(self):
        # The menu music stops here, not in viewDidLoad, so it keeps playing under
        # Now Loading instead of cutting out before the player ever hears it.
        self.app.BGMusicStop()
        self._load_maps()

        # The rain is the whole of gameMode 3's ambience, on the ambience player - not
        # the music player, which action cell 9 stops at the first corridor segment.
        # The other two play at 0.2: movw/movt r4, 0x3e4ccccd at 0x2ddfa/0x2de08.
        pb = self.app.playback
        if self.gameMode == 3:                                   # 0x2dd96
            pb.startAMBPlayer_type_soundGain_Loop_(
                'effect_forest_rainng', 'wav',
                volume.ambience(0.5), True)                     # 0x2ddc8: 0x3f000000
        elif self.gameMode == 2:                                 # 0x2dd6c
            pb.startAMBPlayer_type_soundGain_Loop_(
                'bgm_forest_amb', 'wav', volume.ambience(0.2), True)
        elif self.gameMode == 1:                                 # 0x2ddce
            pb.startAMBPlayer_type_soundGain_Loop_(
                'bgm_cave_amb', 'wav', volume.ambience(0.2), True)

        # PORT: the original never sends setListenerRotation: (it is not in
        # __objc_selrefs) and never turns you.  The port sets the listener once, facing
        # 0, because that orientation is what puts x to the right and the lanes where
        # they belong; nothing turns it after this.
        self.app.playback.setListenerRotation_(self.facing.radians)
        self.running = True
        if self.app.debug:
            self._say('Debug mode.')
        # 0x2e08e: the 1.0 s walk timer only exists once the tutorial has been cleared.
        if self.isTutorial:
            self.MotionSamplingTimer = RunLoop.main().scheduledTimer(
                1.0, self, 'MainControl', None, True)
        elif self.warn_if_not_walking:
            log.warning('TUTORIAL is 0, so -[Stage_1_E MapInitInBundle] does not start '
                        'MotionSamplingTimer and the player never walks. Play the '
                        'tutorial first (it is what sets the key).')

    def _load_maps(self):
        """The three layers of ``CH1_E`` from the bundle, and the grid built from them."""
        def read(name, ext=None):
            p = paths.path_for_resource(name, ext)
            with open(p, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        self.actionMapData = read('a_CH1_E', 'txt')
        self.groundMapData = read('g_CH1_E')
        self.soundMapData = read('s_CH1_E', 'txt')
        self.stage = MakeMaps().initWithMapGroundFileString_soundPosFileName_actionPosFileName_(
            self.groundMapData, self.soundMapData, self.actionMapData)

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

        self._breathe()                                           # 0x3186e..0x31974
        self._walk_and_act()                                      # 0x319e0..0x320da

    def _breathe(self):
        """0x3186e..0x31974.  Every second tick breathes, unless the last breath is
        still holding brearhFlag up.  breath: comes 3 s later (0x31964: movt r5,
        #0x4008), which covers the next second tick, so the player breathes once every
        4 s.  Which breath says how hurt you are: 80 at full health, 81 at two hearts,
        82 at one."""
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
                RunLoop.main().perform(self, 'breath_', None, BREATH_HOLD)

    def _walk_and_act(self):
        """The rest of ``MainControl``: the step, the action cell, the spawn, the
        attacks and death (0x319e0..0x320da)."""
        px = self.gamePlayer.playerXplot
        py = self.gamePlayer.playerYplot
        groundAhead = self.stage.movePlayGroundState_PlotY_(px, py - 1)   # 0x31a32
        actionHere = self.stage.movePlayActionState_PlotY_(px, py)        # 0x31a68

        if groundAhead >= 1:                                              # 0x31a70
            if py >= 23:                                                  # 0x31a80
                self.gamePlayer.playerYplot = py - 1
                y2 = self.gamePlayer.playerYplot
                if y2 == 29:                                              # 0x31ab2
                    # The alarm: six steps of it, until the boss cuts it off.
                    self.app.playSound_Gain_Pos_z_reprats_(
                        SOUND_WARNING, 0.2, (0.0, 0.0), 0, False)
                elif y2 == 23:                                            # 0x31cfc
                    # The boss comes in at 12 o'clock, and the alarm stops.
                    if self.gameMode in (2, 3):                           # 0x31d12
                        self.MonsterInit_(BOSS_FOREST)
                    elif self.gameMode == 1:                              # 0x31e02
                        self.MonsterInit_(BOSS_CAVE)
                    self.app.stopSoundBufNumber_(SOUND_WARNING)           # 0x31e2e
            elif self.checkBoosDie():                                     # 0x31af0
                # Standing at the end: the level waits for the boss to die.
                self._level_transition()
                return                                                    # 0x31e00

        # ---- the action layer, 0x31e32..0x31f16 -------------------------
        # Cells 1..7 set the spawn tier.  9 stores itself too (0x31e70 falls into the
        # store at 0x31f06), and MakeMonster: does nothing for tier 9, so each section
        # of the corridor opens with a quiet stretch until its own tier cell.  8 and 10
        # branch past the store.
        if actionHere == 8:                                               # 0x31e72
            self._action_girl()
        elif actionHere == 9:                                             # 0x31e4c
            self.app.playback.backgroundSoundStop()
            self.monster_num = actionHere
        elif actionHere == 10:                                            # 0x31ec0
            # 0.02, well under the monsters: movw/movt r4, 0x3ca3d70a at 0x321d4/0x321dc
            pb = self.app.playback
            if self.gameMode >= 2:
                pb.startBGPlayer_type_soundGain_Loop_(
                    'bgm_forest', 'wav', volume.music(0.02), True)
            else:
                pb.startBGPlayer_type_soundGain_Loop_(
                    'bgm_cave', 'wav', volume.music(0.02), True)
        elif actionHere != 0:                                             # 0x31f06
            self.monster_num = actionHere

        # ---- spawn, attack, upkeep, 0x31f16..0x31f94 --------------------
        self.MakeMonster_(self.monster_num)
        self.MonsterAttPlayer()
        self.HPImageCount()
        RunLoop.main().perform(self, 'timerLeft', None, 0.0)

        # ---- death, 0x31fa8..0x320da ------------------------------------
        if not self.DieFlag and self.gamePlayer.HP <= 0:
            self.DieFlag = True
            # 0x320ae: the moment of death is `player_die` (84) at 1.0, z 40.  "Game over"
            # (354) comes later, from the panel missionFailTell: puts up (0x32814) - the
            # port used to play it here as well, so the player heard it twice.
            self.app.playSound_Gain_Pos_z_reprats_(
                SOUND_PLAYER_DIE, 1.0, (0.0, 0.0), 40, False)
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
        """Whether the level is allowed to end: not while this level's boss is alive.

            for (i = 0; i < MonsterBuffer.count; i++) {
                m = MonsterBuffer[i];
                if ((unsigned)(gameMode - 2) < 2) { if (m.monsterNumber == 5001) return NO; }
                else if (gameMode == 1)           { if (m.monsterNumber == 5000) return NO; }
            }
            return YES;

        5001 is the forest boss (type5008.plist) and 5000 the cave one (type5003.plist),
        the two ``MainControl`` sends in at row 23.  ``bBOSS`` is declared and never
        touched anywhere in the binary.
        """
        boss = BOSS_NUMBER.get(self.gameMode)
        for m in self.MonsterBuffer:
            if boss is not None and m.monsterNumber == boss:
                return False
        return True

    def _level_transition(self):
        """``MainControl`` 0x31afc..0x31e00 - the boss is dead and you are at the end.

        Every zombie still standing is killed where it is: HP 0, one more round fired,
        its hit sound and its death, and one more kill each (0x31bd4..0x31c5e) - none
        of them reach the next level.  Then the level goes up, the ambience changes to
        the next level's at 0.3 (0x31ce2 / 0x31d82: 0x3e99999a) and ``ChangeLevel:``
        follows 2 s later (0x31d92).
        """
        dead = []
        for m in list(self.MonsterBuffer):
            m.HP = 0
            self.gamePlayer.gunEggCountShot += 1
            m.MonsterHitSound_(None)
            if m.HP <= 0:
                if not self.app.debug:
                    self.gamePlayer.killMonsterCount += 1
                dead.append(m)
        for m in dead:
            self._remove(m)

        self.LVUP += 1                                          # 0x31c80
        pb = self.app.playback
        pb.backgroundSoundStop()
        if self.gameMode == 1:                                  # 0x31c8c
            self.gameMode = 2
            pb.startAMBPlayer_type_soundGain_Loop_(
                'bgm_forest_amb', 'wav', volume.ambience(0.3), True)
        else:
            self.gameMode = 1
            pb.startAMBPlayer_type_soundGain_Loop_(
                'bgm_cave_amb', 'wav', volume.ambience(0.3), True)
        self.levelChanging = True
        RunLoop.main().perform(self, 'ChangeLevel_', None, LEVEL_CHANGE_SECONDS)
        if self.MotionSamplingTimer is not None and self.MotionSamplingTimer.isValid():
            self.MotionSamplingTimer.invalidate()
        self.MotionSamplingTimer = None

    # -[Stage_1_E ChangeLevel:] 0x322e0
    def ChangeLevel_(self, *_):
        """Back to the start of the corridor, with tougher zombies.

        The new ambience is already on the ambience player.  What this adds is the
        other level's ambience as a looping note at 0.02 (0x32362), which is what the
        original does; the port used to play "zombies are coming" here instead.
        """
        self.levelChanging = False
        self.gamePlayer.playerYplot = 680               # 0x32302
        self.monsterHPGain = self.monsterHPGain * 1.5   # 0x32314
        note = SOUND_FOREST_AMB if self.gameMode == 1 else SOUND_CAVE_AMB
        # the ambience volume setting applies to it too, the same as the ambience player;
        # at its default it is the binary's 0.02 exactly
        self.app.playSound_Gain_Pos_z_reprats_(note, volume.ambience(0.02), (0.0, 0.0), 0, True)
        self.changeGameMode()
        self.MotionSamplingTimer = RunLoop.main().scheduledTimer(
            1.0, self, 'MainControl', None, True)

    # -[Stage_1_E MainControl] 0x31e72 - action cell 8
    def _action_girl(self):
        """The first two after the tutorial are fixed, the woman zombie then the girl
        (0x3218a: 10008, 0x31eac: 10003).  Otherwise it is one of the ten at random
        (0x320e6..0x322da), so each section of the corridor sends either the girl who
        heals you or the woman zombie."""
        if self.isTutorialEnd > 0:
            self.GirlMonsterNumber += 1
            if self.GirlMonsterNumber == 2:
                self.MonsterInit_(10003)
                return
            if self.GirlMonsterNumber == 1:
                self.MonsterInit_(10008)
                return
        self.MonsterInit_(GIRL_IDS[arc4random() % 10])

    # ============================================================== monsters
    # -[Stage_1_E MakeMonster:] 0x36100
    def MakeMonster_(self, tier):
        self.LVCount += 1
        if not (1 <= tier <= 7):                        # 0x3611a
            return
        cap = self.LVUP + 2                             # 0x3612e
        if self.LVCount < 3:                            # 0x36144
            return
        # Every attempt from here on starts the count again, whether it spawns or not
        # (0x3623a for tiers 1 and 2, before the count check for the rest: 0x3625a).
        self.LVCount = 0
        if len(self.MonsterBuffer) >= cap:              # 0x36168
            return
        mod, off = MAKE_MONSTER_TIER[tier]
        idx = (arc4random() % mod) + off
        if self.checkMonsterArray_(idx) == -1:          # 0x361ec
            return
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

        # The girl and the woman zombie are built with an HPGain of 1.0, not the
        # level's (0x38d8c / 0x39034: mov.w r2, #0x3f800000 into the argument), so
        # they walk and take hits as on level 1 whatever the level.  Every other
        # monster, the boss included, gets monsterHPGain (0x37730, 0x38f68...).
        gain = 1.0 if kind in (MONSTER_GIRL, MONSTER_WOMAN) else self.monsterHPGain
        m = MonsterControl()
        m.frozen = self.monstersFrozen
        if m.initWithMonsterPatern(type_id, self.app, coming, hit, php, dies,
                                   approach, push, gain) is None:
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
        bare (1..5), so kind = id // 10 + 1.  The scripted ids are their own kinds:
        10001..10005 are the girl and 10006..10010 the woman zombie (0x38aae), and the
        5000s are the bosses.
        """
        if type_id >= 10000:
            return MONSTER_GIRL if type_id - 10001 <= 4 else MONSTER_WOMAN
        if type_id >= 5000:
            return KIND_BOSS
        if type_id >= 100:
            return min(12, type_id // 10)
        return type_id // 10 + 1

    # -[Stage_1_E MonsterAttPlayer] 0x3b040
    def MonsterAttPlayer(self):
        """Every monster within 25 cm reaches you.

        The ones that are done are collected and taken out of ``MonsterBuffer`` after
        the loop (0x3b44e), so the index a grabber is found at is still its index.
        A heart is only lost once the tutorial is behind you (0x3b2e6: ``isTutorial``);
        in the tutorial the monster's beat is prompted again instead (0x3b3a2..0x3b41c).
        """
        done = []
        grab = None
        for m in self.MonsterBuffer:
            if m.monsterRange > 25.0:                  # 0x3b104: vmov.f32 d8, #25.0
                continue
            if m.shakeMonsterFlag:                     # 0x3b27e - it grabs you
                grab = m
                break
            done.append(m)
            if m.monsterNumber == MONSTER_GIRL:        # 0x3b28e - the girl heals
                if self.gamePlayer.HP <= 3 and not self.app.debug:
                    self.gamePlayer.HP += 1
                m.hitPlayer()                          # 270, her thank you
                self.HPImageCount()
                continue
            if self.isTutorial and self.app.debug and not self.debugHits:
                m.DieMonster()                         # --debug: it dies on you instead
                self.HPImageCount()
                continue
            if self.isTutorial and not self.app.debug:  # 0x3b2e6; --debug: no heart
                self.gamePlayer.HP -= 1
            m.hitPlayer()
            self.HPImageCount()
            if self.gamePlayer.HP >= 0:                # 0x3b382
                RunLoop.main().perform(self, 'playerDamage_', None, 0.1)
            if not self.isTutorial:                    # 0x3b3aa
                self._tutorial_monster_reached(m)
        # PORT DIVERGENCE: the original returns straight into the grab and drops this
        # list, so a zombie that hit you on the same tick stayed on top of you and hit
        # again once you were free.  It is taken out either way here.
        for m in done:
            self._remove(m)
        if grab is not None:
            self._grabbed_by(self.MonsterBuffer.index(grab), grab)

    def _tutorial_monster_reached(self, m):
        """0x3b3b2..0x3b41c: during the tutorial, a monster that reaches you restarts
        the beat for its lane.  Stage_Tutorial carries the tutorial here."""

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

        From here you have ``shakeMonsterApproachTime`` seconds to shake free.  Free in
        time and the monster dies; too slow and it hits you.

        **DIVERGENCE:** the original takes ten shakes and never resets ``shakeCount``
        (``checkShakeMode``, 0x323d8, and ``shakeCheck:``, 0x324f8, are never called),
        so after the first escape every later grab broke on one shake.  The port asks
        for 1 to 5 presses of the shake key, drawn fresh for each grab.
        """
        self.shakeCount = 0
        self.shakesNeeded = random.randint(1, SHAKES_MAX)
        self.shakeMonsterNumber = index
        self.heldMonster = m
        self.shakeFlag = 1
        self.isShake = True
        if self.isTutorial == 0:                       # 0x3b640
            self.noAtt = True
        m.shakeMonster()
        loop = RunLoop.main()
        self._invalidate_shake_timer()
        self.shakeMonsterTimer = loop.scheduledTimer(
            0.1, self, 'shakingFind', None, True)      # 0x3b656: 0.1 s, repeating
        loop.perform(self, 'NonShaking', None, m.shakeMonsterApproachTime)

    def _held_monster(self):
        """The monster holding you.  The original reads it back by index; the port
        keeps the monster itself as well, so nothing that changes the list in between
        can make it free or kill the wrong one."""
        m = self.heldMonster
        if m is not None and m in self.MonsterBuffer:
            return m
        if 0 <= self.shakeMonsterNumber < len(self.MonsterBuffer):
            return self.MonsterBuffer[self.shakeMonsterNumber]
        return None

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

        if w in (1, 7):
            # 0x2fa12..0x2fadc: a swing silences the blade's own sounds and resolves
            # 0.1 s later; MonsterDamageKnife plays whatever it lands as.
            for n in (weapon.ReloadSoundnumber, weapon.att1SoundNumber,
                      weapon.att2SoundNumber):
                self.app.stopSoundBufNumber_(n)
            RunLoop.main().perform(self, 'MonsterDamageKnife', None, 0.1)
            return

        if weapon.BulletCount <= 0:                            # 0x2f3f6 and the others
            # The empty click (78) at 0.5, and shotFlag cleared at once (strb r6,
            # [r4, r5] at 0x2fcf2), so you can click again straight away.  PORT
            # DIVERGENCE: it goes off down the lane, where the shot does, not at the
            # original's point (EMPTY_CLICK_POS).
            self.app.playSound_Gain_Pos_z_reprats_(
                SOUND_NO_BULLETS, 0.5, self._lane_pos(lane), 0, False)
            self.shotFlag = False
            return

        # 0x2f41a: ammunition is only spent once the tutorial has been cleared.
        # --debug: none is spent at all.
        if self.isTutorial and not self.app.debug:
            weapon.BulletCount -= 1

        # The shot is played at the weapon's *reload* gain, which is 1.0 for every gun:
        # MovingShot: reads ReloadSoundGain at 0x2f248, 0x2f484, 0x2f664, 0x2f7e2, 0x2f930
        # and 0x2fba6, and never reads ShotSoundgain at all.  The port used ShotSoundgain,
        # the plists' malformed "0.2f", which left every gunshot 14 dB down.
        # PORT DIVERGENCE: the shot goes off down the lane it is aimed at, in line with
        # the zombies there, not at the original's point for the lane (GUN_SHOT_POS).
        self.app.playSound_Gain_Pos_z_reprats_(
            weapon.ShotSoundNumber, weapon.ReloadSoundGain,
            self._lane_pos(lane), 0, False)
        # 0x2fc0e..0x2fc48: whether it is a headshot is decided now, by the breathing
        # gap at the moment of the shot, and carried to the hit on isHeadShot.
        target = self.monsterHitHeadFind()
        if target is not None and target.headShotFlag:
            target.isHeadShot = True
        RunLoop.main().perform(self, 'MonsterDamage', None, SHOT_TRAVEL)   # 0x2fd70
        RunLoop.main().perform(self, 'stopShot_', None, weapon.ShotTime)

    @staticmethod
    def _lane_pos(lane):
        """A point ``SHOT_DISTANCE`` out along the lane's bearing, at the listener's
        height (z 0), for a shot, an empty click or a missed swing.  A zombie far down the same lane lies in
        almost exactly that direction, so the two pan alike, and at the reference
        distance the sound is exactly as loud as it was from the centre."""
        rad = math.radians(lane_bearing(lane))
        return (SHOT_DISTANCE * math.cos(rad), SHOT_DISTANCE * math.sin(rad))

    def _throw_grenade(self, weapon):
        """0x2f1bc - the grenade comes out of GRENADECOUNT, not a magazine."""
        d = UserDefaults.standardUserDefaults()
        n = d.intForKey_('GRENADECOUNT')
        if n <= 0 and not self.app.debug:           # --debug: grenades never run out
            # 0x2f4e8..0x2f50c: the empty click in the centre, z 40, and shotFlag
            # cleared at once.
            self.app.playSound_Gain_Pos_z_reprats_(
                SOUND_NO_BULLETS, 0.5, (0.0, 0.0), GUN_SHOT_Z, False)
            self.shotFlag = False
            return
        self.app.playSound_Gain_Pos_z_reprats_(
            weapon.ShotSoundNumber, weapon.ReloadSoundGain, (0.0, 0.0), 40, False)
        if self.isTutorial and not self.app.debug:  # 0x2f288
            d.setObject_forKey_(str(n - 1), 'GRENADECOUNT')
            d.synchronize()
        RunLoop.main().perform(self, 'MonsterDamage', None, SHOT_TRAVEL)   # 0x2f32a
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
            # 0x3ae48 skips a candidate only when it is further (bhi), so on a tie
            # the later one in MonsterBuffer wins.
            if best is None or m.monsterRange <= best.monsterRange:
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
            if m.isHeadShot:                                    # 0x3a174
                m.isHeadShot = False
                m.HP -= weapon.Damage * 2                       # 0x3a1dc
                if not self.app.debug:
                    self.gamePlayer.HeadShotCount += 1
                # 0x3a24a: 0.1 at the monster's Pos, z 40.  headshot_4 is stereo, and
                # OpenAL never places a stereo sound, so the announcement is heard
                # in the centre at 0.1, however far off the zombie is.
                self.app.playSound_Gain_Pos_z_reprats_(
                    SOUND_HEADSHOT, 0.1, m.Pos, 40, False)
            else:
                m.HP -= weapon.Damage                           # 0x3a796
            self.gamePlayer.gunEggCountShot += 1                # 0x3a7cc
            m.MonsterHitSound_(None)                            # 0x3a7e4
            if m.HP <= 0:
                # 0x3a83a: a killing hit plays 79 at 1.0, where the monster was.
                # SoundList calls it weapon_head_shot, but this is the kill, headshot or
                # not - the headshot's own sound (330) went out above.
                self.app.playSound_Gain_Pos_z_reprats_(
                    SOUND_KILL, 1.0, m.Pos, 40, False)
                self._monster_killed(m)
        else:
            # the grenade hits every live monster (0x3a4f0..0x3a562), and for each one:
            # HP - Damage, gunEggCountShot + 1 (0x3a538), MonsterKillCount: (0x3a546) -
            # the per-kind tally the score is made of, sent before the HP check, so a
            # zombie that lives through the blast still adds to the score - and then
            # MonsterHitSound:.  Only a death adds to the kills (0x3a636..0x3a642).
            for m in list(self.MonsterBuffer):
                m.HP -= weapon.Damage
                self.gamePlayer.gunEggCountShot += 1
                if not self.app.debug:
                    self.MonsterKillCount_(m)
                m.MonsterHitSound_(None)
                if m.HP <= 0:
                    self._monster_killed(m, tally=False)

    def _monster_killed(self, m, tally=True):
        """What every weapon does with a monster it has just killed (0x3a84c, 0x3a56a,
        0x39b12).  Killing the girl who heals you is not a kill: it costs you a heart,
        once the tutorial is behind you, and is not counted (0x3a850..0x3a97a).
        ``tally`` is False for the grenade, which has tallied every monster it hit."""
        if m.monsterNumber == MONSTER_GIRL:
            RunLoop.main().perform(self, 'playerDamage_', None, 0.1)
            if self.isTutorial and not self.app.debug:
                self.gamePlayer.HP -= 1
            self.HPImageCount()
        else:
            if not self.app.debug:
                self.gamePlayer.killMonsterCount += 1       # 0x3aad4
                if tally:
                    self.MonsterKillCount_(m)
            self._kill_seen(m)
        self._remove(m)

    def _kill_seen(self, m):
        """PORT ADDITION: a zombie was killed, counted or not.  ``--debug`` counts no
        kill, but ``Stage_Tutorial`` still has to hear of one, since a kill is what
        finishes each of its first five lessons."""

    # -[Stage_1_E MonsterDamageKnife] 0x392fc
    def MonsterDamageKnife(self, *_):
        """The knife and the sword, 0.1 s after the swing.

        The same lanes and range as a gun (0x3952e..0x3982a), but a hit is plain
        ``Damage``: the headshot doubling is the gun's alone.  A blow that leaves the
        monster standing plays ``att2``, one that kills it ``att1`` (0x39a46), where the
        monster is; only a swing that meets nothing plays the swish, ``ShotSound`` at
        ``ShotSoundgain`` (0x39c3c).  The swing's own recovery, ``stopShot:``, follows
        after ``ShotTime`` (0x39df0).
        """
        weapon = self.weaponSource[self.gamePlayer.useWepon]
        if self.isShake:                                        # 0x3931a
            self.shotFlag = False
            return
        m = self.monsterHitHeadFind()
        if m is None:
            # PORT DIVERGENCE: the swish goes down the lane, like a gunshot.
            self.app.playSound_Gain_Pos_z_reprats_(
                weapon.ShotSoundNumber, weapon.ShotSoundgain,
                self._lane_pos(self.shotMonster), 0, False)
        else:
            m.HP -= weapon.Damage                               # 0x39a18
            sound = weapon.att2SoundNumber if m.HP > 0 else weapon.att1SoundNumber
            self.app.playSound_Gain_Pos_z_reprats_(
                sound, weapon.att1SoundGain, m.Pos, 40, False)
            self.gamePlayer.gunEggCountShot += 1
            m.MonsterHitSound_(None)
            if m.HP <= 0:
                self._monster_killed(m)
        RunLoop.main().perform(self, 'stopShot_', None, weapon.ShotTime)

    # -[Stage_1_E MonsterKillCount:] 0x39e00
    #   A chain of `cmp monsterNumber, N` that bumps the matching per-kind tally.
    #   It does NOT touch killMonsterCount and keeps no score: every call site does
    #   `setKillMonsterCount:+1` first (0x39cee, 0x3a3ae, 0x3aad4), and the score is
    #   derived in ReadScore.  The port works it out after each kill (score_now), so
    #   the window can show it; the original only did so on the panel.
    def MonsterKillCount_(self, m):
        p = self.gamePlayer
        n = m.monsterNumber
        if 1 <= n <= 10:
            setattr(p, 'killMonster%dcount' % n, getattr(p, 'killMonster%dcount' % n) + 1)
        elif n == MONSTER_WOMAN:                                # 0x3a04c
            p.killMonster11count += 1
        elif n in (5000, 5001):                                 # 0x3a084, 0x3a094
            p.killMonster5000count += 1
        # Nothing else is tallied: kind 11 and 12 zombies count as kills but add
        # nothing to the score.
        self.score_now()

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
    #   so 5 headshots is x1.05, 42 is x1.42, 150 is x2.50.  Then it shows the score on
    #   ScoreLabel and reads it aloud, [app TTSNumber:score type:1] (0x3c1f2: mov r2, r4;
    #   the send at 0x3c1fa), digit by digit.  Its only caller is the panel: the score row
    #   queues it 2 s behind its label (selectTapPointSoundStart), and StopElseSpeak
    #   cancels it.
    def ReadScore(self, *_):
        score = self.score_now()
        self.ScoreLabel = '%d' % score
        self.app.TTSNumber_type_(score, 1)
        return score

    def score_now(self):
        """The score, worked out as ReadScore does, without saying it."""
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
        # 0x32c5c: the level's music, 92 (bgm_cave) in the cave and 91 (bgm_forest)
        # anywhere else - ite ne / movne 0x5b / moveq 0x5c, not a test for the cave.
        self.app.stopSoundBufNumber_(92 if self.gameMode == 1 else 91)
        gold = self.ObtainedGold()
        self.app.haveGold += gold                             # 0x32e70
        d = UserDefaults.standardUserDefaults()
        d.setObject_forKey_('%d' % self.app.haveGold, 'GOLD')  # 0x32ee8
        if self.app.stage <= 11:                              # 0x32efe
            d.setObject_forKey_('11', 'STAGE')                # 0x32f44
            self.app.stage = 11                               # 0x32f58
        d.synchronize()                                       # 0x32f7a
        self.gameState = 2                                    # 0x32f9c
        self._panel_voice(SOUND_MISSION_SUCCESS, 0.5)         # 0x32fac
        self.updateTopscoreRank()                             # 0x32fbe
        self.SuccessOrFailMission()                           # 0x32fca

    # -[Stage_1_E missionFailTell:] 0x32760
    def missionFailTell_(self, *_):
        """The game-over panel.  It plays 354 ``game over``, not 228 ``mission fail``
        - 228 is only ever silenced, never played, by this class."""
        self.missionCompletSounding = False                   # 0x32788
        self.bStop = True                                     # 0x3278e
        self.app.stopSoundBufNumber_(92 if self.gameMode == 1 else 91)   # 0x327b0
        self.gameState = 3                                    # 0x32802
        self._panel_voice(SOUND_GAME_OVER, 0.5)               # 0x32814
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
        """Cycle to the next owned-and-equipped weapon.  --debug: every weapon, bought
        and equipped or not."""
        use = self.app.useWeapon
        w = self.gamePlayer.useWepon
        # 0x35c72..0x35c88: the weapon being put away has its change sound stopped first
        old = self.weaponSource[w] if w < len(self.weaponSource) else None
        if old:
            self.app.stopSoundBufNumber_(old.weaponChangeSoundNumber)
        for _ in range(WEAPON_SLOTS):
            w = (w + step) % WEAPON_SLOTS
            if self.app.debug or (w < len(use) and use[w] == '1'):
                break
        self.gamePlayer.useWepon = w
        weapon = self.weaponSource[w]
        if weapon:
            # No reload here: gunChangeAction: never calls ReloadGun or setBulletCount,
            # so each weapon keeps the rounds it had (a full magazine from weaponInit).
            # 0x35e80..0x35e9e: the change sound at a fixed 0.2 (movt r3 #0x3e4c), z 40,
            # whatever the plist's weaponChangeSoundGain says (1.0 in every weapon).
            self.app.playSound_Gain_Pos_z_reprats_(
                weapon.weaponChangeSoundNumber, WEAPON_CHANGE_GAIN,
                (0.0, 0.0), 40, False)
            # 0x35eac: the sword is drawn with its own sound, at 1.0; any other weapon
            # silences it (0x35edc).
            if w == 7:
                self.app.playSound_Gain_Pos_z_reprats_(
                    SOUND_SWORD_START, 1.0, (0.0, 0.0), 40, False)
            else:
                self.app.stopSoundBufNumber_(SOUND_SWORD_START)

    def doubleTapChangeWeapon_(self, *_):
        self.gunChangeAction_(1)

    def threeTapChangeWeapon_(self, *_):
        self.gunChangeAction_(-1)

    # The 6 o'clock swipe, as the reload key.
    def ReloadGesture(self):
        """The reload key does what the 6 o'clock swipe does: it goes through the same
        guards as any other attack in ``MovingShot:`` (0x2f07e..0x2f0ca) before it
        reaches ``GunReloadAction:``.  So there is no reload while a reload or a shot is
        still going, while a zombie holds you, while attacks are barred, or once the
        game-over music has started.  A melee weapon has nothing to reload, and in the
        original the grenade swiped to 6 o'clock is thrown, so for both the key does
        nothing."""
        if self.missionCompletSounding or self.shotFlag:
            return False
        if self.isShake or self.noAtt:
            return False
        if self.gamePlayer.useWepon in (0, 1, 7):
            return False
        self.shotFlag = True                                   # 0x2f096
        self.GunReloadAction_()
        return True

    # -[Stage_1_E GunReloadAction:] 0x3516c
    def GunReloadAction_(self, *_):
        """Start a reload.  ``shotFlag`` stays up from the swipe until ``reloadGun:``
        drops it, so nothing can be fired while the magazine is out."""
        self.shotMonster = 0                                    # 0x351a2
        self.reloadWeaponNumber = self.gamePlayer.useWepon      # 0x351be
        if self.gamePlayer.useWepon == 0:                       # 0x351c8: not the grenade
            return
        weapon = self.weaponSource[self.gamePlayer.useWepon]
        if weapon is None:
            return
        self.app.playSound_Gain_Pos_z_reprats_(
            weapon.ReloadSoundnumber, weapon.ReloadSoundGain, (0.0, 0.0), 40, False)
        RunLoop.main().perform(self, 'reloadGun_', None, weapon.ReloadTime)

    # -[Stage_1_E reloadGun:] 0x35ef0
    def reloadGun_(self, *_):
        """The magazine goes back in: attacks are allowed again (0x35f24), and the weapon
        the reload was started with is refilled, even if you have switched since."""
        self.shotFlag = False
        weapon = self.weaponSource[self.reloadWeaponNumber]
        if weapon:
            self.app.stopSoundBufNumber_(weapon.ReloadSoundnumber)
            weapon.BulletCount = weapon.ReloadGun()

    # -[Stage_1_E accelerometer:didAccelerate:] 0x3c84c - the shake-free struggle.
    def shake_step(self):
        """-[Stage_1_E accelerometer:didAccelerate:] 0x3c84c

            if (isShake != 1)            return;
            if (shakeFlag == 0)          return;      // already free
            if (acceleration.x < 1.0)    return;
            if (++shakeCount >= 10)      shakeFlag = 0;

        Clearing ``shakeFlag`` is all it does; ``shakingFind``, polling every 0.1 s,
        is what notices and performs the escape.  The port counts to ``shakesNeeded``,
        1 to 5, in place of ten (see ``_grabbed_by``).
        """
        if not self.isShake:
            return
        if self.shakeFlag == 0:
            return
        self.shakeCount += 1
        if self.shakeCount >= self.shakesNeeded:    # 0x3c8b0 counts to 10
            self.shakeFlag = 0

    # -[Stage_1_E shakingFind] 0x3b95c - the 0.1 s poll; the escape.
    def shakingFind(self, timer=None):
        if self.shakeFlag != 0:                     # 0x3b976, still held
            return
        self.shakeFlag = 1
        loop = RunLoop.main()
        loop.cancelPerform(self, 'NonShaking')      # 0x3b9ae
        self._invalidate_shake_timer()
        m = self._held_monster()
        self.heldMonster = None
        if m is None:
            self.isShake = False
            return
        m.stopShakeMonsterSound_(None)
        # PORT DIVERGENCE: the original plays the push at the monster's Pos.  It is on
        # top of you by then and the push is your doing, so it is played where you are.
        self.app.playSound_Gain_Pos_z_reprats_(
            m.shakeMonsterPushSound, m.shakeMoneterPushGain, (0.0, 0.0), 40, False)
        # shaking free kills it (0x3baa0..0x3bad8)
        if not self.app.debug:
            self.gamePlayer.killMonsterCount += 1
            self.MonsterKillCount_(m)
        self._kill_seen(m)
        self._remove(m)
        self.isShake = False                        # 0x3bb6c

    # -[Stage_1_E NonShaking] 0x3b6f8 - the time ran out; the grab lands.
    def NonShaking(self, *_):
        if self.shakeFlag == 0:                     # 0x3b714, already escaped
            self.isShake = False
            return
        self._invalidate_shake_timer()
        m = self._held_monster()
        self.heldMonster = None
        if m is None:
            self.isShake = False
            return
        if self.isTutorial and self.app.debug and not self.debugHits:
            m.DieMonster()                          # --debug: it dies on you instead
            self._remove(m)
            self.isShake = False
            return
        if self.isTutorial and not self.app.debug:  # 0x3b79e; --debug: no heart
            self.gamePlayer.HP -= 1
        m.hitPlayer()
        if self.gamePlayer.HP >= 0:                 # 0x3b8bc
            RunLoop.main().perform(self, 'playerDamage_', None, 0.1)
        self._remove(m)
        self.isShake = False                        # 0x3b91a
        if not self.isTutorial:                     # 0x3b920: tutorialEightRestart
            self._tutorial_grab_landed()

    def _tutorial_grab_landed(self):
        """0x3b92a: in the tutorial, a grab you did not shake off prompts beat Eight
        again.  Stage_Tutorial carries the tutorial here."""

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
        # ...and the other level's ambience ChangeLevel: loops as a note.
        self.app.stopSoundBufNumber_(SOUND_FOREST_AMB)
        self.app.stopSoundBufNumber_(SOUND_CAVE_AMB)
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
    #: DIVERGENCE: row 9, the rank, is left out.  It read the place the publisher's
    #: ranking server gave you, and that server is gone.
    PAUSE_ROWS = (1, 2, 3, 4, 5, 10, 6, 7, 8)

    #: Rows whose label does not depend on the state (0x30930..0x311c2).
    PAUSE_ROW_SOUND = {2: 230, 3: 231, 4: 232, 5: 233, 9: 357, 10: 356,
                       7: 224, 8: 355}

    #: ...and the reader each one schedules behind its label.
    PAUSE_ROW_READER = {2: 'ReadNumberOfZombies', 3: 'ReadNumberOfHeadshot',
                        4: 'ReadScore', 5: 'ReadObtainedGold',
                        9: 'ReadRank', 10: 'ReadTopScore'}

    #: 0x3097c, ``mov.w r6, #0x40000000`` - the high half of 2.0.
    READ_DELAY = 2.0

    #: PORT ADDITION: with voice over off, what the screen reader says in place of the
    #: panel's own voice lines.
    PANEL_MESSAGE_TEXT = {227: 'Mission success.', 229: 'Paused.',
                          354: 'Game over.', 358: 'No coin.'}

    def _say(self, text):
        log.info('%s', text)
        if self.speech is None:
            from ..platform.speech import Speech
            self.speech = Speech.shared()
        self.speech.speak(text)

    def _panel_voice(self, sound, gain=0.2):
        """One of the panel's voice lines, or its words with voice over off."""
        if self.app.screen_reader and sound in self.PANEL_MESSAGE_TEXT:
            self._say(self.PANEL_MESSAGE_TEXT[sound])
        else:
            self.app.playSound_Gain_Pos_z_reprats_(sound, gain, (0.0, 0.0), 0, False)

    def pause_row_text(self, row):
        """PORT ADDITION: what the screen reader says for a panel row with voice over
        off, the label and its number together."""
        p = self.gamePlayer
        if row == 1:
            return {1: 'Paused', 2: 'Mission success', 3: 'Game over'}.get(self.gameState, '')
        if row == 2:
            return 'Number of killed zombies, %s' % whole(p.killMonsterCount)
        if row == 3:
            return 'Headshots, %s' % whole(p.HeadShotCount)
        if row == 4:
            return 'Score, %s' % whole(self.score_now())
        if row == 5:
            return 'Obtained gold, %s' % whole(self.ObtainedGold())
        if row == 9:
            rank = UserDefaults.standardUserDefaults().stringForKey_('NOWRANK')
            return 'The rank, %s' % (rank if rank else 'none')
        if row == 10:
            top = UserDefaults.standardUserDefaults().intForKey_('TOPSCORE')
            return 'Top score, %s' % whole(top)
        if row == 6:
            return 'Next stage, Button' if self.gameState == 2 else 'Continue, Button'
        if row == 7:
            return 'Restart, Button'
        if row == 8:
            return 'Main menu, Button'
        return ''

    # -[Stage_1_E StopElseSpeak] 0x30018
    def StopElseSpeak(self):
        """Silence the panel: every label it can speak, the number reader, and any
        reader still queued behind a label."""
        for num in (229, 230, 231, 232, 233, 223, 224, 225, 227, 228, 226,
                    354, 355, 356, 357):
            self.app.stopSoundBufNumber_(num)
        self.app.readStop()
        if self.speech is not None:
            self.speech.stop()
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
        if self.app.screen_reader:
            self._say(self.pause_row_text(row))
            return None

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

    def pause_jump(self, last=False):
        """PORT ADDITION: Home and End on the panel in the screen reader mode, the first
        row or the last of the ones it offers."""
        rows = self.pause_rows()
        row = rows[-1] if last else rows[0]
        self.pause_select(row)
        return row

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
        cannot be re-read; rows 3 and 4 are off by one against their labels, and row 1
        says "paused" even after a win or a death.

        **DIVERGENCE (2026-09-23, tsatria03's decision):** choosing a result row rereads
        that row, in both modes.  Row 1 says its own state again, row 3 the headshots,
        row 4 the score, and row 10 the top score; ``aidocks/DIVERGENCES.md`` has the
        original's table.
        """
        self.StopElseSpeak()
        row = self.selectMenu
        if self.app.screen_reader and row in (1, 2, 3, 4, 5, 9, 10):
            self._say(self.pause_row_text(row))
        elif row == 1:
            self.pause_select(1)                              # 229 in the original
        elif row == 2:
            self.ReadNumberOfZombies()
        elif row == 3:
            self.ReadNumberOfHeadshot()                       # nothing in the original
        elif row == 4:
            self.ReadScore()                                  # the headshots there
        elif row == 5:
            self.ReadObtainedGold()
        elif row == 10:
            self.ReadTopScore()                               # past the original's bound
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
        self._panel_voice(229)

    # -[Stage_1_E StopPlayAction:] 0x33df8
    def StopPlayAction_(self, *_):
        """The stop button.  While the tutorial is still running it ends the tutorial
        instead.

        ``bStop`` is set here and cleared again by ``continueAction:`` (0x33960) and
        ``gameReplayAction:`` (0x3310c), so the game can be paused as often as you like.
        """
        if self.missionCompletSounding:                       # 0x33e16
            return False
        if not self.isTutorial:                               # 0x33e30 -> L_33ea4
            self.tutorial_skip()
            return False
        if self.bStop:                                        # 0x33e40
            return False
        self.bStop = True                                     # 0x33e48
        return self._pause()

    def _pause(self):
        """What the stop button does once it has decided to pause."""
        self.app.playSound_Gain_Pos_z_reprats_(10, 0.2, (0.0, 0.0), 0, False)
        self._pause_stop_sounds()
        self._pause_players()
        if self.MotionSamplingTimer is not None and self.MotionSamplingTimer.isValid():
            self.MotionSamplingTimer.invalidate()
        self.MotionSamplingTimer = None
        # DIVERGENCE: the original leaves a pending ChangeLevel: alone, so it starts
        # the walk under the panel, and continue or restart starts a second walk
        # timer beside it: double speed.  Here the pause holds the level change.
        RunLoop.main().cancelPerform(self, 'ChangeLevel_')
        self.gameState = 1                                    # 0x34168
        self.walkXFlag = True                                 # 0x34296
        self.brearhFlag = True                                # 0x342a4
        self.MonsterStop()                                    # 0x342aa
        self._fill_result_labels()                            # 0x34302..0x34574
        self.selectMenu = 0
        # 0x34710..0x34732: "paused" (229) half a second after the click - the delay's
        # high word, movt r3 #0x3fe0, is dropped by the listing.  Nothing cancels it.
        RunLoop.main().perform(self, 'spaekMenu', None, PAUSED_VOICE_DELAY)
        return True

    def _pause_stop_sounds(self):
        """0x33e86..0x340e4.  Each branch loads its number into r2 and joins one
        ``stopSoundBufNumber:`` at 0x340e4, so the rain's area stops the rain (368),
        the forest its ambience (87), and only the cave stops two: its ambience (88)
        at 0x340da and its music (92) at 0x340e4."""
        if self.gameMode == 3:                                # 0x33e86
            self.app.stopSoundBufNumber_(368)                 # effect_forest_rainng
        elif self.gameMode == 2:                              # 0x33e8c
            self.app.stopSoundBufNumber_(87)                  # bgm_forest_amb
        elif self.gameMode == 1:                              # 0x340c4
            self.app.stopSoundBufNumber_(88)                  # bgm_cave_amb
            self.app.stopSoundBufNumber_(92)                  # bgm_cave

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
        self.bStop = False                                    # 0x33960
        self.app.playSound_Gain_Pos_z_reprats_(10, 0.2, (0.0, 0.0), 0, False)
        self.blindModeOff()
        if self.gameState != 1:                               # 0x339b2
            return False                                      # nothing to resume
        if self.levelChanging:
            # DIVERGENCE: the held level change gets its wait again, and starts the
            # walk itself when it lands.  See _pause.
            RunLoop.main().perform(self, 'ChangeLevel_', None, LEVEL_CHANGE_SECONDS)
        elif self.isTutorial:                                 # 0x33a02
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
        self._resume_players()
        self.selectMenu = 0
        return True

    def _pause_players(self):
        """DIVERGENCE: the original's pause stops only the notes above, never the
        ambience or the music player, and continue plays both again as notes over
        them (0x33b22..0x33be0).  Here both players are paused, and continue lets
        each carry on where it was: the music only if it was playing."""
        pb = self.app.playback
        self.pausedPlayers = []
        if pb is None:
            return
        for player in (pb.ambPlayer, pb.bgPlayer):
            if player.playing:
                player.pause()
                self.pausedPlayers.append(player)

    def _resume_players(self):
        """What ``_pause_players`` paused carries on."""
        for player in self.pausedPlayers:
            player.resume()
        self.pausedPlayers = []

    # -[Stage_1_E gameReplayAction:] 0x330ed
    def gameReplayAction_(self, *_):
        """Restart.  It costs a coin, the way starting a game from the menu does."""
        if not self.bStop:                                    # 0x33106
            return False
        self.bStop = False                                    # 0x3310c
        if self.app.Coin <= 0 and not self.app.debug:         # 0x33128; --debug needs no coin
            if self.app.screen_reader:
                self._panel_voice(358)
            else:
                self.app.playNoCoin_(0.2)
            self._reset_run_flags()                           # L_337b6 runs either way
            return False
        if not self.app.debug:                                # ...and spends none
            self.app.Coin -= 1                                # 0x33146
            d = UserDefaults.standardUserDefaults()
            d.setObject_forKey_('%d' % self.app.Coin, 'COIN')  # 0x331bc
            d.synchronize()
            self._coin_timer_start()                          # 0x33218
        self.app.playSound_Gain_Pos_z_reprats_(10, 0.2, (0.0, 0.0), 0, False)
        self.blindModeOff()
        self.gameState = 0                                    # 0x3326c
        if self.MotionSamplingTimer is not None and self.MotionSamplingTimer.isValid():
            self.MotionSamplingTimer.invalidate()
        self.MotionSamplingTimer = None
        RunLoop.main().cancelPerform(self, 'ChangeLevel_')    # DIVERGENCE, see _pause
        self.levelChanging = False
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
        by the next selector load.  See ``aidocks/DIVERGENCES.md``.
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
        self.ScoreLabel = '%d' % self.score_now()
        self.GoldLabel = '%d' % self.ObtainedGold()
