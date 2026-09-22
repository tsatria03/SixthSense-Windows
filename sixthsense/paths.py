"""Filesystem locations used by the port.

``game/`` holds the original app bundle's data, the contents of ``Payload/sixsense.app``
as it shipped - the binary plists (``SoundList.plist``, the ``typeN.plist`` monster
tables, the weapon tables), the three map layers (``g_CH1_E``, ``s_CH1_E.txt``,
``a_CH1_E.txt``), the nibs, the PNGs, ``Info.plist``, the Facebook resource bundle and
the code signature - all in its top folder, where the original kept them.

The sounds are the one exception.  The original bundle is flat, with its 269 WAVs beside
the plists; the port keeps them in folders under ``game/sounds/used``, each under its
original file name (docs/DIVERGENCES.md).  So ``path_for_resource``, which stands in for
``[[NSBundle mainBundle] pathForResource:ofType:]``, looks in the top folder first, as the
original did, and then by file name anywhere under ``sounds/used``.  ``sounds/unused``
holds files that are not the original's own, and is never searched.

Because the top folder comes first, an untouched original bundle still works: its WAVs are
all found where the original found them.

The port never writes to ``game/``.  The save file lives in ``%APPDATA%\\SixthSense``.

``--game PATH`` (or ``SIXTHSENSE_GAME``) points somewhere else: another copy of the
bundle, or a folder holding ``Payload/sixsense.app``.
"""
from __future__ import annotations

import os
import sys

FROZEN = getattr(sys, 'frozen', False)
if FROZEN:
    ROOT = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    EXE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    EXE_DIR = ROOT

VENDOR = os.path.join(ROOT, 'vendor')
OPENAL_DLL = os.path.join(VENDOR, 'openal', 'soft_oal.dll')
NVDA_DLL = os.path.join(VENDOR, 'nvda', 'nvdaControllerClient64.dll')

# The thin armv7 slice, for tools/.  Not needed to play.
BINARY = os.path.join(ROOT, 'analysis', 'bin', 'sixsense_armv7')

GAME_ENV = 'SIXTHSENSE_GAME'
APP_NAME = 'sixsense.app'

# Where the sounds are, inside the bundle folder.  An original bundle has no such folder.
SOUNDS_USED = os.path.join('sounds', 'used')

_override: str | None = None


def set_game(path: str | None) -> None:
    """Point the bundle lookup somewhere else (``--game``); None goes back to the
    default places."""
    global _override, _game, _sound_index
    _override = path
    _game = None
    _sound_index = None


# kept for callers that still say "resources"
set_resources = set_game


def _candidates():
    if _override:
        yield 'the --game option', _override
        yield 'the --game option', os.path.join(_override, 'Payload', APP_NAME)
        yield 'the --game option', os.path.join(_override, APP_NAME)
    env = os.environ.get(GAME_ENV)
    if env:
        yield 'the %s environment variable' % GAME_ENV, env
        yield 'the %s environment variable' % GAME_ENV, os.path.join(env, 'Payload', APP_NAME)
        yield 'the %s environment variable' % GAME_ENV, os.path.join(env, APP_NAME)
    yield 'the port', os.path.join(EXE_DIR, 'game')
    yield 'the port', os.path.join(ROOT, 'game')


_game: str | None = None
_sound_index: dict[str, str] | None = None


def _is_bundle(path: str) -> bool:
    """A folder is the bundle if the data the game cannot start without is in it."""
    return all(os.path.exists(os.path.join(path, f))
               for f in ('SoundList.plist', 'g_CH1_E'))


def game() -> str:
    """The folder holding the contents of ``sixsense.app``."""
    global _game
    if _game is None:
        tried = []
        for why, path in _candidates():
            if path and _is_bundle(path):
                _game = path
                break
            tried.append('%s: %s' % (why, path))
        else:
            raise SystemExit("SixthSense's game data was not found. Tried:\n  "
                             + '\n  '.join(tried)
                             + "\nPass --game with the path to Payload/sixsense.app.")
    return _game


def sounds() -> str:
    """The folder the sounds are in: ``sounds/used``, or the bundle itself when it is an
    original, flat one."""
    p = os.path.join(game(), SOUNDS_USED)
    return p if os.path.isdir(p) else game()


# The plists, the maps and the images sit together in the bundle's top folder.  These
# exist because the code reads better when it says what it is after.
def data() -> str:
    return game()


def images() -> str:
    return game()


def resources() -> str:
    return game()


def _sounds_by_name() -> dict[str, str]:
    """Every file under ``sounds/used``, by its file name in lower case.

    Built once, the first time a sound is asked for.  Where the original reuses one
    recording in several places, each folder that uses it has its own copy of the same
    file; the first copy in sorted order is the one taken, so a name always gives the
    same file.
    """
    global _sound_index
    if _sound_index is None:
        index = {}
        for dirpath, dirs, files in os.walk(os.path.join(game(), SOUNDS_USED)):
            dirs.sort()
            for name in sorted(files):
                index.setdefault(name.lower(), os.path.join(dirpath, name))
        _sound_index = index
    return _sound_index


def path_for_resource(name: str, ext: str | None = None) -> str | None:
    """``-[NSBundle pathForResource:ofType:]``.

    The bundle's top folder first, which is the only place the original looked; then
    the sounds under ``sounds/used``, by file name, whatever folder they are in.
    Neither cares about case, as Windows does not.
    """
    filename = name if not ext else '%s.%s' % (name, ext)
    p = os.path.join(game(), filename)
    if os.path.exists(p):
        return p
    return _sounds_by_name().get(filename.lower())


def user_dir() -> str:
    """Where ``NSUserDefaults`` and the save game live."""
    base = os.environ.get('APPDATA') or os.path.expanduser('~')
    p = os.path.join(base, 'SixthSense')
    os.makedirs(p, exist_ok=True)
    return p
