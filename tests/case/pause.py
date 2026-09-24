"""The pause and result panel: the rows, the dispatch table and the three buttons.

Everything here is checked against ``-[Stage_1_E selectTapPointSoundStart]`` (0x30168),
``-[Stage_1_E tapCount]`` (0x2fec8) and the four action methods behind them.
"""
from __future__ import annotations

import os
import plistlib
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import _scratch_save                                             # noqa: E402,F401  never the real save

from sixthsense import paths                                    # noqa: E402
from sixthsense.game import stage_1_e as S1E                    # noqa: E402
from sixthsense.game.app_delegate import AppDelegate            # noqa: E402
from sixthsense.game.stage_1_e import Stage_1_E                 # noqa: E402
from sixthsense.platform.defaults import UserDefaults           # noqa: E402
from sixthsense.platform.runloop import RunLoop                 # noqa: E402


def _new_stage(coins=3):
    S1E.LOADING_SECONDS = 0.0
    d = UserDefaults.standardUserDefaults()
    d.setObject_forKey_('1', 'FIREST')          # past the first-launch ten coins
    d.setObject_forKey_('1', 'TUTORIAL')
    d.setObject_forKey_(str(coins), 'COIN')
    d.removeObjectForKey_('TOPSCORE')
    d.removeObjectForKey_('TOPSCOREWEEK')
    d.removeObjectForKey_('NOWRANK')
    d.synchronize()
    app = AppDelegate.shared()
    if app.playback is None:
        app.didFinishLaunching()
    app.Coin = coins
    RunLoop.main().reset()
    st = Stage_1_E()
    st.viewDidLoad()
    RunLoop.main().pump()                       # fire the (zeroed) loading delay
    return app, st


def test_the_rows_are_the_bands_of_the_panel():
    """0x308b6..0x311ec, top to bottom: header, the five readouts, top score, then the
    three buttons.  The rank (9) is left out: its ranking server is gone."""
    assert Stage_1_E.PAUSE_ROWS == (1, 2, 3, 4, 5, 10, 6, 7, 8)
    sl = plistlib.load(open(paths.path_for_resource('SoundList', 'plist'), 'rb'))
    for row, sound in Stage_1_E.PAUSE_ROW_SOUND.items():
        assert paths.path_for_resource(sl[sound], 'wav'), row
    for sound in (229, 223, 226, 354):
        assert paths.path_for_resource(sl[sound], 'wav'), sound


def test_the_header_and_the_first_button_follow_the_state():
    """0x308e4 and 0x30efc: the two rows whose label depends on gameState."""
    _app, st = _new_stage()
    try:
        st.gameState = 1
        assert st.pause_select(1) == 229          # paused
        assert st.pause_select(6) == 223          # continue button
        st.gameState = 2
        assert st.pause_select(1) is None         # silent after a success
        assert st.pause_select(6) == 226          # next stage button
        st.gameState = 3
        assert st.pause_select(1) == 354          # game over
    finally:
        st.teardown()


def test_there_is_no_continue_row_after_a_death():
    """0x30efe: gameState 3 leaves row 6 before it speaks."""
    _app, st = _new_stage()
    try:
        st.gameState = 1
        assert 6 in st.pause_rows()
        st.gameState = 3
        assert 6 not in st.pause_rows()
        assert st.pause_rows() == (1, 2, 3, 4, 5, 10, 7, 8)
    finally:
        st.teardown()


def test_up_and_down_walk_the_rows_and_wrap():
    _app, st = _new_stage()
    try:
        st.gameState = 1
        seen = [st.pause_move(1) for _ in range(len(Stage_1_E.PAUSE_ROWS))]
        assert seen == list(Stage_1_E.PAUSE_ROWS), seen
        st.selectMenu = 1
        assert st.pause_move(-1) == 8, 'moving up off the top did not wrap'
    finally:
        st.teardown()


