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

During play there are three more (tunmi13productions, 2026-09-26;
aidocks/project_gameplay_gain_plan.md), which Page Up and Page Down with a modifier set
in the stage, the tutorial and the test range, as well as by hand:

    GAMEPLAYGAIN       0 to 6 dB on OpenAL's listener, so every sound effect and the
                       recorded speech louder together, the balance between them kept;
                       the music and the ambience are held where they were
    WEAPONVOLUME       the weapons, sfx/weapons, but not their hits
    PLAYERVOLUME       your breathing, being hurt and dying

The entities (the zombies, the bosses, the monster and the woman, and a weapon's hit on
one) had a setting too, ENTITYVOLUME, until tunmi13productions removed it on 2026-09-28:
they are what the player listens for, so they always play at full volume
(aidocks/project_entity_full_volume_plan.md).

The two groups are percentages like the rest and only turn down, since the settings'
part of a source's gain is capped at 1.0 (``oal_playback._gain``) and a gunshot is there
already; the gain is the way up.  ``group_of`` sorts
a sound into its group as its buffer loads, and ``oal_playback`` applies it.
"""
from __future__ import annotations

import math
import os
import re

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
#: The per-file trims that even out the recordings (platform/sound_trims.py).  F8 flips
#: this in debug mode, for hearing them against the files as they are; it is never saved.
SOUND_TRIMS_ON = True


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
GAMEPLAY_GAIN_KEY = 'GAMEPLAYGAIN'
WEAPON_KEY = 'WEAPONVOLUME'
PLAYER_KEY = 'PLAYERVOLUME'
#: The percentages; ``GAMEPLAYGAIN`` is decibels and kept apart.
VOLUME_KEYS = (MASTER_KEY, MENU_MUSIC_KEY, LEVEL_MUSIC_KEY, AMBIENCE_KEY,
               WEAPON_KEY, PLAYER_KEY)

#: The steps Page Up and Page Down move the menu music by; any whole number from 0 to 100
#: can be set by hand.  100 is the original's mix (MENU_MUSIC_DB for the menu music), never
#: louder; 0 is silent.
MENU_MUSIC_VOLUMES = tuple(range(0, 101, 10))
DEFAULT_MENU_MUSIC_VOLUME = 100
DEFAULT_PERCENT = 100

#: The gameplay gain, whole decibels from 0 to 6: 6 dB is a listener gain of 2.0, the cap
#: the dev chose.  0 is the original's mix.
MAX_GAMEPLAY_GAIN_DB = 6
DEFAULT_GAMEPLAY_GAIN_DB = 0

#: What ``load`` last read, by key; every one is 100 until then.
percents = {key: DEFAULT_PERCENT for key in VOLUME_KEYS}
#: What ``load`` last read for ``GAMEPLAYGAIN``.
gameplay_gain_db = DEFAULT_GAMEPLAY_GAIN_DB


def _whole(value, top):
    """``value`` as a whole number from 0 to ``top``, or None when it is not one: a word,
    a fraction, anything out of range.  A hand-edited file may hold "30"."""
    if isinstance(value, bool):
        return None
    if isinstance(value, float):
        value = int(value) if value.is_integer() else None
    elif isinstance(value, str):
        text = value.strip()
        value = int(text) if text.isdigit() else None
    if not isinstance(value, int) or not 0 <= value <= top:
        return None
    return value


def valid_percent(value):
    """``value`` as a whole percentage from 0 to 100, or None when it is not one."""
    return _whole(value, 100)


def valid_gain_db(value):
    """``value`` as a whole gameplay gain from 0 to 6 dB, or None when it is not one."""
    return _whole(value, MAX_GAMEPLAY_GAIN_DB)


def percent(value):
    """``valid_percent``, with anything invalid counting as 100."""
    p = valid_percent(value)
    return DEFAULT_PERCENT if p is None else p


def percent_gain(p) -> float:
    """A percentage as a gain: squared, so 100 is 1.0, 50 a quarter (about -12 dB), 0
    silent, and each step sounds about as big as the last - straight percentages barely
    change anything near the top and drop to nothing in the last step or two."""
    return (max(0, min(p, 100)) / 100.0) ** 2


def step_percent(now, step):
    """Page Up (+1) or Page Down (-1) from ``now``: the next step of ten, holding at 0 and
    100.  From a value set by hand between two steps it goes to the nearer step that way:
    55 goes up to 60 and down to 50."""
    if step > 0:
        return min(100, (now // 10 + 1) * 10)
    return max(0, (-(-now // 10) - 1) * 10)


def step_gain_db(now, step):
    """Page Up (+1) or Page Down (-1) on the gameplay gain: 1 dB, holding at 0 and 6."""
    return max(0, min(MAX_GAMEPLAY_GAIN_DB, now + (1 if step > 0 else -1)))


def load(defaults):
    """Read the volume settings when the game starts, and write any that are missing at
    their default, so settings.json lists every one.  True when anything was written."""
    global gameplay_gain_db
    wrote = False
    for key in VOLUME_KEYS:
        value = defaults.objectForKey_(key)
        if value is None:
            defaults.setInteger_forKey_(DEFAULT_PERCENT, key)
            wrote = True
        percents[key] = percent(value)
    value = defaults.objectForKey_(GAMEPLAY_GAIN_KEY)
    if value is None:
        defaults.setInteger_forKey_(DEFAULT_GAMEPLAY_GAIN_DB, GAMEPLAY_GAIN_KEY)
        wrote = True
    db = valid_gain_db(value)
    gameplay_gain_db = DEFAULT_GAMEPLAY_GAIN_DB if db is None else db
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


# ---- during play (tunmi13productions, 2026-09-26) -------------------------------------------------
#: The groups ``group_of`` sorts a sound into.  BACKDROP is the music and the ambience,
#: which the gameplay gain leaves where they were.
WEAPONS = 'weapons'
ENTITIES = 'entities'
PLAYER = 'player'
BACKDROP = 'backdrop'
#: The entities have no setting: they are always at full volume.
GROUP_KEY = {WEAPONS: WEAPON_KEY, PLAYER: PLAYER_KEY}

#: The folders under game/sounds whose sounds belong to a group.  speech/weapons is the
#: shop naming a weapon, not a weapon, so the folder is matched with sfx in front.
#: A weapon's hit or kill on a zombie, which sfx/weapons keeps but the dev hears as the
#: zombie being struck (2026-09-26): weapon_gun_att1 and 2, and the blades' att1 and 2.
_HIT = re.compile(r'weapon_\w+_att\d$')
_GROUP_FOLDERS = (('sfx/weapons/', WEAPONS), ('sfx/zombies/', ENTITIES),
                  ('sfx/monsters/', ENTITIES), ('sfx/characters/', ENTITIES))


def group_of(name, path=None):
    """The group a sound belongs to, from its file name and where it was found, or None
    for a sound in no group (the speech, the warning, the menu's click)."""
    name = (name or '').lower()
    if name.startswith('player_'):
        return PLAYER
    if name.startswith('bgm_') or name == 'effect_forest_rainng':
        return BACKDROP
    if _HIT.match(name):
        return ENTITIES
    where = (path or '').replace(os.sep, '/').lower()
    for folder, group in _GROUP_FOLDERS:
        if '/' + folder in where:
            return group
    return None


def group_gain(group) -> float:
    """What a group's setting multiplies its sounds by: 1.0 at 100, for the entities,
    and for a sound in no group."""
    key = GROUP_KEY.get(group)
    return 1.0 if key is None else percent_gain(percents[key])


def gameplay_gain() -> float:
    """The listener gain during play: 1.0 at 0 dB, 2.0 at 6 dB."""
    return gain(gameplay_gain_db)
