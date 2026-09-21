"""``SoundListControl`` - one entry of ``AppDelegate.aSoundBufControlData``.

    @interface SoundListControl : NSObject
        NSString *sFileName;     // SoundList.plist[iFileNumber]
        int       iFileNumber;   // the game's sound number
        BOOL      bIsPlaying;

Its index in ``aSoundBufControlData`` is the OpenAL note: slot *i* of the array owns
``oalPlayback._buffers[i]`` and ``._sources[i]``.  The array is the whole of the game's
voice allocation - see ``-[AppDelegate playSoundBufNumber:]`` (0x6370).
"""
from __future__ import annotations


class SoundListControl:
    __slots__ = ('sFileName', 'iFileNumber', 'bIsPlaying')

    def __init__(self):
        self.sFileName = None
        self.iFileNumber = 0
        self.bIsPlaying = False

    def __repr__(self):
        return '<SoundListControl %d %r playing=%s>' % (
            self.iFileNumber, self.sFileName, self.bIsPlaying)