def test_home_and_end_on_the_panel_in_the_screen_reader_mode():
    """With voice over off, Home and End go to the panel's first row and its last, and
    Left and Right to the previous row and the next; with voice over on, End and Right
    stay where they were."""
    from sixthsense.ui.input import Input

    class _Pygame:
        KEYDOWN, KEYUP, QUIT = 1, 2, 3

        class key:
            @staticmethod
            def name(k):
                return k

    class _Key:
        type = _Pygame.KEYDOWN

        def __init__(self, name):
            self.key = name

    app, st = _new_stage()
    said = []
    st._say = said.append                   # never the real screen reader
    try:
        st.gameState = 1
        rows = st.pause_rows()
        keys = Input(st)
        app.mode = 0
        keys.handle(_Key('end'), _Pygame)
        assert st.selectMenu == rows[-1], 'End went to row %d' % st.selectMenu
        assert said, 'End did not read the row'
        keys.handle(_Key('home'), _Pygame)
        assert st.selectMenu == rows[0], 'Home went to row %d' % st.selectMenu
        app.mode = 1
        st.selectMenu = rows[2]
        keys.handle(_Key('end'), _Pygame)
        assert st.selectMenu == rows[2], 'End jumped with voice over on'

        # Left and Right, as VoiceOver's flicks: with voice over off only.
        keys.handle(_Key('right'), _Pygame)
        assert st.selectMenu == rows[2], 'Right moved with voice over on'
        app.mode = 0
        keys.handle(_Key('right'), _Pygame)
        assert st.selectMenu == rows[3], 'Right went to row %d' % st.selectMenu
        keys.handle(_Key('left'), _Pygame)
        keys.handle(_Key('left'), _Pygame)
        assert st.selectMenu == rows[1], 'Left went to row %d' % st.selectMenu
    finally:
        app.mode = 1
        st.teardown()


def test_selecting_a_readout_queues_its_number():
    """Each band plays its label and schedules its reader 2 s behind it (0x3097c)."""
    _app, st = _new_stage()
    loop = RunLoop.main()
    try:
        st.gameState = 2
        st.gamePlayer.killMonsterCount = 7
        st.pause_select(2)
        assert Stage_1_E.READ_DELAY == 2.0
        queued = [q for _d, _s, q in loop._performs
                  if q.selector == 'ReadNumberOfZombies']
        assert queued, 'the reader was not queued'
        st.ReadNumberOfZombies()
        assert st.killZombiesLabel == '7'
    finally:
        st.teardown()


def test_the_score_row_reads_the_score_aloud():
    """-[Stage_1_E ReadScore] 0x3bf38 ends with [app TTSNumber:score type:1] (0x3c1f2,
    0x3c1fa): landing on the score row reads the score digit by digit, 2 s behind its
    label, as the other result rows read theirs.  Working the score out anywhere else
    says nothing."""
    app, st = _new_stage()
    loop = RunLoop.main()
    spoken = []
    real = app.TTSNumber_type_
    app.TTSNumber_type_ = lambda n, t: spoken.append((n, t))
    try:
        st.gameState = 2
        p = st.gamePlayer
        p.killMonster1count, p.killMonster9count = 2, 1        # 300 + 300
        assert st.score_now() == 600 and spoken == [], 'working it out spoke'
        st.pause_select(4)
        queued = [q for _d, _s, q in loop._performs if q.selector == 'ReadScore']
        assert queued, 'the score row did not queue its reader'
        st.ReadScore()
        assert spoken == [(600, 1)], 'the score was not read: %r' % spoken
        assert st.ScoreLabel == '600'
    finally:
        del app.TTSNumber_type_
        assert app.TTSNumber_type_ == real
        st.teardown()


def test_choosing_a_result_row_rereads_that_row():
    """The original's ``tbb`` at 0x2ff32 (04 25 61 30 3b 4b 51 57) left row 3 silent,
    had row 4 read the headshots and could not reach the top score.  The port rereads
    the row chosen, with voice over on as it already did with voice over off."""
    app, st = _new_stage()
    spoken = []
    app.TTSNumber_type_ = lambda n, t: spoken.append(n)
    try:
        st.gameState = 2
        p = st.gamePlayer
        p.killMonsterCount, p.HeadShotCount = 5, 2
        p.killMonster1count = 4                             # 600, x1.02 for 2 headshots
        score = st.score_now()
        d = UserDefaults.standardUserDefaults()
        d.setObject_forKey_('9000', 'TOPSCORE')

        for row, number in ((2, 5), (3, 2), (4, score), (10, 9000)):
            spoken.clear()
            st.selectMenu = row
            st.pause_activate()
            assert spoken == [number], 'row %d read %r, not %r' % (row, spoken, number)

        st.selectMenu = 9            # the rank row is left out, and reads nothing
        spoken.clear()
        st.pause_activate()
        assert spoken == []
    finally:
        del app.TTSNumber_type_
        UserDefaults.standardUserDefaults().removeObjectForKey_('TOPSCORE')
        st.teardown()


