"""Keep the tests off the real save.

Every test file imports this first, before any of the game: it points
``SIXTHSENSE_USER_DIR`` at a fresh folder of its own, so ``defaults.json`` and
``keys.json`` are written there and never to ``%APPDATA%\\SixthSense``, and it
deletes that folder when the run ends.  ``paths.py``'s test fails if a test file
does not import it.

It is not a test itself; the leading underscore keeps it apart from them.
"""
from __future__ import annotations

import atexit
import os
import shutil
import tempfile

FOLDER = tempfile.mkdtemp(prefix='sixthsense_test_save_')
os.environ['SIXTHSENSE_USER_DIR'] = FOLDER
atexit.register(shutil.rmtree, FOLDER, True)
