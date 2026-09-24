"""The ten tutorial beats, and the handoff into the real game.

Shortens the 9.5 s prompts so the whole run fits in a test; nothing else is changed.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import _scratch_save                                             # noqa: E402,F401  never the real save

from sixthsense.game import stage_1_e as S1E                     # noqa: E402
from sixthsense.game import stage_tutorial as T                  # noqa: E402
from sixthsense.game.app_delegate import AppDelegate             # noqa: E402
from sixthsense.game.stage_tutorial import BEAT_NAMES, Stage_Tutorial  # noqa: E402
from sixthsense.platform.defaults import UserDefaults            # noqa: E402
from sixthsense.platform.runloop import RunLoop                  # noqa: E402

LANE = {1: 180.0, 2: 123.0, 3: 90.0, 4: 57.0, 5: 0.0}
_REAL_BEATS = list(T.BEATS)
_REAL_LOADING_SECONDS = S1E.LOADING_SECONDS


def _tutorial(prompt=0.4, first_run=False):
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
    st = Stage_Tutorial(first_run=first_run)
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

        for n in T.STOP_NEEDS:
            st.beat_done[n] = True
        st.StopPlayAction_()
        assert st.gameState == 0, 'P ran the ordinary pause, not tutorial_skip'
        assert st.checkTutorialTimer is None, 'P did not end the tutorial'
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


def test_voice_over_off_adds_the_keys_after_the_prompt():
    """PORT ADDITION: with voice over off, the key hint follows the recording, and
    names the player's own bindings."""
    from sixthsense.platform.keymap import KeyMap
    st = _tutorial(prompt=0.4)
    app = st.app
    km = KeyMap.shared()
    saved_mode, saved_bindings = app.mode, dict(km.bindings)
    said = []
    st._say = said.append
    try:
        app.mode = 1
        assert st.key_hint('One') is None, 'voice over on should stay recordings only'
        app.mode = 0
        km.bindings = {a: list(b) for a, b in km.bindings.items()}
        km.bindings['lane1'] = [('a',), ('left',)]
        km.bindings['reload'] = [('s',), ('r',), ('down',)]
        km.bindings['lane2'] = [('q',), ('left', 'up')]
        assert st.key_hint('One') == "Press A or Left Arrow to shoot toward 9 o'clock."
        assert st.key_hint('Two') == 'Press Q or Left Arrow plus Up Arrow to shoot toward 10:30.'
        assert st.key_hint('Six') == 'Press S, R, or Down Arrow to reload.'
        assert st.key_hint('FiveHalf') is None
        km.bindings['pause'] = [('p',)]
        assert st.key_hint('Nine') == 'Press P to end the tutorial.'
        km.bindings['shake'] = [('left shift', 'space'), ('right shift', 'space')]
        assert st.key_hint('Eight') == 'Press Shift plus Space a few times to shake the zombie off.'
        km.bindings['shake'] = [('left shift', 'space')]
        assert st.key_hint('Eight') == 'Press Left Shift plus Space a few times to shake the zombie off.'
        km.bindings['lane1'] = []
        assert st.key_hint('One') is None, 'an unbound action should say nothing'
        km.bindings['lane1'] = [('a',), ('left',)]
        assert not said, 'the hint was spoken over the recording'
        _pump(RunLoop.main(), 3.0, until=lambda: bool(said))
        assert said == ["Press A or Left Arrow to shoot toward 9 o'clock."], said
    finally:
        app.mode = saved_mode
        km.bindings = saved_bindings
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
    """0x84cfa..0x84d16: a reload only counts once One to FiveHalf are done, and then
    NextTutorial starts beat Seven at once (0x84d5a)."""
    st = _tutorial(prompt=0.4)
    try:
        st.GunReloadAction_()
        assert not st.beat_done['Six'], 'a reload during beat One finished beat Six'
        for n in T.REQUIRES['Six']:
            st.beat_done[n] = True
        st.GunReloadAction_()
        assert st.beat_done['Six']
        assert st.current_beat == 'Seven', st.current_beat
    finally:
        st.teardown()
        _restore()


def test_p_does_nothing_before_beat_eight_is_done():
    """0x83926..0x8393c: the stop button is ignored until beats One to Eight are
    done; it used to end the tutorial at any time and leave you stuck."""
    st = _tutorial(prompt=0.4)
    try:
        for n in BEAT_NAMES[:7]:               # One to Seven, Eight still to go
            st.beat_done[n] = True
        st.StopPlayAction_()
        assert not st.finished and not st.ending
        assert st.checkTutorialTimer is not None, 'CheckTutorial was stopped'
        assert st.gameState == 0, 'P paused the tutorial'
        assert UserDefaults.standardUserDefaults().intForKey_('TUTORIAL') == 0
    finally:
        st.teardown()
        _restore()


