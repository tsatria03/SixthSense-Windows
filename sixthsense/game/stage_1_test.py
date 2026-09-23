"""``Stage_1_TEST`` - the weapon test range.  Ported from 0x40468..0x521ec.

The Try button on a weapon's page in the shop pushes it
(``-[DetailStoreController testAction:]`` 0x1c1c0), holding the weapon being tried
(``setTestWeapon:``).  It is its own class, a copy of ``Stage_1_E`` with 38 of the
methods they share changed; the rest are the stage's own, so this subclasses it and
overrides only what differs.  What it amounts to:

**One weapon.**  You hold the weapon you are trying (0x40be0: ``setUseWepon:
testWeapon``) and nothing else: ``gunChangeAction:`` is a bare return (0x49198, ``bx lr``),
so the weapon keys do nothing.

**No walking.**  ``MainControl`` (0x459d4) never steps you forward.  You stand at the
top of the corridor, (20, 680), where the action cell is 9, so the music stays off.
Every tick spawns from tier 1 (``monster_num`` is set to 1 before ``MakeMonster:``,
0x45f12), so up to three of the first two kinds of zombie come at once (the
``LVUP + 2`` cap, with ``LVUP`` 1).

**Five kills and it is over.**  With ``killMonsterCount`` at 5 or more (0x45be6) the
ambience and music stop, ``bgm_game_complete`` (90) plays, and the result panel comes
up 8 s later (``MissionSuccessTell``, 0x45da2).  Losing your last heart ends it the way
the stage does.  Either way the panel says "game over" (354), and the gold for the run
is 12% of the score (0x46aa2: ``vldr d17, 0.12``), not the stage's twelve a kill.

**The panel** has no rank and no top score, and nothing is written to either.  Its
last row is "back" (13), and it goes back to the weapon's page.  Restarting costs no
coin.  The tutorial is treated as finished (0x409c2: ``isTutorial = 1``), whatever the
save says, so the zombies hit and the rounds are spent.
"""
from __future__ import annotations

import logging

from ..platform import volume
from ..platform.defaults import UserDefaults
from ..platform.runloop import RunLoop
from .player_control import PlayerControl
from . import stage_1_e
from .stage_1_e import (MONSTER_ARRAY, SOUND_NOW_LOADING,
                        SOUND_PLAYER_DIE, SOUND_SWORD_START, Stage_1_E, arc4random)

log = logging.getLogger('test')

#: -[DetailStoreController testAction:] 0x1c1d8..0x1c204: the shop's weaponType to the
#: weapon slot the range hands you.  Anything else, the grenade included, is slot 0.
TEST_WEAPON = {1: 3, 2: 4, 3: 5, 4: 6, 5: 7, 6: 8}

WIN_KILLS = 5                   # 0x45be6: cmp r0, #5
SOUND_GAME_COMPLETE = 90        # bgm_game_complete, 0x45d74
SOUND_SAW_WAIT = 74             # weapon_saw_wait, 0x48be4
SOUND_BACK = 13                 # back button, the panel's last row (0x43f92)
SOUND_MISSION_SUCCESS = 227
SOUND_MISSION_FAIL = 228
SOUND_PAUSED = 229
SOUND_CONTINUE = 223


def test_weapon_for(weaponType):
    return TEST_WEAPON.get(weaponType, 0)


