"""ctypes binding for the OpenAL calls ``oalPlayback`` makes.

The original links ``/System/Library/Frameworks/OpenAL.framework`` and drives it directly
(``alGenBuffers``/``alBufferData``/``alSourcei``/``alSourcefv``/``alListenerfv``), so this
port keeps the same API and passes the same enums and the same values; OpenAL Soft does
the mixing.  Only the entry points ``oalPlayback`` uses are bound.

HRTF is explicitly **off** - see ``AL.open``.  The original is not a 3D audio game in
the binaural sense: it is stereo panning plus distance attenuation, which is all iOS's
OpenAL does for plain core AL calls.
"""
from __future__ import annotations

import atexit
import ctypes
import logging
import os
from ctypes import POINTER, byref, c_char_p, c_float, c_int, c_uint, c_void_p

from .. import paths

log = logging.getLogger('openal')

# --- core AL enums (the ones the original passes) ---------------------------
AL_NONE = 0
AL_SOURCE_RELATIVE = 0x0202
AL_CONE_INNER_ANGLE = 0x1001
AL_CONE_OUTER_ANGLE = 0x1002
AL_PITCH = 0x1003
AL_POSITION = 0x1004
AL_DIRECTION = 0x1005
AL_VELOCITY = 0x1006
AL_LOOPING = 0x1007
AL_BUFFER = 0x1009
AL_GAIN = 0x100A
AL_ORIENTATION = 0x100F
AL_SOURCE_STATE = 0x1010
AL_INITIAL = 0x1011
AL_PLAYING = 0x1012
AL_PAUSED = 0x1013
AL_STOPPED = 0x1014
AL_REFERENCE_DISTANCE = 0x1020
AL_ROLLOFF_FACTOR = 0x1021
AL_MAX_DISTANCE = 0x1023
AL_SEC_OFFSET = 0x1024
AL_FORMAT_MONO8 = 0x1100
AL_FORMAT_MONO16 = 0x1101
AL_FORMAT_STEREO8 = 0x1102
AL_FORMAT_STEREO16 = 0x1103
AL_NO_ERROR = 0
AL_DISTANCE_MODEL = 0xD000
AL_INVERSE_DISTANCE_CLAMPED = 0xD002

ALC_FREQUENCY = 0x1007
ALC_MONO_SOURCES = 0x1010
ALC_STEREO_SOURCES = 0x1011

# ALC_SOFT_HRTF
ALC_HRTF_SOFT = 0x1992
ALC_HRTF_STATUS_SOFT = 0x1993
ALC_HRTF_SPECIFIER_SOFT = 0x1995
ALC_TRUE = 1
ALC_FALSE = 0

# ALC_EXT_disconnect
ALC_CONNECTED = 0x313

# ALC_SOFT_system_events: checked against OpenAL Soft 1.25.1 on WASAPI, where
# alcEventIsSupportedSOFT answers 0x19D9 for all three once the driver has started
ALC_PLAYBACK_DEVICE_SOFT = 0x19D4
ALC_EVENT_TYPE_DEFAULT_DEVICE_CHANGED_SOFT = 0x19D6
ALC_EVENT_SUPPORTED_SOFT = 0x19D9
_EVENT_CALLBACK = ctypes.CFUNCTYPE(None, c_int, c_int, c_void_p, c_int, c_char_p, c_void_p)

AL_ERRORS = {0xA001: 'AL_INVALID_NAME', 0xA002: 'AL_INVALID_ENUM', 0xA003: 'AL_INVALID_VALUE',
             0xA004: 'AL_INVALID_OPERATION', 0xA005: 'AL_OUT_OF_MEMORY'}


class OpenALError(RuntimeError):
    pass