def test_p_ends_the_tutorial_row_back_at_the_menu():
    """Beat Nine: P plays tutorial success, and 3.05 s later -[Stage_Tutorial
    tutorialEnd:] (0x83738) is GameEndAction:."""
    st = _tutorial(prompt=0.4)
    loop = RunLoop.main()
    played = []
    real_play = st.app.playSound_Gain_Pos_z_reprats_
    st.app.playSound_Gain_Pos_z_reprats_ = \
        lambda num, *a, **k: (played.append(num), real_play(num, *a, **k))[-1]
    try:
        calls = []
        real_beat = st.tutorial_beat
        st.tutorial_beat = lambda name: (calls.append(name), real_beat(name))[-1]
        for n in T.STOP_NEEDS:
            st.beat_done[n] = True
        st.StopPlayAction_()
        assert st.beat_done['Nine'] and st.finished
        assert st.checkTutorialTimer is None, 'CheckTutorial is still running'
        assert UserDefaults.standardUserDefaults().intForKey_('TUTORIAL') == 1
        assert T.SOUND_TUTORIAL_SUCCESS in played
        st.StopPlayAction_()                   # a second P while it ends
        assert st.gameState == 0, 'P paused the ending'
        assert st.running
        assert _pump(loop, 4.0, until=lambda: not st.running), 'never went back to the menu'
        assert not calls, 'a prompt restarted after the tutorial ended'
        assert T.SOUND_ZOMBIES_COMING not in played
        assert st.MotionSamplingTimer is None, 'the tutorial row started the game'
    finally:
        st.app.playSound_Gain_Pos_z_reprats_ = real_play
        st.teardown()
        _restore()


def test_the_once_a_second_check_never_replays_a_prompt():
    """tutorialNEnd (0x8cb60 .. 0x8dd78) only slides the hint finger; a prompt is replayed
    only by tutorialNRestart, when the beat's monster reaches you, and tutorialSixRestart
    is never sent.  The port replayed the reload lesson's prompt about every ten seconds,
    since Six has no monster to hold it back."""
    st = _tutorial(prompt=0.4)
    try:
        calls = []
        real_beat = st.tutorial_beat
        st.tutorial_beat = lambda name: (calls.append(name), real_beat(name))[-1]

        st.current_beat = 'Six'
        st.tutorial_sound_stop('Six')          # the prompt has finished playing
        for _ in range(30):                    # half a minute of CheckTutorial ticks
            st.tutorial_beat_end('Six')
            st.CheckTutorial()
        assert calls == [], 'the reload prompt was replayed %d times' % len(calls)
    finally:
        st.teardown()
        _restore()


def test_weapon_change_finishes_beat_seven():
    st = _tutorial(prompt=0.4)
    try:
        AppDelegate.shared().useWeapon = ['1'] * 8
        st.gunChangeAction_(1)
        assert not st.beat_done['Seven'], 'Tab during beat One finished beat Seven'
        for n in T.REQUIRES['Seven'] + ('FiveHalf',):
            st.beat_done[n] = True
        st.gunChangeAction_(1)
        assert st.beat_done['Seven']
        assert st.current_beat != 'Eight', 'beat Eight came before the 1.5 s wait'
        assert _pump(RunLoop.main(), 2.5, until=lambda: st.current_beat == 'Eight'), \
            'beat Eight never came'
        st.threeTapChangeWeapon_()
        assert not st.beat_done['Nine'], 'the previous weapon finished beat Nine'
    finally:
        st.teardown()
        _restore()


def test_shaking_free_finishes_beat_eight():
    st = _tutorial(prompt=0.4)
    loop = RunLoop.main()
    try:
        for n in T.REQUIRES['Eight']:
            st.beat_done[n] = True
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


def _kill_the_beats_monster(st, loop):
    """Wait for the beat's monster and shoot it until it dies."""
    assert _pump(loop, 5.0, until=lambda: bool(st.MonsterBuffer)), \
        'beat %s sent no monster' % st.current_beat
    m = st.MonsterBuffer[0]
    _pump(loop, 2.0, until=lambda: m.MovingPosAngle != 0)
    for _ in range(40):
        if m not in st.MonsterBuffer:
            return
        st.shotFlag = False
        st.MovingShot_(LANE[m.MovingType])
        _pump(loop, S1E.SHOT_TRAVEL + 0.2, until=lambda: m not in st.MonsterBuffer)
    raise AssertionError('the monster of beat %s never died' % st.current_beat)


