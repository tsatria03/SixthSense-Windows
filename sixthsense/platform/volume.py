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

The decibel knobs are constants.  On top of them sit the player's settings (tsatria03,
2026-09-25; aidocks/project_volume_settings_plan.md), percentages kept in settings.json and
changed only by editing it:

    MASTERVOLUME       everything, with MASTER_DB
    MENUMUSICVOLUME    the menu music, which Page Up and Page Down also set
    LEVELMUSICVOLUME   the level music, with MUSIC_DB
    AMBIENCEVOLUME     the ambience and the rain, with AMBIENCE_DB

Each is a whole number from 0 to 100; 100, the default, is the original's mix, and anything
else counts as 100.  The percentage is squared into the gain (``percent_gain``), so each
step sounds about as big as the last.  ``load`` reads them when the game starts and writes
any that are missing, so settings.json shows every one; an edit takes effect on the next
start.
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


# ---- the player's settings ---------------------------------------------------------------
#: The settings.json keys, in the order that file lists them (defaults.SETTINGS_KEYS).
MASTER_KEY = 'MASTERVOLUME'
MENU_MUSIC_KEY = 'MENUMUSICVOLUME'
LEVEL_MUSIC_KEY = 'LEVELMUSICVOLUME'
AMBIENCE_KEY = 'AMBIENCEVOLUME'
VOLUME_KEYS = (MASTER_KEY, MENU_MUSIC_KEY, LEVEL_MUSIC_KEY, AMBIENCE_KEY)

#: The steps Page Up and Page Down move the menu music by; any whole number from 0 to 100
#: can be set by hand.  100 is the original's mix (MENU_MUSIC_DB for the menu music), never
#: louder; 0 is silent.
MENU_MUSIC_VOLUMES = tuple(range(0, 101, 10))
DEFAULT_MENU_MUSIC_VOLUME = 100
DEFAULT_PERCENT = 100

#: What ``load`` last read, by key; every one is 100 until then.
percents = {key: DEFAULT_PERCENT for key in VOLUME_KEYS}


def valid_percent(value):
    """``value`` as a whole percentage from 0 to 100, or None when it is not one: a word,
    a fraction, anything below 0 or above 100.  A hand-edited file may hold "30"."""
    if isinstance(value, bool):
        return None
    if isinstance(value, float):
        value = int(value) if value.is_integer() else None
    elif isinstance(value, str):
        text = value.strip()
        value = int(text) if text.isdigit() else None
    if not isinstance(value, int) or not 0 <= value <= 100:
        return None
    return value


def percent(value):
    """``valid_percent``, with anything invalid counting as 100."""
    p = valid_percent(value)
    return DEFAULT_PERCENT if p is None else p


def percent_gain(p) -> float:
    """A percentage as a gain: squared, so 100 is 1.0, 50 a quarter (about -12 dB), 0
    silent, and each step sounds about as big as the last - straight percentages barely
    change anything near the top and drop to nothing in the last step or two."""
    return (max(0, min(p, 100)) / 100.0) ** 2


def load(defaults):
    """Read the volume settings when the game starts, and write any that are missing at
    their default, so settings.json lists every one.  True when anything was written."""
    wrote = False
    for key in VOLUME_KEYS:
        value = defaults.objectForKey_(key)
        if value is None:
            defaults.setInteger_forKey_(DEFAULT_PERCENT, key)
            wrote = True
        percents[key] = percent(value)
    return wrote


def master(g: float) -> float:
    """``MASTER_DB`` and ``MASTERVOLUME`` applied.  ``oal_playback`` calls this on its way
    to ``AL_GAIN``, so nothing else has to remember to."""
    return g * gain(MASTER_DB) * percent_gain(percents[MASTER_KEY])


def music(g: float) -> float:
    """A level music gain from the binary, with ``MUSIC_DB`` and ``LEVELMUSICVOLUME``."""
    return g * gain(MUSIC_DB) * percent_gain(percents[LEVEL_MUSIC_KEY])


def ambience(g: float) -> float:
    """An ambience or rain gain from the binary, with ``AMBIENCE_DB`` and
    ``AMBIENCEVOLUME``."""
    return g * gain(AMBIENCE_DB) * percent_gain(percents[AMBIENCE_KEY])


def menu_music(p: int = DEFAULT_MENU_MUSIC_VOLUME) -> float:
    """The menu music's gain at ``p`` percent: ``MENU_MUSIC_DB`` at 100%, squared below
    that.  In decibels, ``40 * log10(p / 100)`` under ``MENU_MUSIC_DB``."""
    return gain(MENU_MUSIC_DB) * percent_gain(p)
