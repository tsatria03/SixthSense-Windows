"""Filesystem locations used by the port.

The game's data is the original bundle's data, unconverted and un-rearranged.
``game/`` holds the contents of ``Payload/sixsense.app`` exactly as it shipped - the
269 WAVs, the binary plists (``SoundList.plist``, the ``typeN.plist`` monster tables,
the weapon tables), the three map layers (``g_CH1_E``, ``s_CH1_E.txt``,
``a_CH1_E.txt``), the nibs, the PNGs, ``Info.plist``, the Facebook resource bundle and
the code signature. The bundle is flat, so every lookup the original makes through
``[[NSBundle mainBundle] pathForResource:ofType:]`` is the same lookup here.

Nothing in ``game/`` is modified, and the port never writes to it. The save file lives
in ``%APPDATA%\\SixthSense``.

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

_override: str | None = None


def set_game(path: str) -> None:
    """Point the bundle lookup somewhere else (``--game``)."""
    global _override, _game
    _override = path
    _game = None


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


# The bundle is flat: sounds, plists, maps and images all sit next to each other.
# These three exist because the code reads better when it says what it is after.
def sounds() -> str:
    return game()


def data() -> str:
    return game()


def images() -> str:
    return game()


def resources() -> str:
    return game()


def path_for_resource(name: str, ext: str | None = None) -> str | None:
    """``-[NSBundle pathForResource:ofType:]``."""
    filename = name if not ext else '%s.%s' % (name, ext)
    p = os.path.join(game(), filename)
    return p if os.path.exists(p) else None


def user_dir() -> str:
    """Where ``NSUserDefaults`` and the save game live."""
    base = os.environ.get('APPDATA') or os.path.expanduser('~')
    p = os.path.join(base, 'SixthSense')
    os.makedirs(p, exist_ok=True)
    return p
