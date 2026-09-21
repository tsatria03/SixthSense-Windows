"""``oalPlayback`` - the OpenAL layer.  Ported from the class at 0xd470..0xe9f1.

    @interface oalPlayback
        ALBuffer  _buffers[128];   // filename, bufferId, data
        ALSource  _sources[122];   // sourceId, noteIndex, queued, time, sourcePos, isPlaying
        BOOL      _initialized;
        int       _numBuffers;
        CGPoint   listenerPos;
        float     listenerRotation;
        AVAudioPlayer *bgPlayer, *ambPlayer;
        BOOL      loopNotes;
        int       sourceNumber;

A "note" is an index into both arrays at once: ``AppDelegate`` hands out note numbers from
``aSoundBufControlData`` (see ``app_delegate.playSoundBufNumber_``) and every call here -
``queueNote:``, ``startSound:Postion:``, ``stopSound:`` - indexes ``_sources[note]`` with it.
``_numBuffers``/``sourceNumber`` are the high-water marks, raised by ``initBufferOne:`` and
``initSourceOne:``.

The AL parameters are the original's, unchanged:

    -[oalPlayback queueNote:gain:sourcePos:defaultZ:repeats:]        0xe028
        AL_LOOPING           repeats
        AL_REFERENCE_DISTANCE 40.0     (0xe0de: movt r2, #0x4220)
        AL_MAX_DISTANCE      800.0     (0xe0ee: movt r2, #0x4448)
        AL_GAIN              gain
        AL_CONE_OUTER_ANGLE  1.0       (0xe10a)
        AL_CONE_INNER_ANGLE  1.0       (0xe116)
        AL_POSITION          (pos.x, (float)defaultZ, pos.y)   (0xe124..0xe146)
        AL_BUFFER            _buffers[note].bufferId

    -[oalPlayback MonsterQueueNote:...]                              0xe188
        same, but AL_REFERENCE_DISTANCE 100.0 and AL_MAX_DISTANCE 1600.0, and it sets
        only AL_CONE_OUTER_ANGLE.

    -[oalPlayback setListenerRotation:]                              0xe890
        alListenerfv(AL_ORIENTATION,
                     {cosf(rot + M_PI_2), sinf(rot + M_PI_2), 0, 0, 1, 1})

The up vector the original passes is (0, 1, 1), not a unit vector, and its "at" vector lies
in x/y while sources are placed in x/z.  Both are reproduced as written - see
docs/DIVERGENCES.md.
"""
from __future__ import annotations

import logging
import math
import os
import time
import wave

from .. import paths
from ..platform import openal as al
from ..platform.music import MusicPlayer

log = logging.getLogger('oal')

MAX_BUFFERS = 128       # oalPlayback._buffers[128]
MAX_SOURCES = 122       # oalPlayback._sources[122]


class _Buffer:
    __slots__ = ('filename', 'bufferId', 'channels', 'rate')

    def __init__(self):
        self.filename = None
        self.bufferId = 0
        self.channels = 0
        self.rate = 0


class _Source:
    __slots__ = ('sourceId', 'noteIndex', 'queued', 'time', 'sourcePos', 'isPlaying')

    def __init__(self):
        self.sourceId = 0
        self.noteIndex = 0
        self.queued = False
        self.time = 0.0
        self.sourcePos = (0.0, 0.0)
        self.isPlaying = False


def _load_wav(path):
    """What ``-[oalPlayback initBufferOne:FileName:Type:]`` gets from AudioFile/ExtAudioFile.

    The bundle's WAVs are 16-bit PCM, mono or stereo.  OpenAL only spatialises mono
    buffers; the original relied on exactly that, which is why the zombie and weapon
    sounds are mono and the voice/menu/music ones are stereo.  Nothing is converted.
    """
    with wave.open(path, 'rb') as w:
        ch = w.getnchannels()
        width = w.getsampwidth()
        rate = w.getframerate()
        pcm = w.readframes(w.getnframes())
    if width == 1:
        fmt = al.AL_FORMAT_MONO8 if ch == 1 else al.AL_FORMAT_STEREO8
    else:
        fmt = al.AL_FORMAT_MONO16 if ch == 1 else al.AL_FORMAT_STEREO16
    return fmt, pcm, rate, ch


