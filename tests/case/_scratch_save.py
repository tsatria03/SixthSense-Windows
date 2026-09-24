"""Keep the tests off the real save, and silent.

Every test file imports this first, before any of the game.  It:

* points ``SIXTHSENSE_USER_DIR`` at a fresh folder of its own, so ``defaults.json`` and
  ``keys.json`` are written there and never to ``%APPDATA%\\SixthSense``, and deletes
  that folder when the run ends;
* sets ``SIXTHSENSE_SILENT``, so ``platform/speech.py`` never loads NVDA's client or
  Prism and never speaks or cuts off the player's screen reader;
* sends the sound to OpenAL Soft's null driver and SDL's dummy audio, and gives pygame
  a dummy display, so nothing is heard and no window opens for a screen reader to
  announce.

Each is set outright, whatever the shell running the tests has set, so a test is silent
and off the real save wherever it is run from.  ``paths.py``'s tests fail if a test file
does not import this.  It is not a test itself; the leading underscore keeps it apart.
"""
from __future__ import annotations

import atexit
import os
import shutil
import tempfile

FOLDER = tempfile.mkdtemp(prefix='sixthsense_test_save_')
QUIET = {
    'SIXTHSENSE_USER_DIR': FOLDER,
    'SIXTHSENSE_SILENT': '1',
    'ALSOFT_DRIVERS': 'null',
    'SDL_AUDIODRIVER': 'dummy',
    'SDL_VIDEODRIVER': 'dummy',
}
os.environ.update(QUIET)
atexit.register(shutil.rmtree, FOLDER, True)