def test_choosing_the_first_row_says_its_own_state():
    """Row 1 is "paused", "mission success" (silent) or "game over" by the state; the
    original replayed 229, "paused", whatever the state.  Choosing it now says the row's
    own label again."""
    app, st = _new_stage()
    played = []
    real = app.playSound_Gain_Pos_z_reprats_
    app.playSound_Gain_Pos_z_reprats_ = lambda n, *a: played.append(n)
    try:
        for state, sound in ((1, 229), (3, 354)):
            st.gameState = state
            st.selectMenu = 1
            played.clear()
            st.pause_activate()
            assert played == [sound], 'state %d played %r' % (state, played)
    finally:
        app.playSound_Gain_Pos_z_reprats_ = real
        del app.playSound_Gain_Pos_z_reprats_
        st.teardown()


def test_pausing_works_again_after_continue():
    """bStop is set at 0x33e48, and continueAction: clears it at 0x33960 (a
    conditional store the listings drop), so the game pauses as often as you like.
    Until continue, a second press does nothing."""
    _app, st = _new_stage()
    try:
        for _ in range(3):
            assert st.StopPlayAction_() is True, 'the pause did not come up'
            assert st.gameState == 1 and st.bStop is True
            assert st.MotionSamplingTimer is None, 'the walk timer kept running'
            assert st.walkXFlag is True and st.brearhFlag is True
            assert st.StopPlayAction_() is False, 'paused over its own panel'
            assert st.continueAction_() is True
            assert st.gameState == 0 and st.bStop is False
            assert st.MotionSamplingTimer is not None, 'the walk did not come back'
    finally:
        st.teardown()


def test_restart_clears_the_pause_too():
    """gameReplayAction: clears bStop at 0x3310c, coin or no coin."""
    app, st = _new_stage()
    try:
        st.StopPlayAction_()
        app.Coin = 0
        st.gameReplayAction_()
        assert st.bStop is False
    finally:
        st.teardown()


def test_continue_puts_the_walk_back():
    _app, st = _new_stage()
    try:
        st.StopPlayAction_()
        assert st.continueAction_() is True
        assert st.gameState == 0
        assert st.walkXFlag is False and st.brearhFlag is False
        assert st.MotionSamplingTimer is not None, 'the walk timer did not come back'
        st.gameState = 2
        assert st.continueAction_() is False, 'it resumed from the result panel'
    finally:
        st.teardown()


def test_pausing_pauses_the_ambience_and_the_music_and_continue_carries_them_on():
    """DIVERGENCE: the original's pause leaves both players running and continue
    plays both again as notes over them.  Here each pauses on its own player and
    carries on there, and the music comes back only if it was playing."""
    app, st = _new_stage()
    pb = app.playback
    try:
        amb_path = pb.ambPlayer.path
        pb.startBGPlayer_type_soundGain_Loop_('bgm_cave', 'wav', 0.02, True)
        music_path = pb.bgPlayer.path
        assert pb.ambPlayer.playing and pb.bgPlayer.playing
        st.StopPlayAction_()
        assert not pb.ambPlayer.playing, 'the ambience plays on under the panel'
        assert not pb.bgPlayer.playing, 'the music plays on under the panel'
        st.continueAction_()
        assert pb.ambPlayer.playing and pb.ambPlayer.path == amb_path, \
            'the ambience did not come back on its own player'
        assert pb.bgPlayer.playing and pb.bgPlayer.path == music_path, \
            'the music did not come back on its own player'

        pb.backgroundSoundStop()                 # a section's quiet stretch
        st.StopPlayAction_()
        st.continueAction_()
        assert pb.ambPlayer.playing, 'the ambience did not come back'
        assert not pb.bgPlayer.playing, 'continue started music that was not playing'
    finally:
        st.teardown()

