"""Measure what the five lanes actually pan to.

Renders one mono source per lane through OpenAL Soft's loopback device, with the same
listener orientation and the same source parameters ``-[oalPlayback queueNote:...]``
passes, and prints the left/right energy split and the resulting gain.

This is how the claim in aidocks/GAME_STRUCTURE.md about the listener basis was checked:
the game's ``Pos.x`` becomes left/right, its ``Pos.y`` becomes elevation (inaudible to
amplitude panning), and the forward distance is the constant ``defaultZ``.

    python tools/pan_check.py
"""
from __future__ import annotations

import ctypes
import math
import os
import sys
from ctypes import POINTER, byref, c_char_p, c_float, c_int, c_uint, c_void_p

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sixthsense.platform import openal as al          # noqa: E402

# ALC_SOFT_loopback
ALC_FORMAT_CHANNELS_SOFT = 0x1990
ALC_FORMAT_TYPE_SOFT = 0x1991
ALC_STEREO_SOFT = 0x1501
ALC_FLOAT_SOFT = 0x1406
ALC_FREQUENCY = 0x1007

RATE = 44100
FRAMES = 4096

# -[MonsterControl initWithMonsterPatern:...] 0x10b7a - where each lane comes in.
LANES = {
    1: ('WZ  west,  hard left', (-1000.0, 0.0)),
    2: ('WNZ half left       ', (-500.0, 866.0)),
    3: ('NZ  straight ahead  ', (0.0, 1000.0)),
    4: ('ENZ half right      ', (500.0, 866.0)),
    5: ('EZ  east,  hard right', (1000.0, 0.0)),
}


def main():
    lib = al.AL()
    L = lib.lib
    if not lib.alcIsExtensionPresent(None, b'ALC_SOFT_loopback'):
        print('ALC_SOFT_loopback is not available in this OpenAL Soft build.')
        return 1

    # the binding does not declare alcGetProcAddress; ctypes would truncate the
    # returned pointer to an int on 64-bit without these
    L.alcGetProcAddress.restype = c_void_p
    L.alcGetProcAddress.argtypes = [c_void_p, c_char_p]

    addr = L.alcGetProcAddress(None, b'alcLoopbackOpenDeviceSOFT')
    open_loopback = ctypes.CFUNCTYPE(c_void_p, c_char_p)(addr)
    addr = L.alcGetProcAddress(None, b'alcRenderSamplesSOFT')
    render = ctypes.CFUNCTYPE(None, c_void_p, c_void_p, c_int)(addr)

    dev = open_loopback(None)
    attrs = (c_int * 9)(ALC_FORMAT_CHANNELS_SOFT, ALC_STEREO_SOFT,
                        ALC_FORMAT_TYPE_SOFT, ALC_FLOAT_SOFT,
                        ALC_FREQUENCY, RATE,
                        al.ALC_HRTF_SOFT, al.ALC_FALSE,      # as the port opens it
                        0)
    ctx = lib.alcCreateContext(dev, attrs)
    lib.alcMakeContextCurrent(ctx)
    lib.alDistanceModel(al.AL_INVERSE_DISTANCE_CLAMPED)

    # a mono buffer of steady tone, so the only thing that varies is the panning
    n = RATE // 4
    pcm = (ctypes.c_short * n)()
    for i in range(n):
        pcm[i] = int(20000 * math.sin(2 * math.pi * 440.0 * i / RATE))
    buf = lib.gen_buffer()
    lib.alBufferData(buf, al.AL_FORMAT_MONO16, ctypes.byref(pcm),
                     ctypes.sizeof(pcm), RATE)

    # -[oalPlayback setListenerRotation:] 0xe890, facing 0
    a = 0.0 + math.pi / 2.0
    lib.listener_fv(al.AL_ORIENTATION, (math.cos(a), math.sin(a), 0.0, 0.0, 1.0, 1.0))
    lib.alListener3f(al.AL_POSITION, 0.0, 0.0, 0.0)

    out = (c_float * (FRAMES * 2))()
    print('listener facing 0 deg, AL_POSITION = (Pos.x, defaultZ, Pos.y), defaultZ = 40')
    print('MonsterQueueNote parameters: ref 100, max 1600, gain 1.0\n')
    print('lane  where                    Pos            L      R    L/R dB   total')
    for lane, (label, pos) in LANES.items():
        src = lib.gen_source()
        lib.alSourcei(src, al.AL_BUFFER, buf)
        lib.alSourcei(src, al.AL_LOOPING, 1)
        lib.alSourcef(src, al.AL_REFERENCE_DISTANCE, 100.0)
        lib.alSourcef(src, al.AL_MAX_DISTANCE, 1600.0)
        lib.alSourcef(src, al.AL_GAIN, 1.0)
        lib.source_fv(src, al.AL_POSITION, (pos[0], 40.0, pos[1]))
        lib.alSourcePlay(src)
        render(dev, byref(out), FRAMES)
        left = math.sqrt(sum(out[i] ** 2 for i in range(0, FRAMES * 2, 2)) / FRAMES)
        right = math.sqrt(sum(out[i] ** 2 for i in range(1, FRAMES * 2, 2)) / FRAMES)
        db = 20 * math.log10((left + 1e-9) / (right + 1e-9))
        total = math.sqrt(left ** 2 + right ** 2)
        print('  %d   %-22s (%6.0f,%5.0f)  %.3f  %.3f  %+6.1f   %.3f'
              % (lane, label, pos[0], pos[1], left, right, db, total))
        lib.alSourceStop(src)
        lib.delete_source(src)

    lib.alcMakeContextCurrent(None)
    lib.alcDestroyContext(ctx)
    lib.alcCloseDevice(dev)
    return 0


if __name__ == '__main__':
    sys.exit(main())