_SIGNATURES = [
    ('alcOpenDevice', c_void_p, [c_char_p]),
    ('alcCloseDevice', c_int, [c_void_p]),
    ('alcCreateContext', c_void_p, [c_void_p, POINTER(c_int)]),
    ('alcMakeContextCurrent', c_int, [c_void_p]),
    ('alcDestroyContext', None, [c_void_p]),
    ('alcProcessContext', None, [c_void_p]),
    ('alcSuspendContext', None, [c_void_p]),
    ('alcGetError', c_int, [c_void_p]),
    ('alcGetString', c_char_p, [c_void_p, c_int]),
    ('alcGetIntegerv', None, [c_void_p, c_int, c_int, POINTER(c_int)]),
    ('alcIsExtensionPresent', c_int, [c_void_p, c_char_p]),
    ('alcGetProcAddress', c_void_p, [c_void_p, c_char_p]),
    ('alGetError', c_int, []),
    ('alGetString', c_char_p, [c_int]),
    ('alDistanceModel', None, [c_int]),
    ('alGenBuffers', None, [c_int, POINTER(c_uint)]),
    ('alDeleteBuffers', None, [c_int, POINTER(c_uint)]),
    ('alBufferData', None, [c_uint, c_int, c_void_p, c_int, c_int]),
    ('alGenSources', None, [c_int, POINTER(c_uint)]),
    ('alDeleteSources', None, [c_int, POINTER(c_uint)]),
    ('alSourcei', None, [c_uint, c_int, c_int]),
    ('alSourcef', None, [c_uint, c_int, c_float]),
    ('alSourcefv', None, [c_uint, c_int, POINTER(c_float)]),
    ('alSource3f', None, [c_uint, c_int, c_float, c_float, c_float]),
    ('alGetSourcei', None, [c_uint, c_int, POINTER(c_int)]),
    ('alGetSourcef', None, [c_uint, c_int, POINTER(c_float)]),
    ('alGetSourcefv', None, [c_uint, c_int, POINTER(c_float)]),
    ('alSourcePlay', None, [c_uint]),
    ('alSourceStop', None, [c_uint]),
    ('alSourcePause', None, [c_uint]),
    ('alSourceRewind', None, [c_uint]),
    ('alListenerf', None, [c_int, c_float]),
    ('alListener3f', None, [c_int, c_float, c_float, c_float]),
    ('alListenerfv', None, [c_int, POINTER(c_float)]),
]


