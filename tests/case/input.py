"""The keyboard: the clock-face defaults, chords, and rebinding.

Runs pygame headless (`SDL_VIDEODRIVER=dummy`) and feeds synthetic key events through
`Input.handle`, the same path the real window uses. Bindings are kept in a temporary
file so the player's own `keys.json` is never touched.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import _scratch_save                                             # noqa: E402,F401  never the real save

import pygame                                                    # noqa: E402

from sixthsense.game import stage_1_e as S1E                     # noqa: E402
from sixthsense.game.app_delegate import AppDelegate             # noqa: E402
from sixthsense.game.stage_1_e import Stage_1_E                  # noqa: E402
from sixthsense.platform.defaults import UserDefaults            # noqa: E402
from sixthsense.platform.keymap import (ACTION_IDS, CHORD_WINDOW,  # noqa: E402
                                        DEFAULTS, FIXED, KeyMap)
from sixthsense.platform.runloop import RunLoop                  # noqa: E402
from sixthsense.ui.input import LANE_ANGLE, Input                # noqa: E402
from sixthsense.ui.keybind_screen import KeyBindScreen           # noqa: E402


def _stage():
    if not pygame.get_init():
        pygame.init()
        pygame.display.set_mode((64, 64))
    S1E.LOADING_SECONDS = 0.0
    d = UserDefaults.standardUserDefaults()
    d.setObject_forKey_('1', 'TUTORIAL')
    d.synchronize()
    app = AppDelegate.shared()
    if app.playback is None:
        app.didFinishLaunching()
    RunLoop.main().reset()
    st = Stage_1_E()
    st.viewDidLoad()
    RunLoop.main().pump()                     # fire the (zeroed) loading delay
    km = KeyMap(path=os.path.join(tempfile.mkdtemp(), 'keys.json'))
    return st, Input(st, keymap=km)


def _down(inp, *names):
    for n in names:
        inp.handle(pygame.event.Event(pygame.KEYDOWN,
                                      key=pygame.key.key_code(n), mod=0), pygame)


def _up(inp, *names):
    for n in names:
        inp.handle(pygame.event.Event(pygame.KEYUP,
                                      key=pygame.key.key_code(n), mod=0), pygame)


def _settle(inp):
    """Let a pending chord window close."""
    time.sleep(CHORD_WINDOW + 0.02)
    inp.pump()


def _fire(inp, *names):
    """Press a key or chord and let it resolve, as a player would."""
    inp.stage.shotFlag = False
    _down(inp, *names)
    _settle(inp)
    _up(inp, *names)


# ---------------------------------------------------------------- defaults
def test_the_defaults_are_the_clock_face():
    """The tutorial teaches the lanes as clock positions; the arrows are a clock."""
    assert DEFAULTS['lane1'] == [('a',), ('left',)]              # 9 o'clock
    assert DEFAULTS['lane2'] == [('q',), ('left', 'up')]         # 10:30
    assert DEFAULTS['lane3'] == [('w',), ('up',)]                # 12
    assert DEFAULTS['lane4'] == [('e',), ('right', 'up')]        # 1:30
    assert DEFAULTS['lane5'] == [('d',), ('right',)]             # 3 o'clock
    assert ('down',) in DEFAULTS['reload']                       # 6 o'clock
    # The original never turns you (setListenerRotation: is not in __objc_selrefs),
    # so there is nothing to turn with
    assert 'turn_left' not in DEFAULTS and 'turn_right' not in DEFAULTS
    for a in ACTION_IDS:
        for b in DEFAULTS[a]:
            assert not any(k in FIXED for k in b), '%s binds a fixed key' % a


def test_every_letter_still_attacks_its_lane():
    st, inp = _stage()
    try:
        for name, lane in (('a', 1), ('q', 2), ('w', 3), ('e', 4), ('d', 5)):
            _fire(inp, name)
            assert st.shotMonster == lane, \
                '%s gave lane %d, wanted %d' % (name.upper(), st.shotMonster, lane)
            assert st.shotAngle == LANE_ANGLE[lane]
    finally:
        st.teardown()


def test_the_arrows_attack_their_lanes():
    st, inp = _stage()
    try:
        for names, lane in ((('left',), 1), (('up',), 3), (('right',), 5)):
            _fire(inp, *names)
            assert st.shotMonster == lane, \
                '%s gave lane %d, wanted %d' % (names, st.shotMonster, lane)
    finally:
        st.teardown()


# ------------------------------------------------------------------ chords
def test_the_diagonals_are_chords():
    st, inp = _stage()
    try:
        for names, lane in ((('left', 'up'), 2), (('right', 'up'), 4)):
            _fire(inp, *names)
            assert st.shotMonster == lane, \
                '%s gave lane %d, wanted %d' % (names, st.shotMonster, lane)
    finally:
        st.teardown()


def test_a_chord_works_either_way_round():
    st, inp = _stage()
    try:
        _fire(inp, 'up', 'left')          # Up first this time
        assert st.shotMonster == 2
        _fire(inp, 'up', 'right')
        assert st.shotMonster == 4
    finally:
        st.teardown()


def test_a_single_key_does_not_also_fire_its_chord():
    """Left alone is lane 1 and must not leak into lane 2."""
    st, inp = _stage()
    try:
        st.shotFlag = False
        _down(inp, 'left')
        assert st.shotMonster == 0, 'lane fired before the chord window closed'
        _settle(inp)
        assert st.shotMonster == 1
        _up(inp, 'left')
    finally:
        st.teardown()


def test_completing_a_chord_fires_at_once():
    """Adding Up inside the window gives lane 2, not lane 1 then lane 2."""
    st, inp = _stage()
    try:
        st.shotFlag = False
        _down(inp, 'left')
        _down(inp, 'up')                  # well inside CHORD_WINDOW
        assert st.shotMonster == 2, 'the chord did not take over'
        _settle(inp)
        assert st.shotMonster == 2, 'the window fired a second, wrong lane'
        _up(inp, 'left', 'up')
    finally:
        st.teardown()


def test_rolling_from_one_attack_key_to_the_next():
    """A player does not let go before pressing the next lane.  The key just pressed is
    what decides, so A still held and D pressed is lane 5 - it used to be lane 1 again,
    because both bindings matched and the order of the action list broke the tie."""
    st, inp = _stage()
    try:
        st.shotFlag = False
        _down(inp, 'a')
        _settle(inp)
        assert st.shotMonster == 1
        st.shotFlag = False
        _down(inp, 'd')                   # A is still down
        _settle(inp)
        assert st.shotMonster == 5, 'rolling onto D gave lane %d' % st.shotMonster
        _up(inp, 'a', 'd')

        # and the chord still wins when its own key is the new one
        st.shotFlag = False
        _down(inp, 'left')
        _settle(inp)
        assert st.shotMonster == 1
        st.shotFlag = False
        _down(inp, 'up')                  # Left still down: this is the 10:30 chord
        _settle(inp)
        assert st.shotMonster == 2, 'Left plus Up gave lane %d' % st.shotMonster
        _up(inp, 'left', 'up')
    finally:
        st.teardown()


def test_shift_tab_is_a_chord_too():
    st, inp = _stage()
    try:
        AppDelegate.shared().useWeapon = ['1'] * 8
        before = st.gamePlayer.useWepon
        _fire(inp, 'tab')
        after = st.gamePlayer.useWepon
        assert after != before
        _fire(inp, 'left shift', 'tab')
        assert st.gamePlayer.useWepon == before, 'Shift+Tab did not go back'
    finally:
        st.teardown()


# ----------------------------------------------------------------- actions
def test_reload_and_no_turning():
    st, inp = _stage()
    loop = RunLoop.main()
    try:
        w = st.weaponSource[st.gamePlayer.useWepon]
        full = w.ReloadGun()
        for names in (('s',), ('r',), ('down',)):
            w.BulletCount = 0
            _fire(inp, *names)
            t0 = time.monotonic()
            while time.monotonic() - t0 < w.ReloadTime + 0.5:
                loop.pump()
                time.sleep(0.004)
            assert w.BulletCount == full, '%s did not reload' % (names,)

        before = st.facing.Angle
        _fire(inp, '.')
        _fire(inp, ',')
        assert st.facing.Angle == before, 'comma or full stop still turned you'
        assert not hasattr(st, 'turn_left') and not hasattr(st, 'turn_right')
    finally:
        st.teardown()


def test_f1_and_escape_are_not_the_stage_s():
    st, inp = _stage()
    try:
        _down(inp, 'f1')
        assert inp.open_bindings, 'F1 did not ask for the binding screen'
        assert not inp.quit
        inp.open_bindings = False
        _down(inp, 'escape')
        assert not inp.quit, 'Escape left the stage instead of pausing'
    finally:
        st.teardown()


def test_escape_pauses_and_resumes():
    """PORT ADDITION: Escape is P in a stage, and Continue on the pause panel."""
    st, inp = _stage()
    try:
        _down(inp, 'escape')
        assert st.gameState == 1, 'Escape did not pause'
        _down(inp, 'escape')
        assert st.gameState == 0, 'Escape did not resume'
        assert st.MotionSamplingTimer is not None, 'the walk did not start again'
        _down(inp, 'escape')
        assert st.gameState == 1, 'Escape did not pause a second time'
        st.gameState = 3                                  # a death: nothing to resume
        _down(inp, 'escape')
        assert st.gameState == 3 and not inp.quit
    finally:
        st.teardown()


def test_escape_still_leaves_the_tutorial():
    """The tutorial's stop button skips it, so Escape leaves instead of pausing."""
    from sixthsense.game.stage_tutorial import Stage_Tutorial
    assert Stage_Tutorial.ESCAPE_LEAVES
    st, _inp = _stage()
    try:
        inp = Input(st, keymap=_inp.keymap)
        st.ESCAPE_LEAVES = True
        _down(inp, 'escape')
        assert inp.quit and st.gameState == 0
    finally:
        st.teardown()


