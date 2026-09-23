"""The weapon test range, ``Stage_1_TEST``: the Try button's one weapon, standing still,
tier 1 zombies, five kills to win, and its own panel.

Opens the audio device, so it needs OpenAL Soft present.  The clock is driven by
calling ``MainControl`` by hand, so nothing walks in while a test looks.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sixthsense.game import stage_1_e as S1E                    # noqa: E402
from sixthsense.game.app_delegate import AppDelegate            # noqa: E402
from sixthsense.game.stage_1_test import Stage_1_TEST           # noqa: E402
from sixthsense.platform.runloop import RunLoop                 # noqa: E402


def _range(slot=4):
    """A range holding ``slot`` (4 is the M4A1), past its loading delay, with every
    sound it plays recorded in ``played``."""
    S1E.LOADING_SECONDS = 0.0
    app = AppDelegate.shared()
    if app.playback is None:
        app.didFinishLaunching()
    app.mode = 1                              # voice over on: the recordings play
    RunLoop.main().reset()
    played = []
    real = app.playSound_Gain_Pos_z_reprats_
    app.playSound_Gain_Pos_z_reprats_ = lambda n, *a: (played.append(n), real(n, *a))
    st = Stage_1_TEST(slot)
    st._say = lambda text: None               # never the real screen reader
    st.viewDidLoad()
    RunLoop.main().pump()                     # fire the (zeroed) loading delay
    return app, st, played


def _done(app, st):
    del app.playSound_Gain_Pos_z_reprats_
    st.teardown()


def _tick(st):
    """One MainControl, as the timer would, with the 0.6 s walkXFlag let go."""
    st.walkXFlag = False
    st.MainControl()


def test_it_holds_the_test_weapon_and_stands_still():
    """0x40be0: useWepon is testWeapon.  MainControl never steps you, and the weapon
    keys do nothing (gunChangeAction: is bx lr, 0x49198)."""
    app, st, _played = _range(4)
    try:
        assert st.gamePlayer.useWepon == 4
        assert st.isTutorial == 1, 'the range must count as past the tutorial'
        assert st.weaponSource[4].BulletCount > 0, 'the magazine is not loaded'
        for _ in range(5):
            _tick(st)
        assert st.gamePlayer.playerYplot == 680, 'the range walked you'
        st.doubleTapChangeWeapon_()
        st.threeTapChangeWeapon_()
        assert st.gamePlayer.useWepon == 4, 'the weapon changed'
    finally:
        _done(app, st)


def test_the_sword_is_drawn_as_the_range_opens():
    """0x48c2e: weaponInit plays the sword's draw (329) when slot 7 is the one held."""
    app, st, played = _range(7)
    try:
        assert S1E.SOUND_SWORD_START in played, played
    finally:
        _done(app, st)


def test_it_sends_tier_1_zombies_three_at_most():
    """0x45f12: monster_num is 1 before every MakeMonster:, and LVUP 1 caps them at
    three.  Tier 1 is MONSTER_ARRAY 0..9, the first two kinds."""
    app, st, _played = _range()
    try:
        for _ in range(40):
            _tick(st)
            assert len(st.MonsterBuffer) <= 3, 'more than three at once'
        assert st.MonsterBuffer, 'nothing came'
        assert {m.monsterNumber for m in st.MonsterBuffer} <= {1, 2}, \
            [m.monsterNumber for m in st.MonsterBuffer]
    finally:
        _done(app, st)


def test_five_kills_win_and_pay_twelve_percent_of_the_score():
    """0x45be6: five kills stop the clock and play bgm_game_complete (90); 8 s later
    MissionSuccessTell pays int(score * 0.12) into GOLD and says game over (354)."""
    app, st, played = _range()
    try:
        p = st.gamePlayer
        p.killMonsterCount = 5
        p.killMonster1count = 5               # 5 * 150 = 750, no headshots
        gold0 = app.haveGold
        _tick(st)
        assert 90 in played, played
        assert st.gameState == 2 and st.missionCompletSounding
        st.MissionSuccessTell()
        assert app.haveGold == gold0 + 90, (gold0, app.haveGold)
        assert played[-1] == 354, played[-3:]
        assert st.bStop
    finally:
        _done(app, st)


def test_the_panel_has_no_rank_and_its_last_row_is_back():
    """0x43c24: rows 1 to 8 only, in every state.  Row 1 is 227 after a win, 228 after a
    death and 229 when paused; row 6 only speaks while paused (223); row 8 is back (13)."""
    app, st, played = _range()
    try:
        st.gameState = 2
        assert st.pause_rows() == (1, 2, 3, 4, 5, 6, 7, 8)
        assert st.pause_select(1) == 227
        assert st.pause_select(6) is None, 'row 6 spoke after a win'
        assert st.pause_select(8) == 13
        st.gameState = 3
        assert st.pause_select(1) == 228
        st.gameState = 1
        assert 6 in st.pause_rows()
        assert st.pause_select(1) == 229
        assert st.pause_select(6) == 223
    finally:
        _done(app, st)


