"""The opening screen: the splash, the welcome message and the earphone reminder.

Shortens WELCOME_SECONDS so the whole run fits in a test; nothing else is changed.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

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


def _earphone_playing(app):
    """234's slot outlives the test that played it, so its being there says nothing."""
    i = app.CheckSoundBuf_(234)
    return i != -1 and app.aSoundBufControlData[i].bIsPlaying


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
        got = _pump(RunLoop.main(), 1.0, until=lambda: _earphone_playing(app))
        assert got, 'the earphone reminder never started playing'
        i = app.CheckSoundBuf_(234)
        page.skipAction()
        assert not app.aSoundBufControlData[i].bIsPlaying, \
            'the earphone reminder kept playing after skipping'
    finally:
        page.teardown()
        _restore()



def test_moving_off_the_welcome_row_cancels_the_earphone_reminder():
    """Row 2 never hears the reminder, and coming back to row 1 reads the welcome
    message alone, since it already says to use earphones."""
    page = _page(welcome=0.3)
    app = page.app
    played, real_play = _spy(app)
    try:
        page.move(1)
        _pump(RunLoop.main(), 0.6)
        assert 234 not in played, 'the earphone reminder played over row 2'
        page.move(-1)
        assert page.selectMenu == 1
        assert 14 in played, 'coming back to row 1 did not read the welcome message'
        _pump(RunLoop.main(), 0.6)
        assert 234 not in played, 'the earphone reminder followed the reread welcome'
    finally:
        app.playSound_Gain_Pos_z_reprats_ = real_play
        page.teardown()
        _restore()


def test_moving_rows_after_it_already_started_stops_it():
    page = _page(welcome=0.2)
    app = page.app
    try:
        got = _pump(RunLoop.main(), 1.0, until=lambda: _earphone_playing(app))
        assert got, 'the earphone reminder never started playing'
        i = app.CheckSoundBuf_(234)
        page.move(1)
        assert not app.aSoundBufControlData[i].bIsPlaying, \
            'the earphone reminder kept playing over row 2'
    finally:
        page.teardown()
        _restore()

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


def _launch(delay=0.1, logo=0.2, splash=0.2, welcome=5.0):
    """The screen from its very start, the logo first, with the waits shortened."""
    I.LOGO_DELAY, I.LOGO_SECONDS = delay, logo
    I.SPLASH_SECONDS, I.WELCOME_SECONDS = splash, welcome
    app = AppDelegate.shared()
    if app.playback is None:
        app.didFinishLaunching()
    RunLoop.main().reset()
    return StartIntroPage(), app


_REAL = (I.LOGO_DELAY, I.LOGO_SECONDS, I.SPLASH_SECONDS)


def _restore_launch():
    I.LOGO_DELAY, I.LOGO_SECONDS, I.SPLASH_SECONDS = _REAL
    _restore()


def test_the_logo_sound_waits_a_moment_and_the_welcome_waits_for_it():
    """-[AppDelegate application:didFinishLaunchingWithOptions:] plays 340, bitbee_1,
    at 0.2 as it launches (0x4502), and the opening screen comes 2.5 + 1.0 s later
    (0x459a, 0x49da).  The port waits LOGO_DELAY first, so the logo does not start
    the instant the game opens.  The splash then waits 2 s before the welcome."""
    assert _REAL[1] == 3.5 and I.SOUND_LOGO == 340
    assert 0.5 <= _REAL[0] <= 1.0, 'the wait before the logo is %r' % _REAL[0]
    page, app = _launch()
    played, real_play = _spy(app)
    try:
        page.viewDidLoad()
        assert played == [], 'something played the instant the game opened: %r' % played
        got = _pump(RunLoop.main(), 1.0, until=lambda: 340 in played)
        assert got and played[0] == 340, 'the logo did not come first: %r' % played
        assert 14 not in played, 'the welcome came during the logo'
        got = _pump(RunLoop.main(), 1.5, until=lambda: 14 in played)
        assert got, 'the welcome never came after the logo and the splash'
        assert not page.logo and not page.splash
    finally:
        app.playSound_Gain_Pos_z_reprats_ = real_play
        page.teardown()
        _restore_launch()


def test_enter_skips_the_logo_to_the_opening_screen():
    """PORT ADDITION: Enter during the logo stops it and brings the opening screen at
    once, whose welcome follows its splash as usual."""
    from sixthsense.ui.screen_input import ScreenInput
    page, app = _launch(logo=5.0)
    played, real_play = _spy(app)
    try:
        page.viewDidLoad()
        _pump(RunLoop.main(), 1.0, until=lambda: 340 in played)
        i = app.CheckSoundBuf_(340)
        ScreenInput(page).handle(_Key('return'), _Pygame)
        assert not page.logo, 'Enter did not skip the logo'
        assert page.next_screen is None, 'Enter left the opening screen'
        assert not app.aSoundBufControlData[i].bIsPlaying, 'the logo sound kept playing'
        got = _pump(RunLoop.main(), 1.0, until=lambda: 14 in played)
        assert got, 'the welcome did not follow the skipped logo'
    finally:
        app.playSound_Gain_Pos_z_reprats_ = real_play
        page.teardown()
        _restore_launch()


def test_enter_in_the_quiet_before_the_logo_skips_it_too():
    from sixthsense.ui.screen_input import ScreenInput
    page, app = _launch(delay=5.0)
    played, real_play = _spy(app)
    try:
        page.viewDidLoad()
        ScreenInput(page).handle(_Key('return'), _Pygame)
        _pump(RunLoop.main(), 0.6)
        assert 340 not in played, 'the logo played after it was skipped'
        assert not page.logo
    finally:
        app.playSound_Gain_Pos_z_reprats_ = real_play
        page.teardown()
        _restore_launch()


def test_escape_during_the_logo_skips_to_the_menu():
    from sixthsense.ui.screen_input import ScreenInput
    page, app = _launch(logo=5.0)
    played, real_play = _spy(app)
    try:
        page.viewDidLoad()
        _pump(RunLoop.main(), 1.0, until=lambda: 340 in played)
        i = app.CheckSoundBuf_(340)
        ScreenInput(page).handle(_Key('escape'), _Pygame)
        assert page.next_screen == 'menu'
        assert not app.aSoundBufControlData[i].bIsPlaying, 'the logo sound kept playing'
        _pump(RunLoop.main(), 0.8)
        assert 14 not in played, 'the welcome came after skipping to the menu'
    finally:
        app.playSound_Gain_Pos_z_reprats_ = real_play
        page.teardown()
        _restore_launch()


def test_up_and_down_do_nothing_during_the_logo():
    page, app = _launch(logo=5.0)
    played, real_play = _spy(app)
    try:
        page.viewDidLoad()
        assert page.move(1) is None and page.jump(last=True) is None
        assert 14 not in played and 266 not in played, 'a row was read: %r' % played
    finally:
        app.playSound_Gain_Pos_z_reprats_ = real_play
        page.teardown()
        _restore_launch()


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