def _walk_timers(st):
    return [t for t in RunLoop.main()._timers
            if t.target is st and t.selector == 'MainControl' and t.isValid()]


def _past_the_level_change():
    RunLoop.main().pump(now=time.monotonic() + S1E.LEVEL_CHANGE_SECONDS + 0.5)


def test_pausing_while_the_level_changes_holds_it():
    """DIVERGENCE: the original's ChangeLevel: fires under the panel and starts the
    walk there, and continue adds a second walk timer. Here the pause holds it, and
    continue gives it its wait again."""
    _app, st = _new_stage()
    try:
        st._level_transition()
        gain = st.monsterHPGain
        assert st.StopPlayAction_() is True
        _past_the_level_change()
        assert st.monsterHPGain == gain, 'the level changed under the pause panel'
        assert not _walk_timers(st), 'the walk started under the pause panel'
        assert st.continueAction_() is True
        assert not _walk_timers(st), 'continue walked before the level changed'
        _past_the_level_change()
        assert st.monsterHPGain == gain * 1.5, 'the level never changed after continue'
        assert st.levelChanging is False
        assert len(_walk_timers(st)) == 1, 'more than one walk timer'
    finally:
        st.teardown()


def test_restarting_while_the_level_changes_walks_at_one_speed():
    _app, st = _new_stage()
    try:
        st._level_transition()
        st.StopPlayAction_()
        assert st.gameReplayAction_() is True
        _past_the_level_change()
        assert st.LVUP == 1 and st.monsterHPGain == 1.0, 'the old level change landed'
        assert st.levelChanging is False
        assert len(_walk_timers(st)) == 1, 'restart left two walk timers'
    finally:
        st.teardown()

def test_debug_mode_restarts_without_a_coin_and_spends_none():
    for coins in (0, 2):
        app, st = _new_stage(coins=coins)
        app.debug = True
        try:
            st.StopPlayAction_()
            assert st.gameReplayAction_() is True, 'debug mode refused to restart'
            assert app.Coin == coins, 'debug mode spent a coin'
            assert UserDefaults.standardUserDefaults().intForKey_('COIN') == coins
        finally:
            app.debug = False
            st.teardown()

def test_restart_costs_a_coin_and_resets_the_run():
    app, st = _new_stage(coins=2)
    try:
        st.gamePlayer.killMonsterCount = 9
        st.gamePlayer.HeadShotCount = 4
        st.gamePlayer.playerYplot = 500
        st.gamePlayer.HP = 1
        st.StopPlayAction_()
        assert st.gameReplayAction_() is True
        assert app.Coin == 1, 'the coin was not spent'
        assert UserDefaults.standardUserDefaults().intForKey_('COIN') == 1
        assert st.gamePlayer.HP == 3
        assert st.gamePlayer.playerYplot == 680 and st.gamePlayer.playerXplot == 20
        assert st.gamePlayer.killMonsterCount == 0
        assert st.gamePlayer.HeadShotCount == 0
        assert st.LVUP == 1 and st.monsterHPGain == 1.0
        assert st.MonsterBuffer == []
        assert st.gameState == 0 and st.running is True
    finally:
        st.teardown()


def test_restart_with_no_coin_says_so():
    app, st = _new_stage(coins=0)
    try:
        st.StopPlayAction_()
        before = st.gamePlayer.playerYplot
        assert st.gameReplayAction_() is False
        assert app.Coin == 0
        assert st.gamePlayer.playerYplot == before, 'it restarted anyway'
        assert st.gameState == 1, 'the panel went away'
    finally:
        st.teardown()


def test_the_main_menu_button_ends_the_run():
    _app, st = _new_stage()
    try:
        st.StopPlayAction_()
        assert st.GameEndAction_() is True
        assert st.running is False
        assert st.MonsterBuffer == []
        assert st.MotionSamplingTimer is None
    finally:
        st.teardown()