def test_the_clock_stops_while_it_is_held():
    """F1 over a stage holds the run loop: nothing fires, and on resume every due
    date has moved on by the time it was held."""
    loop = RunLoop.main()
    loop.reset()

    class _T:
        fired = 0

        def tick(self, *_):
            self.fired += 1

    t = _T()
    loop.perform(t, 'tick', None, 0.05)
    loop.hold()
    time.sleep(0.1)
    loop.pump()
    assert t.fired == 0, 'it fired while held'
    loop.resume()
    loop.pump()
    assert t.fired == 0, 'the wait was not moved on by the time held'
    time.sleep(0.08)
    loop.pump()
    assert t.fired == 1
    loop.reset()


def test_there_is_no_mouse():
    st, inp = _stage()
    try:
        before = (st.shotMonster, st.shotFlag, st.facing.Angle)
        for ev in (pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(0, 0)),
                   pygame.event.Event(pygame.MOUSEMOTION, rel=(-60, 0), pos=(0, 0)),
                   pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(-60, 0))):
            inp.handle(ev, pygame)
        assert (st.shotMonster, st.shotFlag, st.facing.Angle) == before
        assert not hasattr(inp, 'begin_drag')
    finally:
        st.teardown()


# --------------------------------------------------------------- rebinding
def test_rebinding_takes_effect_and_steals_the_key():
    st, inp = _stage()
    try:
        inp.keymap.set_binding('lane5', ('a',))      # A was lane 1
        assert inp.keymap.bindings['lane1'] == [('left',)], 'A was not taken away'
        _fire(inp, 'a')
        assert st.shotMonster == 5, 'the rebind did not take effect'
        _fire(inp, 'left')
        assert st.shotMonster == 1, 'lane 1 lost its other binding too'
    finally:
        st.teardown()


