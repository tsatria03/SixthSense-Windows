"""PORT ADDITION: the volume knobs, in decibels.

Every gain in this game comes out of the binary, and each one is written where it is used
with the address it was read from: the level music at 0.02 (0x321d4), the ambience at 0.2
(0x2ddfa), the rain at 0.5 (0x2ddc8), a gunshot at 1.0.  Those numbers stay exactly as they
are, so the mix is still the original's.

What is here instead is a set of knobs that move whole groups of sounds, in decibels,
because decibels are how loudness is actually talked about: +6 dB is twice the amplitude,
-6 dB is half, and about 10 dB either way is heard as twice or half as loud.  At 0.0 a knob
changes nothing at all, so the mix as shipped is the binary's until someone turns one.

    MASTER_DB       everything the game plays
    MUSIC_DB        the level music, under the zombies
    AMBIENCE_DB     the cave, the forest and the rain
    MENU_MUSIC_DB   the menu music, which is the port's own sound and so has no gain in
                    the binary to start from - this one is the whole value, not a trim

``MASTER_DB`` is applied in ``oal_playback``, where every ``AL_GAIN`` is set, so it reaches
sound effects, speech recordings and music alike.  The group knobs are applied where the
sound is started, because only the caller knows what kind of sound it is starting.

These are constants, not settings: nothing writes them to the save file yet.  When the game
grows a settings screen, this is where its sliders would be read into.
"""
from __future__ import annotations

import math

#: Everything, at once.
MASTER_DB = 0.0
#: The level music (``bgm_cave`` / ``bgm_forest``), on top of the binary's 0.02.
MUSIC_DB = 0.0
#: The ambience and the rain, on top of the binary's 0.2 and 0.5.
AMBIENCE_DB = 0.0
#: The menu music, in full: the original never plays music on its menu, so there is no
#: value of its own to sit on top of.  -14 dB is a gain of 0.1995, the 0.2 the dev picked
#: by ear on 2026-09-22, and the same loudness the menu's own rows are read at.
MENU_MUSIC_DB = -14.0


def gain(db: float) -> float:
    """Decibels as the amplitude multiplier OpenAL's ``AL_GAIN`` wants: 0 dB is 1.0,
    -6 dB is about a half, -20 dB is a tenth."""
    return 10.0 ** (db / 20.0)


def decibels(g: float) -> float:
    """The other way round, for saying out loud how loud something is.  Silence has no
    decibel value, so it comes back as negative infinity."""
    return 20.0 * math.log10(g) if g > 0 else float('-inf')


def master(g: float) -> float:
    """``MASTER_DB`` applied.  ``oal_playback`` calls this on its way to ``AL_GAIN``, so
    nothing else has to remember to."""
    return g * gain(MASTER_DB)


def music(g: float) -> float:
    """A level music gain from the binary, with ``MUSIC_DB`` applied."""
    return g * gain(MUSIC_DB)


def ambience(g: float) -> float:
    """An ambience or rain gain from the binary, with ``AMBIENCE_DB`` applied."""
    return g * gain(AMBIENCE_DB)


def menu_music() -> float:
    """The menu music's gain, which is ``MENU_MUSIC_DB`` and nothing else."""
    return gain(MENU_MUSIC_DB)
