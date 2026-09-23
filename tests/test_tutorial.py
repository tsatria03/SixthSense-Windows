"""The ten tutorial beats, and the handoff into the real game.

Shortens the 9.5 s prompts so the whole run fits in a test; nothing else is changed.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sixthsense.game import stage_1_e as S1E                     # noqa: E402
from sixthsense.game import stage_tutorial as T                  # noqa: E402
from sixthsense.game.app_delegate import AppDelegate             # noqa: E402
from sixthsense.game.stage_tutorial import BEAT_NAMES, Stage_Tutorial  # noqa: E402
from sixthsense.platform.defaults import UserDefaults            # noqa: E402
from sixthsense.platform.runloop import RunLoop                  # noqa: E402

LANE = {1: 180.0, 2: 123.0, 3: 90.0, 4: 57.0, 5: 0.0}
_REAL_BEATS = list(T.BEATS)
_REAL_LOADING_SECONDS = S1E.LOADING_SECONDS


def _tutorial(prompt=0.4):
    """A tutorial with short prompts, and TUTORIAL cleared as on a fresh install."""
    T.BEATS[:] = [(n, s, prompt, sp) for (n, s, _d, sp) in _REAL_BEATS]
    S1E.LOADING_SECONDS = 0.0
    d = UserDefaults.standardUserDefaults()
    d.setObject_forKey_('0', 'TUTORIAL')
    d.synchronize()
    app = AppDelegate.shared()
    if app.playback is None:
        app.didFinishLaunching()
    RunLoop.main().reset()
    st = Stage_Tutorial()
    st.viewDidLoad()
    RunLoop.main().pump()                      # fire the (zeroed) loading delay
    st.gamePlayer.useWepon = 6                 # MG80, 1600 cm - reaches a fresh spawn
    st.weaponSource[6].BulletCount = 50
    return st


def _restore():
    T.BEATS[:] = _REAL_BEATS
    S1E.LOADING_SECONDS = _REAL_LOADING_SECONDS


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


def test_replaying_the_tutorial_does_not_read_it_as_finished():
    """0x7cfd8: the original forces isTutorial to 0. Without it, a save with
    TUTORIAL already "1" (from a previous completion or skip) made a replay
    start the walk timer immediately, and made P run the ordinary in-game pause
    instead of tutorial_skip, since isTutorial is what StopPlayAction_ branches
    on."""
    T.BEATS[:] = [(n, s, 0.4, sp) for (n, s, _d, sp) in _REAL_BEATS]
    S1E.LOADING_SECONDS = 0.0
    d = UserDefaults.standardUserDefaults()
    d.setObject_forKey_('1', 'TUTORIAL')          # already finished once before
    d.synchronize()
    app = AppDelegate.shared()
    if app.playback is None:
        app.didFinishLaunching()
    RunLoop.main().reset()
    st = Stage_Tutorial()
    try:
        st.viewDidLoad()
        RunLoop.main().pump()                      # fire the (zeroed) loading delay
        assert st.isTutorial == 0, 'a replay must not read as already finished'
        assert st.MotionSamplingTimer is None, 'the walk timer started during a replay'
        assert st.checkTutorialTimer is not None

        st.StopPlayAction_()
        assert st.checkTutorialTimer is None, 'P ran the ordinary pause, not tutorial_skip'
    finally:
        st.teardown()
        _restore()


def test_the_first_prompt_waits_for_now_loading_to_finish():
    """0x7d6a2: beat One's prompt used to start the instant MapInitInBundle ran,
    talking over Now Loading (46, played just before it in -[Stage_1_E
    viewDidLoad]).  It must wait LOADING_SECONDS first."""
    T.BEATS[:] = [(n, s, 0.4, sp) for (n, s, _d, sp) in _REAL_BEATS]
    S1E.LOADING_SECONDS = 0.3
    d = UserDefaults.standardUserDefaults()
    d.setObject_forKey_('0', 'TUTORIAL')
    d.synchronize()
    app = AppDelegate.shared()
    if app.playback is None:
        app.didFinishLaunching()
    RunLoop.main().reset()
    played = []
    real_play = app.playSound_Gain_Pos_z_reprats_
    app.playSound_Gain_Pos_z_reprats_ = \
        lambda num, *a, **k: (played.append(num), real_play(num, *a, **k))[-1]
    st = Stage_Tutorial()
    try:
        st.viewDidLoad()
        assert 46 in played, 'Now Loading did not play'
        assert 275 not in played, 'beat One spoke before Now Loading had time to finish'
        _pump(RunLoop.main(), 0.15)
        assert 275 not in played, 'beat One started before LOADING_SECONDS was up'
        _pump(RunLoop.main(), 0.3)
        assert 275 in played, 'beat One never started'
    finally:
        app.playSound_Gain_Pos_z_reprats_ = real_play
        st.teardown()
        _restore()


def test_leaving_the_tutorial_stops_the_current_prompt():
    """teardown() invalidated checkTutorialTimer but never stopped whatever beat's
    prompt was still playing, so it kept going right over the menu."""
    st = _tutorial(prompt=0.4)
    real_stop = st.app.stopSoundBufNumber_
    try:
        assert st.current_beat == 'One'
        stopped = []
        st.app.stopSoundBufNumber_ = \
            lambda num: (stopped.append(num), real_stop(num))[-1]
        st.teardown()
        assert 275 in stopped, "beat One's own prompt was not stopped"
    finally:
        st.app.stopSoundBufNumber_ = real_stop
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
        _pump(loop, S1E.SHOT_TRAVEL + 0.5, until=lambda: st.beat_done['One'])
        assert st.beat_done['One'], 'the kill did not finish beat One'
        got = _pump(loop, 4.0, until=lambda: st.current_beat == 'Two')
        assert got, 'the tutorial did not move on to beat Two'
    finally:
        st.teardown()
        _restore()


def test_a_kill_finishes_the_beat_in_debug_mode_too():
    """--debug counts no kill, but the tutorial's lessons still see the zombie die,
    so beat One finishes and the tutorial can be played through."""
    app = AppDelegate.shared()
    st = _tutorial(prompt=0.4)
    loop = RunLoop.main()
    app.debug = True
    try:
        _pump(loop, 3.0, until=lambda: bool(st.MonsterBuffer))
        m = st.MonsterBuffer[0]
        _pump(loop, 2.0, until=lambda: m.MovingPosAngle != 0)
        st.shotFlag = False
        st.MovingShot_(LANE[m.MovingType])
        _pump(loop, S1E.SHOT_TRAVEL + 0.5, until=lambda: st.beat_done['One'])
        assert st.beat_done['One'], 'in debug mode the kill did not finish beat One'
        assert st.gamePlayer.killMonsterCount == 0, 'the kill counted in debug mode'
    finally:
        app.debug = False
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


def test_p_silences_the_prompts_when_it_skips():
    """-[Stage_Tutorial StopPlayAction:] 0x8392a wrote TUTORIAL and played tutorial
    success without ever stopping CheckTutorial, so the prompts kept nagging after
    P supposedly skipped the tutorial."""
    st = _tutorial(prompt=0.4)
    loop = RunLoop.main()
    try:
        assert st.checkTutorialTimer is not None
        calls = []
        real_beat = st.tutorial_beat
        st.tutorial_beat = lambda name: (calls.append(name), real_beat(name))[-1]

        st.StopPlayAction_()
        assert st.checkTutorialTimer is None, 'CheckTutorial is still running'
        assert UserDefaults.standardUserDefaults().intForKey_('TUTORIAL') == 1

        _pump(loop, 2.0)
        assert not calls, 'a prompt restarted after P skipped the tutorial'
    finally:
        st.teardown()
        _restore()


def test_a_finished_prompt_does_not_restart_every_second():
    """tutorial_beat never cleared beat_flag[name], so once a beat's own prompt
    had finished playing once, tutorial_beat_end restarted it on every
    CheckTutorial tick forever - most visible on Six, Seven and Nine, which
    have no monster to gate the restart on."""
    st = _tutorial(prompt=0.4)
    try:
        calls = []
        real_beat = st.tutorial_beat
        st.tutorial_beat = lambda name: (calls.append(name), real_beat(name))[-1]

        st.current_beat = 'Six'
        st.tutorial_sound_stop('Six')          # the prompt has finished playing
        st.tutorial_beat_end('Six')            # one tick later: restart, as the original does
        assert calls == ['Six']

        st.tutorial_beat_end('Six')            # another tick, nothing has changed since
        assert calls == ['Six'], 'the prompt restarted again before its own delay was up'
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


def test_the_animal_zombie_grabs_you_by_itself():
    """CheckTutorial 0x8c754 calls MonsterAttPlayer while you are not held, so the
    grabber beat Eight sends in takes hold without anything calling it by hand."""
    st = _tutorial(prompt=0.4)
    try:
        for n in BEAT_NAMES[:8]:
            st.beat_done[n] = True
        st.tutorial_sound_stop('Eight')        # the prompt is over; type 73 comes in
        assert st.noAtt, 'the animal zombie can be shot'   # 0x8e1a8
        m = st.MonsterBuffer[0]
        m.monsterRange = 10.0
        st.CheckTutorial()
        assert st.isShake, 'CheckTutorial never let it grab'
        hp0 = st.gamePlayer.HP
        for _ in range(10):
            st.shake_step()
        _pump(RunLoop.main(), 2.0, until=lambda: not st.isShake)
        assert st.beat_done['Eight']
        assert st.gamePlayer.HP == hp0
    finally:
        st.teardown()
        _restore()


def test_a_zombie_that_reaches_you_restarts_its_beat():
    """0x3b3a2..0x3b41c: no heart lost, and the beat is prompted again."""
    st = _tutorial(prompt=0.4)
    try:
        calls = []
        real_beat = st.tutorial_beat
        st.tutorial_beat = lambda name: (calls.append(name), real_beat(name))[-1]
        st.MonsterInit_(2)                     # beat Two's zombie
        st.MonsterBuffer[0].monsterRange = 10.0
        hp0 = st.gamePlayer.HP
        st.MonsterAttPlayer()
        assert st.gamePlayer.HP == hp0, 'the tutorial took a heart'
        assert calls == ['Two'], calls
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