def test_a_new_chord_can_be_bound():
    st, inp = _stage()
    try:
        inp.keymap.set_binding('shake', ('left ctrl', 'space'))
        st.isShake = True
        st.shakeFlag = 1
        st.shakeCount = 0
        _fire(inp, 'left ctrl', 'space')
        assert st.shakeCount == 1, 'the bound chord did not shake'
    finally:
        st.teardown()


def test_holding_the_shake_key_is_one_shake():
    """A held key's repeats are not further shakes; each needs its own press."""
    st, inp = _stage()
    try:
        st.isShake = True
        st.shakeFlag = 1
        st.shakeCount = 0
        st.shakesNeeded = 5
        _down(inp, 'space')
        _settle(inp)
        _down(inp, 'space')                    # the OS repeating a held key
        _down(inp, 'space')
        _settle(inp)
        assert st.shakeCount == 1, 'holding Space shook %d times' % st.shakeCount
        _up(inp, 'space')
        _fire(inp, 'space')
        assert st.shakeCount == 2, 'a fresh press did not shake'
    finally:
        st.teardown()


def test_bindings_survive_a_round_trip():
    path = os.path.join(tempfile.mkdtemp(), 'keys.json')
    a = KeyMap(path=path)
    a.set_binding('lane3', ('page up',))
    b = KeyMap(path=path)
    assert b.bindings['lane3'] == [('page up',)]
    b.reset()
    c = KeyMap(path=path)
    assert c.bindings['lane3'] == DEFAULTS['lane3'], 'reset did not stick'


# ----------------------------------------------------------- binding screen
class _Recorder:
    def __init__(self):
        self.said = []

    def speak(self, text, interrupt=True):
        self.said.append(text)
        return True

    def stop(self):
        pass


def _screen():
    km = KeyMap(path=os.path.join(tempfile.mkdtemp(), 'keys.json'))
    rec = _Recorder()
    return KeyBindScreen(keymap=km, speech=rec), km, rec


def test_the_screen_reads_itself():
    scr, _km, rec = _screen()
    scr.open()
    assert any('Up and Down' in s for s in rec.said), 'no help was spoken'
    assert any('hard left' in s for s in rec.said), 'the first action was not read'
    rec.said.clear()
    scr.move(1)
    assert rec.said and '10:30' in rec.said[0], 'moving did not read the new action'


