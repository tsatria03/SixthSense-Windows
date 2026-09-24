"""The music and the ambience do not leak memory as they change.

Each file the two players load is 2 to 3 MB, and a level change swaps both, so a buffer
that is never freed shows at once: on 2026-09-23, with the freeing switched off, 200
swaps grew the process by over a gigabyte, while the game as it is stayed flat after
the first two files.  This swaps both players 20 times, cave and forest in turn, and
checks the process's private memory stays where it was after the first swaps.

It opens the audio device, so run it with OpenAL's null driver, and it writes the save
through ``didFinishLaunching``: see the safe way to run the tests.  Windows only.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import gc
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import _scratch_save                                             # noqa: E402,F401  never the real save

from sixthsense.game.app_delegate import AppDelegate             # noqa: E402

PAIRS = [('bgm_forest', 'bgm_cave_amb'), ('bgm_cave', 'bgm_forest_amb')]
SWAPS = 20
#: well under one leaked file, 2 to 3 MB, and far under 20 swaps' worth
ALLOWED_GROWTH_MB = 2.0


class _Counters(ctypes.Structure):
    _fields_ = [('cb', wt.DWORD), ('PageFaultCount', wt.DWORD),
                ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t),
                ('PrivateUsage', ctypes.c_size_t)]


def _private_mb():
    """The process's private memory, what Task Manager calls its commit size."""
    k32 = ctypes.WinDLL('kernel32')
    psapi = ctypes.WinDLL('psapi')
    k32.GetCurrentProcess.restype = wt.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(_Counters), wt.DWORD]
    c = _Counters()
    c.cb = ctypes.sizeof(c)
    psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return c.PrivateUsage / 1048576


def _swap(pb, i):
    bg, amb = PAIRS[i % 2]
    pb.startBGPlayer_type_soundGain_Loop_(bg, 'wav', 0.02, True)
    pb.startAMBPlayer_type_soundGain_Loop_(amb, 'wav', 0.2, True)


def test_changing_the_music_and_the_ambience_does_not_leak():
    app = AppDelegate.shared()
    if app.playback is None:
        app.didFinishLaunching()
    pb = app.playback
    try:
        for i in range(2):                      # both players now hold a file each
            _swap(pb, i)
        gc.collect()
        before = _private_mb()
        for i in range(SWAPS):
            _swap(pb, i)
        gc.collect()
        grown = _private_mb() - before
        assert grown < ALLOWED_GROWTH_MB, \
            'memory grew %.1f MB over %d swaps: the old files are not freed' % (grown, SWAPS)
    finally:
        pb.backgroundSoundStop()
        pb.AMBSoundStop()


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
