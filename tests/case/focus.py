"""Losing the window's focus is pressing P (ui/focus.py).

The original's ``interruptStop`` calls ``StopPlayAction:`` (0x2c6ce) when the app goes to
the background, which is what P calls here.

Opens the audio device, so it needs OpenAL Soft present.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import _scratch_save                                             # noqa: E402,F401  never the real save

from sixthsense.game import stage_1_e as S1E                    # noqa: E402
from sixthsense.game.app_delegate import AppDelegate            # noqa: E402
from sixthsense.game.stage_1_e import Stage_1_E                 # noqa: E402
from sixthsense.platform.defaults import UserDefaults           # noqa: E402
from sixthsense.platform.runloop import RunLoop                 # noqa: E402
from sixthsense.ui.focus import focus_lost, interrupt_stop      # noqa: E402
from sixthsense.ui.input import Input                           # noqa: E402


def _new_stage():
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
    RunLoop.main().pump()
    return app, st


class _Event:
    def __init__(self, type_):
        self.type = type_


class _Pygame:
    WINDOWFOCUSLOST = 1
    WINDOWFOCUSGAINED = 2


def test_only_losing_focus_counts():
    assert focus_lost(_Event(_Pygame.WINDOWFOCUSLOST), _Pygame)
    assert not focus_lost(_Event(_Pygame.WINDOWFOCUSGAINED), _Pygame)
    assert not focus_lost(_Event(99), _Pygame)


def test_losing_focus_does_what_p_does():
    """The same stop, so the same panel: paused, the clock and the zombies held."""
    _app, by_focus = _new_stage()
    try:
        assert interrupt_stop(by_focus)
        assert by_focus.gameState == 1, 'the pause panel is not up'
        assert by_focus.MotionSamplingTimer is None, 'the clock kept running'
    finally:
        by_focus.teardown()

    _app, by_p = _new_stage()
    try:
        Input(by_p).perform('pause')
        for name in ('gameState', 'bStop', 'walkXFlag', 'brearhFlag', 'selectMenu'):
            assert getattr(by_p, name) == getattr(by_focus, name), \
                '%s differs: P %r, focus %r' % (name, getattr(by_p, name),
                                                getattr(by_focus, name))
    finally:
        by_p.teardown()


def test_losing_focus_pauses_every_time():
    """Continue clears bStop (0x33960), so each time the window loses focus the game
    pauses again, the same as P."""
    _app, st = _new_stage()
    try:
        for _ in range(3):
            assert interrupt_stop(st)
            assert st.gameState == 1, 'the window lost focus and nothing paused'
            st.continueAction_()
            assert st.gameState == 0
    finally:
        st.teardown()


def test_a_screen_without_a_stop_button_ignores_it():
    class Menu:
        pass
    assert not interrupt_stop(Menu())


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
