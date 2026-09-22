"""The opening screen: the splash, the welcome message and the earphone reminder.

Shortens WELCOME_SECONDS so the whole run fits in a test; nothing else is changed.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sixthsense.game import intro as I                            # noqa: E402
from sixthsense.game.app_delegate import AppDelegate              # noqa: E402
from sixthsense.game.intro import StartIntroPage                  # noqa: E402
from sixthsense.platform.runloop import RunLoop                   # noqa: E402

_REAL_WELCOME_SECONDS = I.WELCOME_SECONDS


def _page(welcome=0.3):
    """The intro past its splash, with a short wait before the earphone reminder."""
    I.WELCOME_SECONDS = welcome
    app = AppDelegate.shared()
    if app.playback is None:
        app.didFinishLaunching()
    RunLoop.main().reset()
    page = StartIntroPage()
    page.startIntro1()                     # skip the splash delay directly
    return page


def _restore():
    I.WELCOME_SECONDS = _REAL_WELCOME_SECONDS


def _pump(loop, seconds, until=None):
    t0 = time.monotonic()
    while time.monotonic() - t0 < seconds:
        loop.pump()
        if until is not None and until():
            return True
        time.sleep(0.004)
    return False


def _spy(app):
    played = []
    real_play = app.playSound_Gain_Pos_z_reprats_
    app.playSound_Gain_Pos_z_reprats_ = \
        lambda num, *a, **k: (played.append(num), real_play(num, *a, **k))[-1]
    return played, real_play


def test_the_earphone_reminder_waits_for_the_welcome_message():
    """PORT ADDITION: the original never plays 234 here at all - it only plays it
    from MainController's StartGameAction:, which used to collide with the
    menu's own title read every time the menu came up. Saying it once, after
    the welcome message, keeps the reminder without that collision."""
    page = _page(welcome=0.3)
    app = page.app
    played, real_play = _spy(app)
    try:
        assert 234 not in played, 'the earphone reminder started too early'
        got = _pump(RunLoop.main(), 1.0, until=lambda: 234 in played)
        assert got, 'the earphone reminder never played'
    finally:
        app.playSound_Gain_Pos_z_reprats_ = real_play
        page.teardown()
        _restore()


def test_skipping_the_intro_cancels_the_earphone_reminder():
    """A player who skips never hears it, the same way skipping cuts off the
    welcome message itself."""
    page = _page(welcome=0.3)
    app = page.app
    played, real_play = _spy(app)
    try:
        page.skipAction()
        _pump(RunLoop.main(), 1.0)
        assert 234 not in played, 'the earphone reminder played after skipping'
    finally:
        app.playSound_Gain_Pos_z_reprats_ = real_play
        page.teardown()
        _restore()


def test_skipping_after_it_already_started_stops_it():
    page = _page(welcome=0.2)
    app = page.app
    try:
        got = _pump(RunLoop.main(), 1.0, until=lambda: app.CheckSoundBuf_(234) != -1)
        assert got, 'the earphone reminder never started playing'
        i = app.CheckSoundBuf_(234)
        assert app.aSoundBufControlData[i].bIsPlaying
        page.skipAction()
        assert not app.aSoundBufControlData[i].bIsPlaying, \
            'the earphone reminder kept playing after skipping'
    finally:
        page.teardown()
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