class AL:
    """The loaded library plus one device and context."""

    def __init__(self, dll_path: str | None = None):
        path = dll_path or paths.OPENAL_DLL
        if not os.path.exists(path):
            raise OpenALError('OpenAL Soft not found: %s' % path)
        if hasattr(os, 'add_dll_directory'):
            try:
                os.add_dll_directory(os.path.dirname(os.path.abspath(path)))
            except OSError:
                pass
        self.lib = ctypes.CDLL(path)
        for name, restype, argtypes in _SIGNATURES:
            fn = getattr(self.lib, name)
            fn.restype = restype
            fn.argtypes = argtypes
            setattr(self, name, fn)
        self.device = None
        self.context = None
        self.hrtf = False
        self._attrs = None
        self._can_check = False       # ALC_EXT_disconnect
        self._reopen = None           # alcReopenDeviceSOFT, ALC_SOFT_reopen_device
        self._sources = set()         # every source gen_source made and not yet deleted
        self._loops = []              # the looping sources playing at the last check
        self.default_changed = False  # set from OpenAL's own thread, see _watch_default
        self._event_callback = None
        self._set_event_callback = None

    # ---- device / context -------------------------------------------------
    def open(self) -> None:
        """Open the device the way ``-[oalPlayback setUpOpenAL]`` does.

        **HRTF is switched off deliberately.**  The original imports eighteen OpenAL
        symbols and every one of them is core AL or ALC (``alListenerfv``,
        ``alSourcefv``, ``alSourcef``, ``alSourcePlayv``, ...); it touches none of
        Apple's ``ALC_ASA_*`` spatial extensions, and the only extension string in the
        whole binary is ``alBufferDataStatic``.  iOS's OpenAL renders plain core AL as
        distance attenuation plus amplitude panning - there is no binaural filtering in
        it at all.  Leaving OpenAL Soft's HRTF on its default would let it engage on
        headphones and put the game somewhere the original never was, so it is
        explicitly disabled.
        """
        self.device = self.alcOpenDevice(None)
        if not self.device:
            raise OpenALError('alcOpenDevice failed')
        attrs = [ALC_MONO_SOURCES, 160, ALC_STEREO_SOURCES, 8]
        if self.alcIsExtensionPresent(self.device, b'ALC_SOFT_HRTF'):
            attrs += [ALC_HRTF_SOFT, ALC_FALSE]
        attrs.append(0)
        arr = (c_int * len(attrs))(*attrs)
        self._attrs = arr                                   # kept for reopen
        self.context = self.alcCreateContext(self.device, arr)
        if not self.context:
            raise OpenALError('alcCreateContext failed')
        self.alcMakeContextCurrent(self.context)
        status = c_int(0)
        try:
            self.alcGetIntegerv(self.device, ALC_HRTF_SOFT, 1, byref(status))
            self.hrtf = bool(status.value)
        except Exception:
            self.hrtf = False
        # -[oalPlayback setUpOpenAL] leaves the default model in place; OpenAL's default
        # is AL_INVERSE_DISTANCE_CLAMPED, which is what AL_REFERENCE_DISTANCE 40 /
        # AL_MAX_DISTANCE 800 in -queueNote: were tuned against.
        self.alDistanceModel(AL_INVERSE_DISTANCE_CLAMPED)
        self.alGetError()
        self._can_check = bool(self.alcIsExtensionPresent(self.device, b'ALC_EXT_disconnect'))
        if self.alcIsExtensionPresent(self.device, b'ALC_SOFT_reopen_device'):
            addr = self.alcGetProcAddress(self.device, b'alcReopenDeviceSOFT')
            if addr:
                self._reopen = ctypes.CFUNCTYPE(ctypes.c_byte, c_void_p, c_char_p,
                                                POINTER(c_int))(addr)
        self._watch_default()

    def _watch_default(self) -> None:
        """Ask OpenAL to say when Windows' default output changes, such as headphones
        plugged back in, which leaves the old device connected and so is not a loss.
        The callback runs on OpenAL's own thread, so it only raises a flag."""
        if not self.alcIsExtensionPresent(self.device, b'ALC_SOFT_system_events'):
            return
        get = self.alcGetProcAddress
        supported = get(None, b'alcEventIsSupportedSOFT')
        control = get(None, b'alcEventControlSOFT')
        callback = get(None, b'alcEventCallbackSOFT')
        if not (supported and control and callback):
            return
        supported = ctypes.CFUNCTYPE(c_int, c_int, c_int)(supported)
        if supported(ALC_EVENT_TYPE_DEFAULT_DEVICE_CHANGED_SOFT,
                     ALC_PLAYBACK_DEVICE_SOFT) != ALC_EVENT_SUPPORTED_SOFT:
            return

        def on_event(event, kind, device, length, message, user):
            if (event == ALC_EVENT_TYPE_DEFAULT_DEVICE_CHANGED_SOFT
                    and kind == ALC_PLAYBACK_DEVICE_SOFT):
                self.default_changed = True

        self._event_callback = _EVENT_CALLBACK(on_event)      # kept alive while set
        self._set_event_callback = ctypes.CFUNCTYPE(None, _EVENT_CALLBACK, c_void_p)(callback)
        self._set_event_callback(self._event_callback, None)
        events = (c_int * 1)(ALC_EVENT_TYPE_DEFAULT_DEVICE_CHANGED_SOFT)
        ctypes.CFUNCTYPE(ctypes.c_byte, c_int, POINTER(c_int), ctypes.c_byte)(control)(
            1, events, 1)
        # OpenAL is never closed on exit, so let go of the callback before Python stops
        atexit.register(self._unwatch_default)

    def _unwatch_default(self) -> None:
        if self._set_event_callback is not None:
            self._set_event_callback(_EVENT_CALLBACK(), None)
            self._set_event_callback = None

    # ---- a lost device ----------------------------------------------------
    def connected(self) -> bool:
        """False once the device has gone, such as headphones unplugged."""
        if not self.device or not self._can_check:
            return True
        v = c_int(1)
        self.alcGetIntegerv(self.device, ALC_CONNECTED, 1, byref(v))
        return bool(v.value)

    def reopen(self) -> bool:
        """Move this device onto the current default output, keeping every buffer,
        source and setting, HRTF off included."""
        if not self.device or self._reopen is None:
            return False
        return bool(self._reopen(self.device, None, self._attrs))

    def check_device(self) -> bool:
        """PORT ADDITION: the original rebuilt its audio on coming back to the
        foreground (``-[Stage_1_E audioRestart]`` 0x2c5bc).  Here the device moves to
        the default output as soon as it is lost or Windows' default changes.

        A lost device stops every source, so the loops that were playing at the last
        check - the music, the ambience, the footsteps - are started again; a paused
        one was not playing, so it stays paused.  True if the device moved."""
        moved = self.default_changed
        if self.connected() and not moved:
            self._loops = self._looping_sources()
            return False
        why = 'the default output changed' if moved else 'the audio device was lost'
        if not self.reopen():
            log.warning('%s, and the device could not be reopened', why)
            return False
        self.default_changed = False
        stopped = [s for s in self._loops
                   if s in self._sources and self.source_state(s) != AL_PLAYING]
        for s in stopped:
            self.alSourcePlay(s)
        log.info('%s; reopened on the default output, %d loops started again',
                 why, len(stopped))
        return True

    def _looping_sources(self):
        looping = c_int(0)
        out = []
        for s in self._sources:
            if self.source_state(s) == AL_PLAYING:
                self.alGetSourcei(s, AL_LOOPING, byref(looping))
                if looping.value:
                    out.append(s)
        return out

    def close(self) -> None:
        if self.context:
            self.alcMakeContextCurrent(None)
            self.alcDestroyContext(self.context)
            self.context = None
        if self.device:
            self.alcCloseDevice(self.device)
            self.device = None

    # ---- convenience ------------------------------------------------------
    def gen_buffer(self) -> int:
        b = c_uint(0)
        self.alGenBuffers(1, byref(b))
        return b.value

    def delete_buffer(self, bid: int) -> None:
        if bid:
            b = c_uint(bid)
            self.alDeleteBuffers(1, byref(b))

    def gen_source(self) -> int:
        s = c_uint(0)
        self.alGenSources(1, byref(s))
        self._sources.add(s.value)
        return s.value

    def delete_source(self, sid: int) -> None:
        if sid:
            s = c_uint(sid)
            self.alDeleteSources(1, byref(s))
            self._sources.discard(sid)

    def buffer_data(self, bid: int, fmt: int, pcm: bytes, rate: int) -> None:
        self.alBufferData(bid, fmt, pcm, len(pcm), rate)

    def source_fv(self, sid: int, param: int, values) -> None:
        arr = (c_float * len(values))(*values)
        self.alSourcefv(sid, param, arr)

    def listener_fv(self, param: int, values) -> None:
        arr = (c_float * len(values))(*values)
        self.alListenerfv(param, arr)

    def source_state(self, sid: int) -> int:
        v = c_int(0)
        self.alGetSourcei(sid, AL_SOURCE_STATE, byref(v))
        return v.value

    def source_position(self, sid: int):
        """Not in the original; lets the tests read back where a source really is."""
        v = (c_float * 3)()
        self.alGetSourcefv(sid, AL_POSITION, v)
        return tuple(v)

    def source_float(self, sid: int, param: int) -> float:
        v = c_float(0.0)
        self.alGetSourcef(sid, param, byref(v))
        return v.value

    def check(self, where: str = '') -> None:
        e = self.alGetError()
        if e != AL_NO_ERROR:
            raise OpenALError('%s: %s' % (where, AL_ERRORS.get(e, hex(e))))
