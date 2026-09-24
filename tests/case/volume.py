"""The volume knobs: decibels in, gains out, and the binary's own mix left alone."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sixthsense.platform import volume                           # noqa: E402


def test_zero_decibels_changes_nothing():
    """0 dB is a gain of exactly 1.0, which is what makes a knob at rest free: every
    value it multiplies comes back bit for bit."""
    assert volume.gain(0.0) == 1.0
    for g in (0.02, 0.2, 0.5, 1.0):
        assert g * volume.gain(0.0) == g


def test_the_decibel_scale_is_the_usual_one():
    """Amplitude decibels: -6 dB is about half, +6 dB about double, -20 dB a tenth."""
    assert abs(volume.gain(-6.0) - 0.5) < 0.01
    assert abs(volume.gain(6.0) - 2.0) < 0.02
    assert abs(volume.gain(-20.0) - 0.1) < 1e-9
    assert abs(volume.gain(-40.0) - 0.01) < 1e-9


def test_decibels_and_gain_are_each_other_backwards():
    for db in (-34.0, -20.0, -14.0, -6.0, 0.0, 6.0):
        assert abs(volume.decibels(volume.gain(db)) - db) < 1e-9
    assert volume.decibels(1.0) == 0.0
    assert volume.decibels(0.0) == float('-inf'), 'silence has no decibel value'


def test_the_knobs_start_at_rest():
    """Shipped, every group knob is 0 dB, so the mix is the binary's: the level music at
    0.02 (0x321d4), the ambience at 0.2 (0x2ddfa), the rain at 0.5 (0x2ddc8), a gunshot
    at 1.0.  Only the menu music, which the original never plays, has a value of its own."""
    assert volume.MASTER_DB == 0.0
    assert volume.MUSIC_DB == 0.0
    assert volume.AMBIENCE_DB == 0.0
    assert volume.master(1.0) == 1.0
    assert volume.music(0.02) == 0.02
    assert volume.ambience(0.2) == 0.2
    assert volume.ambience(0.5) == 0.5


def test_the_menu_music_is_no_louder_than_a_spoken_row():
    """Every row of every menu is read at 0.2, so the music under them may not be louder."""
    assert volume.menu_music() <= 0.2


def test_a_knob_moves_what_it_owns():
    """Turning MUSIC_DB up moves the level music and leaves the ambience where it was."""
    was = volume.MUSIC_DB
    try:
        volume.MUSIC_DB = 6.0
        assert abs(volume.music(0.02) - 0.04) < 0.001, 'six decibels did not double it'
        assert volume.ambience(0.2) == 0.2, 'the music knob moved the ambience'
    finally:
        volume.MUSIC_DB = was


def test_the_master_knob_moves_everything():
    was = volume.MASTER_DB
    try:
        volume.MASTER_DB = -6.0
        assert abs(volume.master(1.0) - 0.5) < 0.01
        assert abs(volume.master(0.02) - 0.01) < 0.001
    finally:
        volume.MASTER_DB = was


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