def test_gold_is_twelve_a_kill_and_two_a_headshot():
    """0x3c616 - and every per-kind tally the method reads first is discarded."""
    _app, st = _new_stage()
    try:
        p = st.gamePlayer
        p.killMonsterCount, p.HeadShotCount = 10, 3
        p.killMonster9count = 100          # dead weight in the original too
        assert st.ObtainedGold() == 12 * 10 + 2 * 3
        st.ReadObtainedGold()
        assert st.GoldLabel == '126'
    finally:
        st.teardown()


def test_a_death_shows_the_panel_eleven_seconds_later():
    """0x3bd2c stores 11.0, and missionFailTell: is what sets gameState 3."""
    _app, st = _new_stage()
    loop = RunLoop.main()
    try:
        st.playerDie_()
        assert st.gameState == 0, 'the panel went up immediately'
        assert st.missionCompletSounding is True
        q = [p for _d, _s, p in loop._performs
             if p.selector == 'missionFailTell_']
        assert q, 'missionFailTell: was not queued'
        assert abs((q[0].due - time.monotonic()) - 11.0) < 0.5, 'not an 11 s wait'
        st.missionFailTell_()
        assert st.gameState == 3
        assert st.bStop is True, 'the panel cannot take a button press'
        assert st.missionCompletSounding is False
    finally:
        st.teardown()


def test_a_run_that_beats_the_stored_best_saves_it():
    """0x34c56 / 0x34cc0 - TOPSCORE and TOPSCOREWEEK."""
    _app, st = _new_stage()
    d = UserDefaults.standardUserDefaults()
    try:
        st.gamePlayer.killMonster9count = 4          # 4 * 300 = 1200
        st.gamePlayer.killMonsterCount = 4
        st.SuccessOrFailMission()
        assert st.score == 1200, st.score
        assert d.intForKey_('TOPSCORE') == 1200
        assert d.intForKey_('TOPSCOREWEEK') == 1200
        assert st.TopScoreLabel == '1200'
        assert st.ScoreLabel == '1200'
        assert st.GoldLabel == '48'                  # 12 * 4 kills, no headshots
    finally:
        st.teardown()


def test_finishing_the_mission_banks_the_gold():
    app, st = _new_stage()
    try:
        before = app.haveGold
        st.gamePlayer.killMonsterCount = 3
        st.MissionSuccessTell()
        assert st.gameState == 2
        assert app.haveGold == before + 36
        assert UserDefaults.standardUserDefaults().intForKey_('GOLD') == app.haveGold
        assert app.stage == 11, 'STAGE was not opened up'
    finally:
        st.teardown()


class _Recorder:
    def __init__(self):
        self.said = []

    def speak(self, text, interrupt=True):
        self.said.append(text)
        return True

    def stop(self):
        pass


def test_with_voice_over_off_the_panel_speaks_its_rows():
    """PORT ADDITION: mode 0 reads each row with its number, whole."""
    app, st = _new_stage(coins=0)
    st.speech = _Recorder()
    app.mode = 0
    try:
        st.gamePlayer.killMonsterCount = 105
        st.gamePlayer.HeadShotCount = 3
        st.StopPlayAction_()
        st.pause_select(1)
        assert st.speech.said[-1] == 'Paused'
        st.pause_select(2)
        assert st.speech.said[-1] == 'Number of killed zombies, 105'
        st.pause_select(5)
        assert st.speech.said[-1] == 'Obtained gold, 1,266'
        st.pause_activate()
        assert st.speech.said[-1] == 'Obtained gold, 1,266', 'the row was not reread'
        st.pause_select(6)
        assert st.speech.said[-1] == 'Continue, Button'
        st.pause_select(7)
        st.pause_activate()                                  # no coin
        assert st.speech.said[-1] == 'No coin.'
        st.gameState = 3
        st.missionFailTell_()
        assert 'Game over.' in st.speech.said
    finally:
        app.mode = 1
        st.teardown()


if __name__ == '__main__':
    fns = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    bad = 0
    for fn in fns:
        try:
            fn()
            print('ok    %s' % fn.__name__)
        except AssertionError as e:
            bad += 1
            print('FAIL  %s: %s' % (fn.__name__, e))
        except Exception as e:
            bad += 1
            print('ERROR %s: %r' % (fn.__name__, e))
    print('%d/%d passed' % (len(fns) - bad, len(fns)))
    sys.exit(1 if bad else 0)