class Stage_1_TEST(Stage_1_E):
    """The weapon test range: one weapon, standing still, five kills."""

    #: The panel's rows, in order: no rank (9) and no top score (10).
    PAUSE_ROWS = (1, 2, 3, 4, 5, 6, 7, 8)
    PAUSE_ROW_SOUND = {2: 230, 3: 231, 4: 232, 5: 233, 7: 224, 8: SOUND_BACK}
    PAUSE_ROW_READER = {2: 'ReadNumberOfZombies', 3: 'ReadNumberOfHeadshot',
                        4: 'ReadScore', 5: 'ReadObtainedGold'}
    PANEL_MESSAGE_TEXT = dict(Stage_1_E.PANEL_MESSAGE_TEXT)

    #: F2 and Shift+F2 of --debug have no corridor to move along here.
    IS_TEST_RANGE = True

    def __init__(self, testWeapon=0):
        super().__init__()
        self.testWeapon = testWeapon            # setTestWeapon:, 0x521d4

    # ================================================================ loading
    # -[Stage_1_TEST viewDidLoad] 0x40468
    def viewDidLoad(self):
        self.app.playSound_Gain_Pos_z_reprats_(
            SOUND_NOW_LOADING, 0.2, (0.0, 0.0), 0, False)          # 0x41082
        self.isTutorial = 1                                         # 0x409c2
        self._new_player()                                          # 0x409f4..0x40bf2
        self.MonsterBuffer = []                                     # 0x40d06
        self.monsterArray = list(MONSTER_ARRAY)                     # 0x40fc2
        # 0x40fce: and r0, r0, #1 - the cave or the forest, never the rain, where the
        # stage picks from all three (0x2d360: % 3).
        self.gameMode = (arc4random() & 1) + 1
        self.changeGameMode()
        self.running = True
        RunLoop.main().perform(self, 'MapInitInBundle', None, stage_1_e.LOADING_SECONDS)

    def _new_player(self):
        """What ``viewDidLoad`` and ``gameReplayAction:`` both do: a fresh player with
        three hearts at the top of the corridor, level 1, holding the test weapon with
        a full magazine."""
        p = PlayerControl()                     # every tally starts at 0 (0x40a5a..)
        p.HP = 3                                # 0x40a2c
        p.playerXplot = 20                      # 0x40b8e
        p.playerYplot = 680                     # 0x40ba6
        self.gamePlayer = p
        self.monsterHPGain = 1.0                # 0x40bc4
        self.LVUP = 1                           # 0x40bd2
        p.useWepon = self.testWeapon            # 0x40be0
        self.weaponInit()                       # 0x40bf2
        weapon = self.weaponSource[p.useWepon] if p.useWepon < len(self.weaponSource) else None
        if weapon:
            weapon.BulletCount = weapon.ReloadGun()                 # 0x40c48

    # -[Stage_1_TEST weaponInit] 0x48908
    def weaponInit(self):
        """The stage's eight weapons, then the sound of drawing the one you hold: the
        saw's idle loop for slot 8 (0x48be4), the sword's draw for slot 7 (0x48c2e)."""
        super().weaponInit()
        use = self.gamePlayer.useWepon
        if use == 8:
            self.app.playSound_Gain_Pos_z_reprats_(
                SOUND_SAW_WAIT, 0.1, (0.0, 0.0), 40, True)
        else:
            self.app.stopSoundBufNumber_(SOUND_SAW_WAIT)            # 0x48bfa
        if use == 7:
            self.app.playSound_Gain_Pos_z_reprats_(
                SOUND_SWORD_START, 1.0, (0.0, 0.0), 40, False)

    # -[Stage_1_TEST MapInitInBundle] 0x417cc
    def MapInitInBundle(self):
        """The stage's maps, and the cave's or the forest's ambience (0x41978 tests
        for 2 and 1, the only areas the range picks)."""
        self.app.BGMusicStop()
        self._load_maps()
        pb = self.app.playback
        if self.gameMode == 2:
            pb.startAMBPlayer_type_soundGain_Loop_(
                'bgm_forest_amb', 'wav', volume.ambience(0.2), True)
        elif self.gameMode == 1:
            pb.startAMBPlayer_type_soundGain_Loop_(
                'bgm_cave_amb', 'wav', volume.ambience(0.2), True)
        pb.setListenerRotation_(self.facing.radians)
        self.running = True
        self.walkXFlag = False                                      # 0x41c48
        self.brearhFlag = False                                     # 0x41c58
        self.MotionSamplingTimer = RunLoop.main().scheduledTimer(   # 0x41ca0
            1.0, self, 'MainControl', None, True)
        if self.app.debug:
            self._say('Debug mode.')

    # ============================================================== the clock
    # -[Stage_1_TEST MainControl] 0x459d4
    def MainControl(self, timer=None):
        if self.walkXFlag or self.isShake:                          # 0x459f0, 0x45a06
            return
        self._breathe()                                             # 0x45a20..0x45b1c

        p = self.gamePlayer
        if p.killMonsterCount >= WIN_KILLS:                         # 0x45be6
            self.app.stopSoundBufNumber_(88)                        # bgm_cave_amb
            self.app.stopSoundBufNumber_(92)                        # bgm_cave
            self.walkXFlag = True                                   # 0x45c1a
            self.gameState = 2                                      # 0x45c30
            self.app.playSound_Gain_Pos_z_reprats_(
                SOUND_GAME_COMPLETE, 0.5, (0.0, 0.0), 0, False)     # 0x45d74
            self.missionCompletSounding = True                      # 0x45d9c
            RunLoop.main().perform(self, 'MissionSuccessTell', None, 8.0)   # 0x45da2
            return

        # The action layer, read where you stand.  That is always (20, 680), cell 9,
        # so only its branch is ever taken: the music stops and the tier is set, and
        # then set to 1 regardless.  Cells 8 and 10 (the girl or the woman, and the
        # music) cannot be reached from here.
        action = self.stage.movePlayActionState_PlotY_(p.playerXplot, p.playerYplot)
        if action == 9:                                             # 0x45dc0
            self.app.playback.backgroundSoundStop()                 # 0x45de2
        if action != 0 and action not in (8, 10):
            self.monster_num = action                               # 0x45ef4
        self.monster_num = 1                                        # 0x45f12
        self.MakeMonster_(self.monster_num)
        self.MonsterAttPlayer()
        self.HPImageCount()
        self.walkXFlag = True                                       # 0x45f6a
        RunLoop.main().perform(self, 'timerLeft', None, 0.6)        # 0x45f7a

        if p.HP == 0 and not self.DieFlag:                          # 0x45f92
            # 0x4e838 in MonsterAttPlayer (0x4e438) does the same the moment a hit leaves you at
            # 0; the flag keeps it to one death however the last heart went.
            self.DieFlag = True
            self.app.playSound_Gain_Pos_z_reprats_(
                SOUND_PLAYER_DIE, 1.0, (0.0, 0.0), 40, False)       # 0x4607a
            RunLoop.main().perform(self, 'playerDie_', None, 1.3)   # 0x460a0

    # -[Stage_1_TEST StopPlayAction:] 0x479b8
    def StopPlayAction_(self, *_):
        """The stage's pause, with its first checks the other way round: ``bStop`` is
        tested and set before the end-of-run music is (0x479d6, 0x479e6, 0x479ee), so
        pressing it while that plays still marks the game stopped.  ``isTutorial`` is
        always 1 here, so the tutorial branch is never taken."""
        if self.bStop:                                              # 0x479d6
            return False
        self.bStop = True                                           # 0x479e6
        if self.missionCompletSounding:                             # 0x479ee
            return False
        return self._pause()

    def _pause_stop_sounds(self):
        """0x47a46..0x47c74: the forest's ambience (87), or the cave's ambience and
        music (88, 92).  There is no test for the rain, which the range never picks."""
        if self.gameMode == 2:
            self.app.stopSoundBufNumber_(87)
        elif self.gameMode == 1:
            self.app.stopSoundBufNumber_(88)
            self.app.stopSoundBufNumber_(92)

    # =============================================================== weapons
    # -[Stage_1_TEST gunChangeAction:] 0x49198 - a bare return.
    def gunChangeAction_(self, step=1):
        return None

    # ================================================================ ending
    def ObtainedGold(self):
        """0x46a92..0x46b2c (and 0x4f7c4 for the panel): the score, headshot
        multiplier and all, times 0.12, cut to a whole number."""
        return int(self.score_now() * 0.12)

    def _pay_gold(self):
        gold = self.ObtainedGold()
        self.app.haveGold += gold                                   # 0x46b30
        d = UserDefaults.standardUserDefaults()
        d.setObject_forKey_('%d' % self.app.haveGold, 'GOLD')       # 0x46ba2
        d.synchronize()                                             # 0x46bc4

    # -[Stage_1_TEST MissionSuccessTell] 0x46820
    def MissionSuccessTell(self, *_):
        """The five kills are in.  No STAGE key and no top score, and the voice line
        is "game over" (354), the same as a death's."""
        self.missionCompletSounding = False                         # 0x46848
        self.bStop = True                                           # 0x4684e
        self.app.stopSoundBufNumber_(92 if self.gameMode == 1 else 91)   # 0x46870
        self._pay_gold()
        self.gameState = 2                                          # 0x46be6
        self._panel_voice(354, 0.5)                                 # 0x46bf8
        self.SuccessOrFailMission()                                 # 0x46c04

    # -[Stage_1_TEST missionFailTell:] 0x46438
    def missionFailTell_(self, *_):
        self.missionCompletSounding = False                         # 0x46460
        self.bStop = True                                           # 0x46466
        self.app.stopSoundBufNumber_(92 if self.gameMode == 1 else 91)   # 0x46488
        self.gameState = 3                                          # 0x464da
        self._panel_voice(354, 0.5)                                 # 0x464ec
        # 0x467ee writes GOLD without a synchronize; iOS saves it on its own soon
        # after, so the port saves it here.
        self._pay_gold()
        self.SuccessOrFailMission()                                 # 0x467fa

    # -[Stage_1_TEST SuccessOrFailMission] 0x482f0
    def SuccessOrFailMission(self):
        """The stage's, without the top score, the week's best or the rank."""
        if self.MotionSamplingTimer is not None and self.MotionSamplingTimer.isValid():
            self.MotionSamplingTimer.invalidate()
        self.MotionSamplingTimer = None
        self.walkXFlag = True                                       # 0x48354
        self.brearhFlag = True                                      # 0x48362
        self.MonsterStop()                                          # 0x48368
        self._fill_result_labels()
        self.selectMenu = 0

    def updateTopscoreRank(self):
        pass                    # the range has no top score and no rank

    # ================================================================= panel
    def pause_rows(self):
        """All eight, whatever the state.  Row 6 only speaks while paused (0x44688:
        ``gameState == 1``, or nothing), and after a win or a death it is silent and
        does what ``continueAction:`` does then: the click (10) and nothing else."""
        return self.PAUSE_ROWS

    def pause_row_text(self, row):
        if row == 1:
            return {1: 'Paused', 2: 'Mission success', 3: 'Mission fail'}.get(self.gameState, '')
        if row == 6:
            return 'Continue, Button' if self.gameState == 1 else ''
        if row == 8:
            return 'Back, Button'
        return super().pause_row_text(row)

    def pause_select(self, row):
        """-[Stage_1_TEST selectTapPointSoundStart] 0x43c24.  Rows 1 and 6 name
        themselves by the state (0x4427c, 0x44688); the rest are the stage's."""
        if row not in (1, 6) or self.app.screen_reader:
            return super().pause_select(row)
        self.selectMenu = row
        self.StopElseSpeak()
        if row == 1:
            sound = {3: SOUND_MISSION_FAIL, 2: SOUND_MISSION_SUCCESS,
                     1: SOUND_PAUSED}.get(self.gameState)            # 0x446e2, 0x4429a, 0x4470e
        else:
            sound = SOUND_CONTINUE if self.gameState == 1 else None  # 0x449fc
        if sound is not None:
            self.app.playSound_Gain_Pos_z_reprats_(sound, 0.2, (0.0, 0.0), 0, False)
        return sound

    # -[Stage_1_TEST gameReplayAction:] 0x46d70
    def gameReplayAction_(self, *_):
        """Restart.  Unlike the stage's, it costs no coin."""
        if not self.bStop:
            return False
        self.bStop = False
        self.app.playSound_Gain_Pos_z_reprats_(10, 0.2, (0.0, 0.0), 0, False)   # 0x46db6
        self.blindModeOff()
        self.gameState = 0                                          # 0x46de4
        if self.MotionSamplingTimer is not None and self.MotionSamplingTimer.isValid():
            self.MotionSamplingTimer.invalidate()
        self.MotionSamplingTimer = None
        self.MonsterDealloc()
        self.MonsterBuffer = []
        self._new_player()                                          # 0x46ed2..0x47144
        self.DieFlag = False
        self.score = 0
        # 0x471fe..0x47292 fetches the ground map from the developer's Dropbox and
        # builds the level when it arrives; the port reads the bundled one.
        self.MapInitInBundle()
        self._reset_run_flags()                                     # 0x474a6..0x474de
        self.selectMenu = 0
        self.running = True
        return True

    # -[Stage_1_TEST GameEndAction:] 0x46c28
    def GameEndAction_(self, *_):
        """The back row: back to the weapon's page."""
        if self.gamePlayer.useWepon == 8:                           # 0x46c4e
            self.app.stopSoundBufNumber_(SOUND_SAW_WAIT)
        return super().GameEndAction_()                             # 10, the pop, 0x46d54
