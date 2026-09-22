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
import wave

from . import openal as al

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
                self.stop()
                if self.buffer:
                    self.al.delete_buffer(self.buffer)
                    self.buffer = 0
                fmt, pcm, rate = _load(path)
                self.buffer = self.al.gen_buffer()
                self.al.buffer_data(self.buffer, fmt, pcm, rate)
                self.path = path
            self.al.alSourceStop(self.source)
            self.al.alSourcei(self.source, al.AL_BUFFER, self.buffer)
            self.al.alSourcei(self.source, al.AL_LOOPING, 1 if loops != 0 else 0)
            self.volume = gain
            self.al.alSourcef(self.source, al.AL_GAIN, gain)
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
            self.al.alSourcef(self.source, al.AL_GAIN, gain)

    @property
    def playing(self):
        return bool(self.source) and self.al.source_state(self.source) == al.AL_PLAYING