def test_restarting_costs_no_coin():
    """0x46d70: the range's restart takes no coin and hands you the same weapon."""
    app, st, _played = _range(5)
    try:
        coins = app.Coin
        st.gamePlayer.killMonsterCount = 3
        st.bStop = True
        assert st.gameReplayAction_() is True
        assert app.Coin == coins, 'the restart took a coin'
        assert st.gamePlayer.killMonsterCount == 0
        assert st.gamePlayer.useWepon == 5
        assert st.running
    finally:
        _done(app, st)


def test_losing_the_last_heart_ends_it_once():
    """0x45f92: at 0 hearts, player_die (84) and playerDie: 1.3 s later, once."""
    app, st, played = _range()
    try:
        st.gamePlayer.HP = 0
        _tick(st)
        _tick(st)
        assert played.count(S1E.SOUND_PLAYER_DIE) == 1, played
    finally:
        _done(app, st)


def test_it_is_always_the_cave_or_the_forest():
    """0x40fce: gameMode is (arc4random() & 1) + 1, never 3, the rain."""
    from sixthsense.game import stage_1_test
    real = stage_1_test.arc4random
    try:
        for value, mode in ((0, 1), (1, 2), (2, 1), (5, 2), (0xFFFFFFFF, 2)):
            stage_1_test.arc4random = lambda v=value: v
            app, st, _played = _range()
            try:
                assert st.gameMode == mode, (value, st.gameMode)
            finally:
                _done(app, st)
    finally:
        stage_1_test.arc4random = real


def test_pausing_and_ending_stop_what_the_original_stops():
    """The pause (0x47a46..0x47c74) stops 87 in the forest, 88 and 92 in the cave.  A
    win or a death (0x46870, 0x46488) stops 92 in the cave and 91 in the forest."""
    for mode, pause, end in ((1, [88, 92], 92), (2, [87], 91)):
        app, st, _played = _range()
        stopped = []
        real = app.stopSoundBufNumber_
        app.stopSoundBufNumber_ = lambda n: (stopped.append(n), real(n))
        try:
            st.gameMode = mode
            st.StopPlayAction_()
            assert [n for n in stopped if n in (87, 88, 91, 92, 368)] == pause, stopped
            stopped.clear()
            st.missionFailTell_()
            assert [n for n in stopped if n in (87, 88, 91, 92, 368)] == [end], stopped
        finally:
            del app.stopSoundBufNumber_
            _done(app, st)


def test_the_pause_marks_the_game_stopped_even_while_the_ending_plays():
    """0x479d6..0x479ee: the range sets bStop before it looks at
    missionCompletSounding, and then does nothing more."""
    app, st, _played = _range()
    try:
        st.missionCompletSounding = True
        assert st.StopPlayAction_() is False
        assert st.bStop and st.gameState == 0
    finally:
        _done(app, st)


def test_the_back_row_leaves_the_range():
    """GameEndAction: 0x46c28 pops back to the weapon's page."""
    app, st, _played = _range()
    try:
        st.GameEndAction_()
        assert not st.running
    finally:
        _done(app, st)


def test_going_back_to_the_weapon_page_silences_the_cave():
    """The back row, then the frame loop's teardown, stop the ambience and the music:
    straight away, after a pause and a resume, and while Now Loading still plays."""
    from sixthsense.game import stage_1_test
    real = stage_1_test.arc4random
    stage_1_test.arc4random = lambda: 0         # the cave
    try:
        for how in ('at once', 'after a pause', 'while loading'):
            if how == 'while loading':
                S1E.LOADING_SECONDS = 5.0
                app = AppDelegate.shared()
                RunLoop.main().reset()
                st = Stage_1_TEST(4)
                st._say = lambda text: None
                st.viewDidLoad()
            else:
                app, st, _played = _range()
                del app.playSound_Gain_Pos_z_reprats_
                if how == 'after a pause':
                    st.StopPlayAction_()
                    st.continueAction_()
            pb = app.playback
            assert st.gameMode == 1
            st.GameEndAction_()
            st.teardown()                       # what the frame loop does next
            RunLoop.main().pump()
            assert not pb.ambPlayer.playing, 'the ambience plays on (%s)' % how
            assert not pb.bgPlayer.playing, 'the other player plays on (%s)' % how
    finally:
        stage_1_test.arc4random = real
        S1E.LOADING_SECONDS = 0.0


def test_the_corridor_keys_of_debug_mode_do_nothing_here():
    """F2 and Shift+F2 have no level or section to move to in the range."""
    from sixthsense.game import debug
    app, st, _played = _range()
    said = []
    st._say = said.append
    try:
        lv = st.LVUP
        debug.perform(st, 'debug_next_level', 3)
        debug.perform(st, 'debug_next_section', 3)
        assert st.LVUP == lv and st.gamePlayer.playerYplot == 680
        assert said and 'no levels' in said[-1], said
    finally:
        _done(app, st)


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
