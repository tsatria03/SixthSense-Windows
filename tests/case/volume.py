"""The volume knobs: decibels in, gains out, and the binary's own mix left alone."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import _scratch_save                                             # noqa: E402,F401  never the real save

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


# ---- the volume settings in settings.json (tsatria03, 2026-09-25) ---------------------------

class _Defaults:
    """Just the part of UserDefaults ``volume.load`` uses."""

    def __init__(self, **keys):
        self.d = dict(keys)

    def objectForKey_(self, key):
        return self.d.get(key)

    def setInteger_forKey_(self, value, key):
        self.d[key] = int(value)


def _loaded(**keys):
    saved = dict(volume.percents)
    defaults = _Defaults(**keys)
    wrote = volume.load(defaults)
    return defaults, wrote, saved


def test_every_volume_at_100_is_the_original_mix():
    defaults, wrote, saved = _loaded()
    try:
        assert wrote, 'the defaults were not written'
        assert defaults.d == {k: 100 for k in volume.VOLUME_KEYS}, defaults.d
        assert volume.master(1.0) == 1.0 and volume.master(0.2) == 0.2
        assert volume.music(0.02) == 0.02
        assert volume.ambience(0.2) == 0.2 and volume.ambience(0.5) == 0.5
        assert volume.menu_music(100) == volume.gain(volume.MENU_MUSIC_DB)
    finally:
        volume.percents.update(saved)


def test_each_volume_moves_only_its_own_group():
    defaults, wrote, saved = _loaded(MASTERVOLUME=100, MENUMUSICVOLUME=100,
                                     LEVELMUSICVOLUME=50, AMBIENCEVOLUME=0)
    try:
        assert not wrote, 'a complete file was written again'
        assert abs(volume.music(0.02) - 0.005) < 1e-12, 'half is not a quarter of the gain'
        assert volume.ambience(0.2) == 0.0 and volume.ambience(0.5) == 0.0
        assert volume.master(1.0) == 1.0, 'the level music setting moved everything'
    finally:
        volume.percents.update(saved)
    defaults, wrote, saved = _loaded(MASTERVOLUME=50, MENUMUSICVOLUME=100,
                                     LEVELMUSICVOLUME=100, AMBIENCEVOLUME=100)
    try:
        assert volume.master(1.0) == 0.25
        assert volume.music(0.02) == 0.02, 'the master volume is applied twice'
    finally:
        volume.percents.update(saved)


def test_a_bad_value_counts_as_100_and_is_kept_as_written():
    """A player's own value is never written over, even a bad one; it just counts as 100."""
    defaults, wrote, saved = _loaded(MASTERVOLUME='loud', MENUMUSICVOLUME=100,
                                     LEVELMUSICVOLUME=250, AMBIENCEVOLUME='40')
    try:
        assert volume.percents['MASTERVOLUME'] == 100
        assert volume.percents['LEVELMUSICVOLUME'] == 100
        assert volume.percents['AMBIENCEVOLUME'] == 40
        assert defaults.d['MASTERVOLUME'] == 'loud', 'the player\'s value was replaced'
    finally:
        volume.percents.update(saved)
    for bad in ('loud', 5.5, -1, 101, True, None, [50]):
        assert volume.percent(bad) == 100, bad
    for good, want in ((0, 0), (100, 100), ('7', 7), (60.0, 60)):
        assert volume.percent(good) == want, good


def test_a_missing_volume_is_added_and_the_rest_kept():
    defaults, wrote, saved = _loaded(MASTERVOLUME=30)
    try:
        assert wrote
        assert defaults.d['MASTERVOLUME'] == 30, 'the player\'s value was replaced'
        assert defaults.d['AMBIENCEVOLUME'] == 100
    finally:
        volume.percents.update(saved)


def test_settings_json_lists_them_in_the_devs_order():
    from sixthsense.platform.defaults import SETTINGS_KEYS
    assert SETTINGS_KEYS == ('MASTERVOLUME', 'MENUMUSICVOLUME', 'LEVELMUSICVOLUME',
                             'AMBIENCEVOLUME', 'EYEMODE')


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
