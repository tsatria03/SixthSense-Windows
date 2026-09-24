"""The frame loop in ``SixthSense.main``: closing the window quits from any screen and
tears down every screen stacked underneath, while Escape and the back rows keep
doing what each screen makes them do.

Each test runs the real loop headless (``SDL_VIDEODRIVER=dummy``) and feeds it a
script of events, one step per frame, instead of a keyboard.  Speech is silenced.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import _scratch_save                                             # noqa: E402,F401  never the real save

import pygame                                                    # noqa: E402

import SixthSense                                                # noqa: E402
from sixthsense.game import stage_1_e as S1E                     # noqa: E402
from sixthsense.platform import speech                           # noqa: E402
from sixthsense.platform.defaults import UserDefaults            # noqa: E402
from sixthsense.platform.runloop import RunLoop                  # noqa: E402

speech.Speech.speak = lambda self, text, interrupt=True: False  # never the real reader

#: How many frames a run may take before the test gives up and closes the window.
LIMIT = 200


class Run:
    """One pass of the frame loop, with every screen it builds and tears down."""

    def __init__(self, script):
        self.script = script            # frame -> a callable taking this Run
        self.built = []                 # (kind, screen), in the order they were made
        self.torn = []
        self.frame = 0
        self.frames_run = 0

    def last(self, kind):
        return [s for k, s in self.built if k == kind][-1]

    def count(self, kind):
        return len([1 for k, _s in self.built if k == kind])

    def go(self):
        S1E.LOADING_SECONDS = 0.0
        RunLoop.main().reset()
        real = {n: getattr(SixthSense, n) for n in
                ('_new_menu', '_new_stage', '_new_tutorial', '_new_screen',
                 '_new_test_range')}
        run = self

        def wrap(kind, fn):
            def make(*a):
                screen = fn(*a)
                k = a[0] if kind == 'screen' else kind
                run.built.append((k, screen))
                inner = screen.teardown
                screen.teardown = lambda: (run.torn.append(screen), inner())[1]
                return screen
            return make

        SixthSense._new_menu = wrap('menu', real['_new_menu'])
        SixthSense._new_stage = wrap('stage', real['_new_stage'])
        SixthSense._new_tutorial = wrap('tutorial', real['_new_tutorial'])
        SixthSense._new_screen = wrap('screen', real['_new_screen'])
        SixthSense._new_test_range = wrap('weapon_test', real['_new_test_range'])
        real_get = pygame.event.get

        def get():
            run.frame += 1
            step = run.script.get(run.frame)
            if run.frame > LIMIT:
                return [pygame.event.Event(pygame.QUIT)]
            if step is not None:
                events = step(run)
                if events:
                    return events
            return real_get()

        pygame.event.get = get
        try:
            SixthSense.main(['--no-intro'])
        finally:
            pygame.event.get = real_get
            for n, fn in real.items():
                setattr(SixthSense, n, fn)
        self.frames_run = self.frame
        return self


def key(name):
    return lambda run: [pygame.event.Event(pygame.KEYDOWN,
                                           key=pygame.key.key_code(name), mod=0),
                        pygame.event.Event(pygame.KEYUP,
                                           key=pygame.key.key_code(name), mod=0)]


def close(run):
    return [pygame.event.Event(pygame.QUIT)]


def to(kind, screen_kind, arg=None):
    """Have the newest ``kind`` screen ask for ``screen_kind``, as its row would."""
    def step(run):
        run.last(kind).next_screen = (screen_kind, arg)
    return step


def _save(**keys):
    d = UserDefaults.standardUserDefaults()
    for k, v in keys.items():
        d.setObject_forKey_(v, k)
    d.synchronize()


def test_closing_from_the_shop_quits_and_stops_the_menu_underneath():
    """The menu under the shop used to live on with its coin timer after a second
    menu was built; now closing quits and tears both down."""
    import time
    _save(COIN='2', TUTORIAL='1', COIN_TIMER_START='1',
          COIN_TIMER=time.strftime('%Y-%m-%d %H:%M:%S'))
    run = Run({5: to('menu', 'store'), 15: close}).go()
    assert run.frames_run < LIMIT, 'closing the window did not quit'
    assert run.count('menu') == 1, 'closing built another menu'
    menu = run.last('menu')
    assert menu in run.torn, 'the menu under the shop was never torn down'
    t = menu.coinTimer
    assert not (t is not None and t.isValid()), "the old menu's coin timer runs on"
    assert run.last('store') in run.torn


def test_closing_from_a_stage_quits():
    _save(TUTORIAL='1')
    run = Run({5: to('menu', 'stage'), 15: close}).go()
    assert run.frames_run < LIMIT, 'closing the window did not quit'
    assert run.count('menu') == 1, 'closing went back to the menu'
    assert run.last('stage') in run.torn


def test_closing_from_the_range_tears_down_every_screen():
    run = Run({5: to('menu', 'store'), 10: to('store', 'store_detail', 2),
               15: to('store_detail', 'weapon_test', 4), 25: close}).go()
    assert run.frames_run < LIMIT, 'closing the window did not quit'
    for kind in ('menu', 'store', 'store_detail', 'weapon_test'):
        assert run.last(kind) in run.torn, '%s was left running' % kind


def test_escape_in_the_shop_still_goes_back():
    """Escape is the back button there: the same menu comes back, and Escape on the
    menu then quits, as before."""
    run = Run({5: to('menu', 'store'), 15: key('escape'), 25: key('escape')}).go()
    assert run.frames_run < LIMIT, 'Escape on the menu did not quit'
    assert run.count('menu') == 1, 'going back built a new menu'
    assert run.last('store') in run.torn


def test_escape_in_a_stage_still_pauses():
    _save(TUTORIAL='1')
    seen = {}

    def look(run):
        seen['state'] = run.last('stage').gameState
        seen['running'] = run.last('stage').running
    run = Run({5: to('menu', 'stage'), 15: key('escape'), 20: look, 25: close}).go()
    assert seen == {'state': 1, 'running': True}, seen
    assert run.count('menu') == 1, 'Escape left the stage'


def test_escape_in_the_tutorial_still_goes_to_the_menu():
    run = Run({5: to('menu', 'tutorial'), 15: key('escape'), 25: close}).go()
    assert run.last('tutorial') in run.torn
    assert run.count('menu') == 2, 'Escape did not bring the menu back'
    assert run.frames_run < LIMIT


def test_escape_in_the_range_still_pauses():
    seen = {}

    def look(run):
        seen['state'] = run.last('weapon_test').gameState
    run = Run({5: to('menu', 'store'), 10: to('store', 'store_detail', 2),
               15: to('store_detail', 'weapon_test', 4), 25: key('escape'),
               30: look, 35: close}).go()
    assert seen == {'state': 1}, seen


def test_the_window_lists_every_debug_key():
    """In debug mode the stage's window text names each debug key, F7 included."""
    from types import SimpleNamespace
    from sixthsense.platform.keymap import DEBUG_IDS, KeyMap
    km = KeyMap()
    km.debug = True
    player = SimpleNamespace(useWepon=0, HP=3, playerXplot=20, playerYplot=30,
                             killMonsterCount=0, HeadShotCount=0)
    stage = SimpleNamespace(gameState=0, gamePlayer=player, weaponSource=[None],
                            gameMode=1, LVUP=1, score=0, MonsterBuffer=[],
                            app=SimpleNamespace(debug=True))
    lines = SixthSense._stage_lines(stage, SimpleNamespace(keymap=km))
    debug = [line for line in lines if line.startswith('debug')]
    assert len(debug) == 1, lines
    missing = [a for a in DEBUG_IDS if km.keys_text(a) not in debug[0]]
    assert not missing, 'the debug line leaves out %s: %s' % (missing, debug[0])
    assert debug[0].count('   ') == len(DEBUG_IDS), debug[0]


def _failing_run(error):
    """``SixthSense.run`` with ``main`` raising ``error``; what it would say, and its exit
    code."""
    said = []
    real_main, real_say = SixthSense.main, SixthSense._say_why

    def fail(argv=None):
        raise error
    SixthSense.main, SixthSense._say_why = fail, said.append
    try:
        return said, SixthSense.run()
    finally:
        SixthSense.main, SixthSense._say_why = real_main, real_say


def test_a_failed_start_says_why():
    said, code = _failing_run(OSError('alcOpenDevice failed'))
    assert code == 1
    assert said == ['SixthSense stopped because of an error. OSError: alcOpenDevice failed'], said
    said, code = _failing_run(SystemExit("SixthSense's game data was not found. Tried:\n  x"))
    assert code == 1
    assert said == ["SixthSense's game data was not found. Tried:"], said


def test_a_normal_exit_says_nothing():
    try:
        _failing_run(SystemExit(0))
    except SystemExit as e:
        assert e.code == 0
    else:
        raise AssertionError('a normal exit was taken for a failure')


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
