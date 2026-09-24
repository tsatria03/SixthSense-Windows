"""Spoken numbers: ``-[AppDelegate TTSNumber:type:]`` (0x5590) and
``-[AppDelegate readNumber:]`` (0x5cbc), which read a number out one digit per
second from the ``zero``..``nine`` WAVs.

``readNumber_`` decrements ``ttsArrayCount`` and indexes ``numberBackUp`` with the
decremented value, so ``numberBackUp`` has to be built least-significant-digit
first for the digits to come out left to right - otherwise a number like 10 is
spoken "zero, one" instead of "one, zero".
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import _scratch_save                                             # noqa: E402,F401  never the real save

from sixthsense.game.app_delegate import AppDelegate               # noqa: E402
from sixthsense.platform.defaults import UserDefaults               # noqa: E402
from sixthsense.platform.runloop import RunLoop                     # noqa: E402


def _app():
    d = UserDefaults.standardUserDefaults()
    # a save already past its first run, so the FIREST grant in
    # didFinishLaunching does not fire and touch unrelated keys
    d.setObject_forKey_('1', 'FIREST')
    d.synchronize()
    app = AppDelegate.shared()
    if app.playback is None:
        app.didFinishLaunching()
    RunLoop.main().reset()
    return app


def _speak(app, number, type_=0):
    """Drive TTSNumber_type_ to completion and return the digit sounds played,
    in the order they were played."""
    played = []
    real = app.playSound_Gain_Pos_z_reprats_

    def _spy(num, *a, **k):
        if isinstance(num, int) and 0 <= num <= 9:
            played.append(num)
        return real(num, *a, **k)

    app.playSound_Gain_Pos_z_reprats_ = _spy
    try:
        app.TTSNumber_type_(number, type_)
        for _ in str(number):
            app.readNumber_(None)
    finally:
        del app.playSound_Gain_Pos_z_reprats_
    return played


def test_digits_are_spoken_most_significant_first():
    app = _app()
    try:
        for number in (0, 1, 7, 9, 10, 20, 42, 100, 102, 160, 999, 12345):
            digits = [int(c) for c in str(number)]
            played = _speak(app, number)
            assert played == digits, \
                '%d was spoken as %r, not %r' % (number, played, digits)
    finally:
        app.readStop()


def test_a_single_digit_number_is_read_once():
    app = _app()
    try:
        played = _speak(app, 5)
        assert played == [5]
        assert app.ttsArrayCount == 0, 'a spare digit was left queued'
    finally:
        app.readStop()


def test_reading_stops_and_clears_state_after_the_last_digit():
    """Once every digit has been read, another tick plays nothing and clears
    numberBackUp, rather than replaying or misreading a stale entry."""
    app = _app()
    try:
        played = _speak(app, 34)
        assert played == [3, 4]
        extra = []
        real = app.playSound_Gain_Pos_z_reprats_

        def _spy(num, *a, **k):
            if isinstance(num, int) and 0 <= num <= 9:
                extra.append(num)
            return real(num, *a, **k)

        app.playSound_Gain_Pos_z_reprats_ = _spy
        try:
            app.readNumber_(None)
        finally:
            del app.playSound_Gain_Pos_z_reprats_
        assert extra == [], 'a digit was spoken after the number finished: %r' % extra
        assert app.numberBackUp == []
    finally:
        app.readStop()


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