def test_the_screen_binds_a_chord():
    scr, km, rec = _screen()
    scr.open()
    scr.index = ACTION_IDS.index('shake')
    scr.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.key.key_code('return'),
                                  mod=0), pygame)
    assert scr.capturing
    for n in ('left ctrl', 'k'):
        scr.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.key.key_code(n),
                                      mod=0), pygame)
    scr.handle(pygame.event.Event(pygame.KEYUP, key=pygame.key.key_code('k'), mod=0),
               pygame)
    assert not scr.capturing
    assert km.bindings['shake'] == [('left ctrl', 'k')], km.bindings['shake']
    assert any('Left Control plus K' in s for s in rec.said)


def _screen_down(scr, name):
    scr.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.key.key_code(name), mod=0),
               pygame)


def _screen_up(scr, name):
    scr.handle(pygame.event.Event(pygame.KEYUP, key=pygame.key.key_code(name), mod=0),
               pygame)


def test_letting_go_of_enter_does_not_end_the_capture():
    """Enter starts the capture, so its own key-up arrives before the player has pressed
    anything.  Ending the capture there answered "Nothing pressed" every time, which left
    no way to rebind a key at all."""
    scr, km, rec = _screen()
    scr.open()
    scr.index = ACTION_IDS.index('pause')
    _screen_down(scr, 'return')
    _screen_up(scr, 'return')                       # the press that started it, released
    assert scr.capturing, 'letting go of Enter ended the capture'
    assert not any('Nothing pressed' in s for s in rec.said), rec.said
    _screen_down(scr, 'k')
    _screen_up(scr, 'k')
    assert not scr.capturing, 'releasing the captured key did not finish it'
    assert km.bindings['pause'] == [('k',)], km.bindings['pause']


def test_resetting_every_binding_asks_first():
    """R throws away every binding the player has made, and there is no undo, so it asks.
    The second R does it; anything else keeps them."""
    scr, km, rec = _screen()
    scr.open()
    km.set_binding('pause', ('k',))
    assert km.bindings['pause'] == [('k',)]

    _screen_down(scr, 'r')
    assert km.bindings['pause'] == [('k',)], 'one R reset the bindings'
    assert any('Press R again' in s for s in rec.said), rec.said
    rec.said.clear()

    _screen_down(scr, 'w')                          # any other key keeps them
    assert km.bindings['pause'] == [('k',)], 'a key that is not R still reset them'
    assert any('kept' in s for s in rec.said), rec.said
    assert not scr.confirm_reset

    _screen_down(scr, 'r')
    _screen_down(scr, 'r')
    assert km.bindings['pause'] == list(DEFAULTS['pause']), km.bindings['pause']
    assert any('back to the default' in s for s in rec.said), rec.said


def test_the_screen_refuses_to_bind_the_way_out():
    scr, km, rec = _screen()
    scr.open()
    scr.index = ACTION_IDS.index('lane1')
    before = list(km.bindings['lane1'])
    scr.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.key.key_code('return'),
                                  mod=0), pygame)
    scr.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.key.key_code('f1'),
                                  mod=0), pygame)
    scr.handle(pygame.event.Event(pygame.KEYUP, key=pygame.key.key_code('f1'), mod=0),
               pygame)
    assert km.bindings['lane1'] == before, 'F1 got bound'
    assert any('cannot be rebound' in s for s in rec.said)


def test_escape_leaves_the_screen():
    scr, _km, _rec = _screen()
    scr.open()
    assert not scr.done
    scr.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.key.key_code('escape'),
                                  mod=0), pygame)
    assert scr.done


def test_the_debug_keys_are_live_only_with_debug():
    """--debug adds the debug_ actions to the keymap and the F1 screen; without it
    F5 does nothing and the screen does not list them."""
    st, inp = _stage()
    said = []
    st._say = said.append                   # never the real screen reader
    try:
        scr = KeyBindScreen(keymap=inp.keymap, speech=_Recorder())
        assert not any(a.startswith('debug_') for a in inp.keymap.actions)
        assert not any('Debug' in s for s in scr.render_lines())
        _fire(inp, 'f5')
        assert st.MonsterBuffer == [], 'F5 spawned without --debug'

        inp.keymap.debug = True
        assert any('Debug: spawn a zombie' in s for s in scr.render_lines())
        _fire(inp, 'd')                     # attack 3 o'clock, so F5 spawns there
        _fire(inp, 'f5')
        assert len(st.MonsterBuffer) == 1, 'F5 did not spawn'
        assert st.MonsterBuffer[0].MovingType == 5, 'not in the lane last attacked'
        assert said[-1] == "Zombie 1, 3 o'clock.", said
        _fire(inp, 'left shift', 'f5')
        assert said[-1] == 'Zombie 2', said
        _fire(inp, 'f2')                    # F2 is the next section...
        assert said[-1] == 'Section 2 of 8.', said
        _fire(inp, 'left shift', 'f2')      # ...and Shift+F2 the next level
        assert said[-1].startswith('Level 2, '), said
    finally:
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
