"""``AVAudioPlayer`` stand-in for the two music streams ``oalPlayback`` owns.

The original keeps ``bgPlayer`` (music) and ``ambPlayer`` (ambience) as AVAudioPlayers,
separate from its OpenAL graph:

    -[oalPlayback startBGPlayer:type:soundGain:Loop:]   0xd5e0
        bgURL   = [NSURL fileURLWithPath:[[NSBundle mainBundle] pathForResource:name ofType:type]];
        bgPlayer = [[AVAudioPlayer alloc] initWithContentsOfURL:bgURL error:nil];
        bgPlayer.numberOfLoops = loop ? -1 : 0;
        bgPlayer.volume = gain;
        [bgPlayer prepareToPlay]; [bgPlayer play];

Here they are OpenAL sources instead of a second audio API, marked ``AL_SOURCE_RELATIVE``
and parked at the listener so panning and distance never touch them.  Every one of these
files is stereo, which OpenAL would refuse to spatialise anyway, so the result is the
same signal AVAudioPlayer produced: the file at ``volume``, unmoved by where the player
is looking.
"""
from __future__ import annotations

import logging
import os
import wave

from . import openal as al
from . import sound_trims

log = logging.getLogger('music')


def _load(path):
    with wave.open(path, 'rb') as w:
        ch, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
        pcm = w.readframes(w.getnframes())
    if width == 1:
        fmt = al.AL_FORMAT_MONO8 if ch == 1 else al.AL_FORMAT_STEREO8
    else:
        fmt = al.AL_FORMAT_MONO16 if ch == 1 else al.AL_FORMAT_STEREO16
    return fmt, pcm, rate


class MusicPlayer:
    def __init__(self, owner):
        self.owner = owner          # the OalPlayback that holds the AL context
        self.source = 0
        self.buffer = 0
        self.path = None
        self.volume = 1.0

    @property
    def al(self):
        return self.owner.al

    def _ensure(self):
        if not self.source:
            self.source = self.al.gen_source()
            self.al.alSourcei(self.source, al.AL_SOURCE_RELATIVE, 1)
            self.al.alSource3f(self.source, al.AL_POSITION, 0.0, 0.0, 0.0)
            self.al.alSourcef(self.source, al.AL_ROLLOFF_FACTOR, 0.0)
            # PORT ADDITION: room above 1.0, so a sound_trims boost is heard (_heard)
            self.al.alSourcef(self.source, al.AL_MAX_GAIN, sound_trims.MAX_GAIN)

    def _drop_buffer(self):
        """Let go of the file that is loaded, in the order OpenAL insists on: stop the
        source, take the buffer off it, then delete the buffer.

        ``alDeleteBuffers`` refuses a buffer that is still attached to a source and
        answers AL_INVALID_OPERATION, so deleting it first - as this did - freed nothing
        and left the whole file in memory for as long as the game ran.  These are the
        largest sounds in the game, 2 to 3 MB each, and a level change swaps two of them.
        """
        self.stop()
        if not self.buffer:
            return
        if self.source:
            self.al.alSourcei(self.source, al.AL_BUFFER, 0)     # detach
        self.al.alGetError()                                    # clear, then watch
        self.al.delete_buffer(self.buffer)
        error = self.al.alGetError()
        if error:
            log.warning('the music buffer for %s was not freed: %s',
                        self.path, al.AL_ERRORS.get(error, hex(error)))
        self.buffer = 0
        self.path = None

    def play(self, path, gain=1.0, loops=-1):
        """``numberOfLoops = -1`` means forever, as in AVAudioPlayer.

        PORT ADDITION: asking for the file that is already playing leaves it where it is,
        and only takes the new gain and loop setting.  ``AVAudioPlayer`` is built fresh
        every time in the original, so it always starts at the top; here the menu music
        would jump back to its first bar every time a menu is built, which is every time
        the player comes back from a stage, the shop or the tutorial.
        """
        try:
            self._ensure()
            if path == self.path and self.playing:
                self.al.alSourcei(self.source, al.AL_LOOPING, 1 if loops != 0 else 0)
                self.set_volume(gain)
                self.al.alGetError()
                return
            if path != self.path:
                self._drop_buffer()
                fmt, pcm, rate = _load(path)
                self.buffer = self.al.gen_buffer()
                self.al.buffer_data(self.buffer, fmt, pcm, rate)
                self.path = path
            self.al.alSourceStop(self.source)
            self.al.alSourcei(self.source, al.AL_BUFFER, self.buffer)
            self.al.alSourcei(self.source, al.AL_LOOPING, 1 if loops != 0 else 0)
            self.volume = gain
            self.al.alSourcef(self.source, al.AL_GAIN, self._heard(gain))
            self.al.alSourcePlay(self.source)
            self.al.alGetError()
        except Exception:
            log.exception('music play failed: %s', path)

    def stop(self):
        if self.source:
            self.al.alSourceStop(self.source)

    def pause(self):
        if self.source:
            self.al.alSourcePause(self.source)

    def resume(self):
        if self.source:
            self.al.alSourcePlay(self.source)

    def set_volume(self, gain):
        self.volume = gain
        if self.source:
            self.al.alSourcef(self.source, al.AL_GAIN, self._heard(gain))

    def _heard(self, gain):
        """PORT ADDITION (2026-09-26): the gameplay gain raises OpenAL's listener, which
        these sources sit under too, so it is taken back off here and the music and the
        ambience sound as they did.  ``volume`` stays the gain the game asked for.

        PORT ADDITION (2026-09-27): the playing file's ``sound_trims`` trim too, after the
        game's gain is capped at 1.0 as OpenAL capped it before ``AL_MAX_GAIN`` was
        raised.  With no trim it is the gain exactly."""
        if self.path:
            trim = sound_trims.gain(os.path.splitext(os.path.basename(self.path))[0])
            if trim != 1.0:
                gain = min(gain, 1.0) * trim
        listener = getattr(self.owner, 'listenerGain', 1.0)
        return gain / listener if listener and listener != 1.0 else gain

    @property
    def playing(self):
        return bool(self.source) and self.al.source_state(self.source) == al.AL_PLAYING