def test_the_whole_tutorial_plays_in_order():
    """Played through as a player would, with the reload and weapon keys pressed
    early: the beats come One to Nine, each once its action is done, and nothing
    pressed early finishes a later lesson."""
    st = _tutorial(prompt=0.4)
    loop = RunLoop.main()
    app = AppDelegate.shared()
    saved_weapons = list(app.useWeapon)
    order = ['One']
    real_beat = st.tutorial_beat
    st.tutorial_beat = lambda name: (order.append(name), real_beat(name))[-1]
    try:
        app.useWeapon = ['1'] * 8
        for name in ('One', 'Two', 'Three', 'Four', 'Five', 'FiveHalf'):
            assert _pump(loop, 3.0, until=lambda: st.current_beat == name), \
                'expected beat %s, at %s' % (name, st.current_beat)
            st.shotFlag = False
            st.ReloadGesture()                 # pressed early
            st.reloadGun_()
            st.gamePlayer.useWepon = 6
            st.doubleTapChangeWeapon_()        # pressed early
            st.gamePlayer.useWepon = 6
            st.weaponSource[6].BulletCount = 50
            assert not st.beat_done['Six'], 'an early reload finished beat Six'
            assert not st.beat_done['Seven'], 'an early Tab finished beat Seven'
            _kill_the_beats_monster(st, loop)
            assert st.beat_done[name], 'the kill did not finish beat %s' % name
        assert _pump(loop, 1.0, until=lambda: st.current_beat == 'Six')
        st.doubleTapChangeWeapon_()            # Tab before the reload
        st.gamePlayer.useWepon = 6
        assert not st.beat_done['Seven'], 'Tab during beat Six finished beat Seven'
        st.shotFlag = False
        st.ReloadGesture()
        assert st.beat_done['Six'] and st.current_beat == 'Seven'
        st.reloadGun_()
        st.doubleTapChangeWeapon_()
        assert st.beat_done['Seven']
        assert _pump(loop, 2.5, until=lambda: st.current_beat == 'Eight')
        assert _pump(loop, 3.0, until=lambda: bool(st.MonsterBuffer)), 'no animal zombie'
        st.MonsterBuffer[0].monsterRange = 10.0
        st.MonsterAttPlayer()
        assert st.isShake, 'the animal zombie did not grab'
        for _ in range(st.shakesNeeded):
            st.shake_step()
        assert _pump(loop, 3.0, until=lambda: st.current_beat == 'Nine'), \
            'beat Nine never came, at %s' % st.current_beat
        st.StopPlayAction_()
        assert st.finished
        seen = [n for i, n in enumerate(order) if i == 0 or order[i - 1] != n]
        assert seen == BEAT_NAMES, seen
    finally:
        app.useWeapon = saved_weapons
        st.teardown()
        _restore()


def test_the_first_run_counts_down_into_the_real_game():
    """-[Stage_1_E tutorialEnd:] 0x33bec reads 3, 2, 1, then tutorialEndGameStart:
    (0x33d40) 6.0 s later plays zombies are coming and starts the walk."""
    st = _tutorial(prompt=0.4, first_run=True)
    loop = RunLoop.main()
    read = []
    real_tts = st.app.TTSNumber_type_
    st.app.TTSNumber_type_ = lambda n, t: (read.append((n, t)), real_tts(n, t))[-1]
    T.ENDING_DELAY, T.COUNTDOWN_SECONDS = 0.2, 0.3
    try:
        for n in T.STOP_NEEDS:
            st.beat_done[n] = True
        st.StopPlayAction_()
        assert st.MotionSamplingTimer is None, 'the game started before the countdown'
        assert _pump(loop, 2.0, until=lambda: st.MotionSamplingTimer is not None), \
            'the walk never started'
        assert read == [(321, 1)], read
        assert st.running, 'the first run went back to the menu'
        assert st.isTutorial == 1, 'isTutorial was not set'          # 0x83786
        assert st.noAtt is False                                     # 0x83774
        assert st.shotFlag is False                                  # 0x83782
        assert not st.ending
        assert UserDefaults.standardUserDefaults().intForKey_('TUTORIAL') == 1
        st.StopPlayAction_()
        assert st.gameState == 1, 'P no longer pauses the real game'
    finally:
        T.ENDING_DELAY, T.COUNTDOWN_SECONDS = 3.05, 6.0
        st.app.TTSNumber_type_ = real_tts
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
