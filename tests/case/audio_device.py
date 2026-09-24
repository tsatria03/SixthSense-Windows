"""A lost audio device is reopened on the default output: ``AL.check_device``.

The fake-device tests stand in for OpenAL's two extensions, so they check the logic
without any device.  The last one opens the real OpenAL Soft on its null driver and
calls the real ``alcReopenDeviceSOFT``, to check the ctypes wiring.  Unplugging real
headphones is left to the dev's ears.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault('ALSOFT_DRIVERS', 'null')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import _scratch_save                                             # noqa: E402,F401  never the real save

from sixthsense.platform import openal                          # noqa: E402


class _FakeAL(openal.AL):
    """An AL with a pretend device: no library, no sound."""

    def __init__(self, connected=True, can_check=True, can_reopen=True, reopens=True):
        self.device = 1
        self.is_connected = connected
        self._can_check = can_check
        self._attrs = 'the open attributes'
        self._sources = set()
        self._loops = []
        self.default_changed = False
        self.reopened = []
        self.state = {}                 # source -> 'playing', 'paused' or 'stopped'
        self.looping = {}

        def reopen(device, name, attrs):
            self.reopened.append((device, name, attrs))
            if reopens:
                self.is_connected = True
            return 1 if reopens else 0
        self._reopen = reopen if can_reopen else None

    def add(self, sid, state, looping):
        self._sources.add(sid)
        self.state[sid] = state
        self.looping[sid] = looping

    def unplug(self):
        """What a lost device does: every source stops."""
        self.is_connected = False
        for sid in self.state:
            self.state[sid] = 'stopped'

    def alcGetIntegerv(self, device, param, size, out):
        assert param == openal.ALC_CONNECTED
        out._obj.value = 1 if self.is_connected else 0

    def source_state(self, sid):
        return {'playing': openal.AL_PLAYING}.get(self.state[sid], 0)

    def alGetSourcei(self, sid, param, out):
        assert param == openal.AL_LOOPING
        out._obj.value = 1 if self.looping[sid] else 0

    def alSourcePlay(self, sid):
        self.state[sid] = 'playing'


def test_a_connected_device_is_left_alone():
    a = _FakeAL(connected=True)
    assert a.check_device() is False
    assert a.reopened == []


def test_a_lost_device_is_reopened_on_the_default_output_with_the_same_settings():
    a = _FakeAL(connected=False)
    assert a.check_device() is True
    assert a.reopened == [(1, None, 'the open attributes')], a.reopened
    assert a.connected()
    assert a.check_device() is False, 'reopened again once it was back'


def test_a_failed_reopen_is_tried_again_next_time():
    a = _FakeAL(connected=False, reopens=False)
    assert a.check_device() is False
    assert a.check_device() is False
    assert len(a.reopened) == 2


def test_without_the_extensions_nothing_is_touched():
    a = _FakeAL(connected=False, can_check=False)
    assert a.connected() is True, 'no way to ask, so it counts as connected'
    assert a.check_device() is False and a.reopened == []
    b = _FakeAL(connected=False, can_reopen=False)
    assert b.check_device() is False


def test_a_changed_default_moves_a_device_that_is_still_connected():
    """Headphones plugged back in: the speakers stay connected, so only OpenAL's
    default-changed event can say it is time to move."""
    a = _FakeAL(connected=True)
    a.default_changed = True
    assert a.check_device() is True
    assert len(a.reopened) == 1
    assert a.default_changed is False
    assert a.check_device() is False, 'moved again with nothing changed'


def test_the_loops_that_were_playing_start_again_after_a_loss():
    a = _FakeAL()
    a.add(1, 'playing', looping=True)       # the menu music
    a.add(2, 'playing', looping=False)      # a gunshot
    a.add(3, 'paused', looping=True)        # music paused with the game
    a.add(4, 'stopped', looping=True)
    assert a.check_device() is False        # a healthy check notes what is looping
    a.unplug()
    assert a.check_device() is True
    assert a.state == {1: 'playing', 2: 'stopped', 3: 'stopped', 4: 'stopped'}, a.state


def test_a_deleted_source_is_not_started_again():
    a = _FakeAL()
    a.add(1, 'playing', looping=True)
    a.check_device()
    a._sources.discard(1)
    a.unplug()
    a.check_device()
    assert a.state[1] == 'stopped'


def test_the_real_library_can_check_and_reopen():
    a = openal.AL()
    a.open()
    try:
        assert a._can_check, 'ALC_EXT_disconnect is missing'
        assert a._reopen is not None, 'ALC_SOFT_reopen_device is missing'
        assert a.connected()
        assert a.check_device() is False
        assert a.reopen() is True, 'alcReopenDeviceSOFT failed'
        assert a.connected()
        assert a.alcGetError(a.device) == 0
    finally:
        a.close()


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
