"""The ten tutorial beats, and the handoff into the real game.

Shortens the 9.5 s prompts so the whole run fits in a test; nothing else is changed.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sixthsense.game import stage_tutorial as T                  # noqa: E402
from sixthsense.game.app_delegate import AppDelegate             # noqa: E402
from sixthsense.game.stage_tutorial import BEAT_NAMES, Stage_Tutorial  # noqa: E402
from sixthsense.platform.defaults import UserDefaults            # noqa: E402
from sixthsense.platform.runloop import RunLoop                  # noqa: E402

LANE = {1: 180.0, 2: 123.0, 3: 90.0, 4: 57.0, 5: 0.0}
_REAL_BEATS = list(T.BEATS)


def _tutorial(prompt=0.4):
    """A tutorial with short prompts, and TUTORIAL cleared as on a fresh install."""
    T.BEATS[:] = [(n, s, prompt, sp) for (n, s, _d, sp) in _REAL_BEATS]
    d = UserDefaults.standardUserDefaults()
    d.setObject_forKey_('0', 'TUTORIAL')
    d.synchronize()
    app = AppDelegate.shared()
    if app.playback is None:
        app.didFinishLaunching()
    RunLoop.main().reset()
    st = Stage_Tutorial()
    st.viewDidLoad()
    st.gamePlayer.useWepon = 6                 # MG80, 1600 cm - reaches a fresh spawn
    st.weaponSource[6].BulletCount = 50
    return st


def _restore():
    T.BEATS[:] = _REAL_BEATS


def _pump(loop, seconds, until=None):
    t0 = time.monotonic()
    while time.monotonic() - t0 < seconds:
        loop.pump()
        if until is not None and until():
            return True
        time.sleep(0.004)
    return False


def test_the_beats_are_the_original_ten():
    assert BEAT_NAMES == ['One', 'Two', 'Three', 'Four', 'Five', 'FiveHalf',
                          'Six', 'Seven', 'Eight', 'Nine']
    prompts = {n: s for n, s, _d, _sp in _REAL_BEATS}
    # the instruction sounds, from each tutorialN (0x8ca6a and friends)
    assert prompts == {'One': 275, 'Two': 276, 'Three': 277, 'Four': 278, 'Five': 279,
                       'FiveHalf': 361, 'Six': 280, 'Seven': 281, 'Eight': 282,
                       'Nine': 284}
    # what each beat sends in, from tutorialNSoundStop
    spawns = {n: sp for n, _s, _d, sp in _REAL_BEATS}
    assert spawns == {'One': 1, 'Two': 2, 'Three': 3, 'Four': 4, 'Five': 5,
                      'FiveHalf': 63, 'Six': None, 'Seven': None, 'Eight': 73,
                      'Nine': None}
    # 9.5 s before the prompt is cut off, except beat eight at 6.5 (0x8ca84)
    delays = {n: d for n, _s, d, _sp in _REAL_BEATS}
    assert set(delays.values()) == {9.5, 6.5}
    assert delays['Eight'] == 6.5


def test_the_tutorial_does_not_walk():
    """-[Stage_Tutorial MapInitInBundle] arms CheckTutorial, not MotionSamplingTimer."""
    st = _tutorial()
    try:
        assert st.isTutorial == 0
        assert st.MotionSamplingTimer is None, 'the tutorial started the walk timer'
        assert st.checkTutorialTimer is not None
        start = st.gamePlayer.playerYplot
        _pump(RunLoop.main(), 3.0)
        assert st.gamePlayer.playerYplot == start, 'the player walked during the tutorial'
    finally:
        st.teardown()
        _restore()


def test_a_beat_prompts_then_sends_its_monster():
    st = _tutorial(prompt=0.4)
    loop = RunLoop.main()
    try:
        assert st.current_beat == 'One'
        assert not st.MonsterBuffer, 'the monster arrived before the prompt finished'
        got = _pump(loop, 3.0, until=lambda: bool(st.MonsterBuffer))
        assert got, 'no monster after the prompt'
        m = st.MonsterBuffer[0]
        assert m.MovingType == 1, 'beat One should send a lane-1 monster, got %d' % m.MovingType
    finally:
        st.teardown()
        _restore()


def test_killing_in_the_taught_lane_finishes_the_beat():
    st = _tutorial(prompt=0.4)
    loop = RunLoop.main()
    try:
        _pump(loop, 3.0, until=lambda: bool(st.MonsterBuffer))
        m = st.MonsterBuffer[0]
        _pump(loop, 2.0, until=lambda: m.MovingPosAngle != 0)
        st.shotFlag = False
        st.MovingShot_(LANE[m.MovingType])
        loop.pump()
        assert st.beat_done['One'], 'the kill did not finish beat One'
        got = _pump(loop, 4.0, until=lambda: st.current_beat == 'Two')
        assert got, 'the tutorial did not move on to beat Two'
    finally:
        st.teardown()
        _restore()


def test_reload_finishes_beat_six():
    st = _tutorial(prompt=0.4)
    try:
        st.GunReloadAction_()
        assert st.beat_done['Six']
    finally:
        st.teardown()
        _restore()


def test_weapon_change_finishes_beat_seven():
    st = _tutorial(prompt=0.4)
    try:
        AppDelegate.shared().useWeapon = ['1'] * 8
        st.gunChangeAction_(1)
        assert st.beat_done['Seven']
        st.threeTapChangeWeapon_()
        assert st.beat_done['Nine']
    finally:
        st.teardown()
        _restore()


def test_shaking_free_finishes_beat_eight():
    st = _tutorial(prompt=0.4)
    loop = RunLoop.main()
    try:
        st.MonsterInit_(73)                    # what beat eight sends in
        m = st.MonsterBuffer[0]
        assert m.shakeMonsterFlag, 'type73 is not a grabber'
        m.monsterRange = 10.0
        st.MonsterAttPlayer()
        assert st.isShake
        for _ in range(10):
            st.shake_step()
        _pump(loop, 2.0, until=lambda: not st.isShake)
        assert st.beat_done['Eight'], 'shaking free did not finish beat Eight'
    finally:
        st.teardown()
        _restore()


def test_the_handoff_starts_the_real_game():
    """-[Stage_Tutorial tutorialEndGameStart:] 0x8374c"""
    st = _tutorial(prompt=0.4)
    try:
        for n in BEAT_NAMES[:-1]:
            st.beat_done[n] = True
        st.threeTapChangeWeapon_()             # the last beat
        assert st.finished
        assert st.isTutorial == 1, 'isTutorial was not set'          # 0x83786
        assert st.noAtt is False                                     # 0x83774
        assert st.shotFlag is False                                  # 0x83782
        assert st.MotionSamplingTimer is not None, 'the walk never started'
        assert st.checkTutorialTimer is None, 'CheckTutorial is still running'
        assert UserDefaults.standardUserDefaults().intForKey_('TUTORIAL') == 1
    finally:
        st.teardown()
        _restore()


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