class OalPlayback:
    """-[oalPlayback ...]"""

    def __init__(self):
        self.al = al.AL()
        self._buffers = [_Buffer() for _ in range(MAX_BUFFERS)]
        self._sources = [_Source() for _ in range(MAX_SOURCES)]
        self._initialized = False
        self._numBuffers = 0
        self.sourceNumber = 0
        self.listenerPos = (0.0, 0.0)
        self.listenerRotation = 0.0
        self.loopNotes = False
        self.isPlaying = False
        self.wasInterrupted = False
        self.iPodIsPlaying = False
        self.bgPlayer = MusicPlayer(self)    # -[oalPlayback bgPlayer]  (AVAudioPlayer)
        self.ambPlayer = MusicPlayer(self)   # -[oalPlayback ambPlayer]
        self.init()

    # ---- -[oalPlayback init] 0xd470 --------------------------------------
    def init(self):
        self.listenerPos = (0.0, 0.0)
        self.listenerRotation = 0.0
        self.setUpAudio()
        self._initialized = True
        self.wasInterrupted = False

    # ---- -[oalPlayback setUpAudio] 0xd9d0 --------------------------------
    def setUpAudio(self):
        self.setUpOpenAL()

    def tearDownAudio(self):
        self.teardownOpenAL()

    # ---- -[oalPlayback setUpOpenAL] 0xdbd4 -------------------------------
    def setUpOpenAL(self):
        self.al.open()
        log.info('OpenAL: %s, HRTF %s',
                 (self.al.alGetString(al.AL_NONE + 0xB003) or b'?').decode(errors='replace'),
                 'on' if self.al.hrtf else 'off')
        self.initBuffers()
        self.initSources()

    def teardownOpenAL(self):
        self.freeSources()
        self.freeBuffers()
        self.al.close()

    # ---- buffers ---------------------------------------------------------
    def initBuffers(self):
        """-[oalPlayback initBuffers] 0xdd50 - nothing is preloaded; AppDelegate fills
        slots on demand through ``initBufferOne:FileName:Type:``."""
        self._numBuffers = 0

    def freeBuffers(self):
        for i in range(MAX_BUFFERS):
            self.freeBufferOne(i)
        self._numBuffers = 0

    def freeBufferOne_(self, index):
        """-[oalPlayback freeBufferOne:] 0xdc4c"""
        self.freeBufferOne(index)

    def freeBufferOne(self, index):
        if not (0 <= index < MAX_BUFFERS):
            return
        b = self._buffers[index]
        if b.bufferId:
            self.al.delete_buffer(b.bufferId)
            b.bufferId = 0
            b.filename = None

    def initBufferOne_FileName_Type_(self, index, filename, filetype):
        """-[oalPlayback initBufferOne:FileName:Type:] 0xdc80"""
        if not (0 <= index < MAX_BUFFERS):
            return
        path = paths.path_for_resource(filename, filetype)
        if path is None or not os.path.exists(path):
            log.warning('sound file missing: %s.%s', filename, filetype)
            return
        b = self._buffers[index]
        if b.bufferId:
            self.al.delete_buffer(b.bufferId)
        fmt, pcm, rate, ch = _load_wav(path)
        b.bufferId = self.al.gen_buffer()
        b.filename = filename
        b.channels = ch
        b.rate = rate
        self.al.buffer_data(b.bufferId, fmt, pcm, rate)
        self.al.alGetError()
        if index + 1 > self._numBuffers:
            self._numBuffers = index + 1

    # ---- sources ---------------------------------------------------------
    def initSources(self):
        """-[oalPlayback initSources] 0xdeb0"""
        self.sourceNumber = 0

    def freeSources(self):
        for i in range(MAX_SOURCES):
            self.freeSourceOne(i)
        self.sourceNumber = 0

    def freeSourceOne_(self, index):
        self.freeSourceOne(index)

    def freeSourceOne(self, index):
        """-[oalPlayback freeSourceOne:] 0xde78"""
        if not (0 <= index < MAX_SOURCES):
            return
        s = self._sources[index]
        if s.sourceId:
            self.al.alSourceStop(s.sourceId)
            self.al.delete_source(s.sourceId)
            s.sourceId = 0
            s.isPlaying = False
            s.queued = False

    def initSourceOne_(self, index):
        """-[oalPlayback initSourceOne:] 0xde3c"""
        if not (0 <= index < MAX_SOURCES):
            return
        s = self._sources[index]
        if s.sourceId:
            self.al.delete_source(s.sourceId)
        s.sourceId = self.al.gen_source()
        s.noteIndex = index
        s.isPlaying = False
        s.queued = False
        self.al.alGetError()
        if index + 1 > self.sourceNumber:
            self.sourceNumber = index + 1

    def findAvailableSource(self):
        """-[oalPlayback findAvailableSource] 0xdf7c - the oldest non-playing source,
        falling back to the oldest of all, which it stops."""
        self.al.alGetError()
        if self.sourceNumber < 1:
            return 0
        oldest = 0
        for i in range(self.sourceNumber):
            s = self._sources[i]
            if not s.sourceId:
                continue
            if self.al.source_state(s.sourceId) != al.AL_PLAYING:
                return i
            if s.time < self._sources[oldest].time:
                oldest = i
        self.al.alSourceStop(self._sources[oldest].sourceId)
        return oldest

    # ---- playing ---------------------------------------------------------
    def _configure(self, note, gain, sourcePos, defaultZ, repeats,
                   reference_distance, max_distance, inner_cone):
        """The body shared by ``queueNote:`` (0xe028) and ``MonsterQueueNote:`` (0xe188)."""
        if not self._initialized or note == -1:
            return
        if not (0 <= note < MAX_SOURCES):
            return
        s = self._sources[note]
        if not s.sourceId:
            return
        A = self.al
        A.alGetError()
        s.time = time.time()
        s.noteIndex = note
        s.queued = True
        sid = s.sourceId
        A.alSourcei(sid, al.AL_LOOPING, 1 if repeats else 0)
        A.alSourcef(sid, al.AL_REFERENCE_DISTANCE, reference_distance)
        A.alSourcef(sid, al.AL_MAX_DISTANCE, max_distance)
        A.alSourcef(sid, al.AL_GAIN, gain)
        A.alSourcef(sid, al.AL_CONE_OUTER_ANGLE, 1.0)
        if inner_cone:
            A.alSourcef(sid, al.AL_CONE_INNER_ANGLE, 1.0)
        # AL_POSITION = (pos.x, (float)defaultZ, pos.y)
        A.source_fv(sid, al.AL_POSITION,
                    (float(sourcePos[0]), float(defaultZ), float(sourcePos[1])))
        b = self._buffers[note] if note < MAX_BUFFERS else None
        A.alSourcei(sid, al.AL_BUFFER, 0)
        if b is not None and b.bufferId:
            A.alSourcei(sid, al.AL_BUFFER, b.bufferId)
        A.alGetError()

    def queueNote_gain_sourcePos_defaultZ_repeats_(self, note, gain, sourcePos, defaultZ, repeats):
        """-[oalPlayback queueNote:gain:sourcePos:defaultZ:repeats:] 0xe028"""
        self._configure(note, gain, sourcePos, defaultZ, repeats,
                        reference_distance=40.0, max_distance=800.0, inner_cone=True)

    def MonsterQueueNote_gain_sourcePos_defaultZ_repeats_(self, note, gain, sourcePos, defaultZ, repeats):
        """-[oalPlayback MonsterQueueNote:gain:sourcePos:defaultZ:repeats:] 0xe188"""
        self._configure(note, gain, sourcePos, defaultZ, repeats,
                        reference_distance=100.0, max_distance=1600.0, inner_cone=False)

    def MosterPos_QuereNote_defaultZ_(self, pos, note, defaultZ):
        """-[oalPlayback MosterPos:QuereNote:defaultZ:] 0xe2d8 - move a live monster's
        source without restarting it."""
        if not self._initialized or note == -1 or not (0 <= note < MAX_SOURCES):
            return
        s = self._sources[note]
        if not s.sourceId:
            return
        s.time = time.time()
        s.noteIndex = note
        s.sourcePos = (float(pos[0]), float(pos[1]))
        self.al.source_fv(s.sourceId, al.AL_POSITION,
                          (float(pos[0]), float(defaultZ), float(pos[1])))
        b = self._buffers[note] if note < MAX_BUFFERS else None
        self.al.alSourcei(s.sourceId, al.AL_BUFFER, 0)
        if b is not None and b.bufferId:
            self.al.alSourcei(s.sourceId, al.AL_BUFFER, b.bufferId)

    def startSound_Postion_(self, note, pos):
        """-[oalPlayback startSound:Postion:] 0xe49c"""
        if not (0 <= note < MAX_SOURCES):
            return
        s = self._sources[note]
        if not s.sourceId:
            return
        s.sourcePos = (float(pos[0]), float(pos[1]))
        s.isPlaying = True
        s.queued = False
        self.al.alSourcePlay(s.sourceId)

    def startSound_Postion_soundGain_(self, note, pos, gain):
        """-[oalPlayback startSound:Postion:soundGain:] 0xe524"""
        if not (0 <= note < MAX_SOURCES):
            return
        s = self._sources[note]
        if not s.sourceId:
            return
        self.al.alSourcef(s.sourceId, al.AL_GAIN, gain)
        self.startSound_Postion_(note, pos)

    def startSoundPostion_SoundNumber_(self, pos, note):
        """-[oalPlayback startSoundPostion:SoundNumber:] 0xe60c"""
        self.startSound_Postion_(note, pos)

    def playQueuedNotes(self):
        """-[oalPlayback playQueuedNotes] 0xe62c - alSourcePlayv over every queued source."""
        for i in range(self.sourceNumber):
            s = self._sources[i]
            if s.queued and s.sourceId:
                s.queued = False
                s.isPlaying = True
                self.al.alSourcePlay(s.sourceId)

    def stopSound_(self, note):
        """-[oalPlayback stopSound:] 0xe3bc"""
        if not (0 <= note < MAX_SOURCES):
            return
        s = self._sources[note]
        if not s.sourceId:
            return
        self.al.alSourceStop(s.sourceId)
        self.al.alGetError()
        if self.al.alGetError() == al.AL_NO_ERROR:
            s.isPlaying = False

    def noteOff_(self, note):
        """-[oalPlayback noteOff:] 0xe6c8"""
        self.stopSound_(note)

    def allNotesOff(self):
        """-[oalPlayback allNotesOff] 0xe734"""
        for i in range(self.sourceNumber):
            s = self._sources[i]
            if s.sourceId:
                self.al.alSourceStop(s.sourceId)
                s.isPlaying = False
                s.queued = False

    def is_note_playing(self, note):
        """Not in the original; the port uses it where the original relied on a timer
        firing at the sound's known length."""
        if not (0 <= note < MAX_SOURCES):
            return False
        s = self._sources[note]
        return bool(s.sourceId) and self.al.source_state(s.sourceId) == al.AL_PLAYING

    # ---- listener --------------------------------------------------------
    def setListenerPos_(self, pos):
        """-[oalPlayback setListenerPos:] 0xe9c8"""
        self.listenerPos = (float(pos[0]), float(pos[1]))
        self.al.alListener3f(al.AL_POSITION, float(pos[0]), 0.0, float(pos[1]))

    def setListenerRotation_(self, rot):
        """-[oalPlayback setListenerRotation:] 0xe890

            float ori[6] = { cosf(rot + M_PI_2), sinf(rot + M_PI_2), 0, 0, 1.0f, 1.0f };
            alListenerfv(AL_ORIENTATION, ori);
        """
        self.listenerRotation = float(rot)
        a = float(rot) + math.pi / 2.0
        self.al.listener_fv(al.AL_ORIENTATION,
                            (math.cos(a), math.sin(a), 0.0, 0.0, 1.0, 1.0))

    def setListenerRotation_Pos_(self, rot, posType):
        """-[oalPlayback setListenerRotation:Pos:] 0xe7b0

        The up vector differs by ``posType``: for 1 and 3 it is (0, 1, 1), otherwise
        (1, ...) - 0xe7e8 ``orr r0, r3, #2 ; cmp r0, #3``.
        """
        self.listenerRotation = float(rot)
        a = float(rot) + math.pi / 2.0
        c, s = math.cos(a), math.sin(a)
        if (posType | 2) == 3:
            ori = (c, s, 0.0, 0.0, 1.0, 1.0)
        else:
            ori = (c, s, 0.0, 1.0, 0.0, 0.0)
        self.al.listener_fv(al.AL_ORIENTATION, ori)

    # ---- background / ambience (AVAudioPlayer in the original) ------------
    def startBGPlayer_type_soundGain_Loop_(self, name, filetype, gain, loop):
        """-[oalPlayback startBGPlayer:type:soundGain:Loop:] 0xd5e0"""
        path = paths.path_for_resource(name, filetype)
        if path:
            self.bgPlayer.play(path, gain, -1 if loop else 0)

    def backgroundSoundStop(self):
        """-[oalPlayback backgroundSoundStop] 0xd738"""
        self.bgPlayer.stop()

    def startAMBPlayer_type_soundGain_Loop_(self, name, filetype, gain, loop):
        """-[oalPlayback startAMBPlayer:type:soundGain:Loop:] 0xd790"""
        path = paths.path_for_resource(name, filetype)
        if path:
            self.ambPlayer.play(path, gain, -1 if loop else 0)

    def AMBSoundStop(self):
        """-[oalPlayback AMBSoundStop] 0xd8e8"""
        self.ambPlayer.stop()
