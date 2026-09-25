"""``NSUserDefaults`` - JSON files in ``%APPDATA%\\SixthSense``.

The keys are the ones the binary writes, with the classes that own them:

    TUTORIAL        int    ``-[Stage_1_E viewDidLoad]``     0 until the tutorial is finished
    FIREST          int    ``-[AppDelegate didFinishLaunching]``  1 once the first 10 coins are given
    GOLD / COIN     int    ``AppDelegate.haveGold``, ``.Coin``
    COIN_TIMER      str    ``-[MainController coinTiemrControlStart]``  when the next coin started
    COIN_TIMER_START  str  "1" while a coin is counting down
    GRENADECOUNT    int    ``-[Stage_1_E MovingShot:]``     grenades in hand
    STAGE           int    ``-[MainController ...]``        highest stage unlocked
    SHOTGUN, M4, AK47, MG80, JAPAN
                    int    owned weapons, ``-[AppDelegate weaponHave]``
    GRENADEUSE, KNIFEUSE, COLTUSE, SHOTGUNUSE, M4USE, AK47USE, MG80USE, JAPANUSE
                    int    equipped weapons
    EYEMODE         int    ``AppDelegate.mode``, the voice-over row (DEFAULTEYEMODE when unset)
    TOPSCORE, TOPSCOREWEEK, WEEKTIME, NOWRANK, REVIEWCOUNT
                           the result panel's records, ``-[Stage_1_E SuccessOrFailMission]``

and the port's own: ``MENUMUSICVOLUME`` (the menu music's volume), and each weapon's
spoken stats, ``<W>AMMOCAPACITY``, ``<W>RANGE``, ``<W>DAMAGE`` and ``<W>PRICE``, written and
never read (``game/weapon_stats.py``).

``synchronize`` writes the files; the original's does the same thing.

PORT ADDITION (tsatria03, 2026-09-25): the original keeps everything in one plist.  The
port keeps it in two files, routed by key name, beside ``keys.json`` (``keymap.py``):

    save.json       progress: every key not named in SETTINGS_KEYS, which is the safe
                    place for a key added later
    settings.json   the player's preferences, SETTINGS_KEYS, written in that order

Nothing that uses ``UserDefaults`` has to know which file a key lives in.  A
``defaults.json`` from before the split is moved over by itself the first time the game
starts without a ``save.json``, and kept as ``defaults.json.old``
(aidocks/project_save_split_plan.md).

PORT ADDITION: a file that cannot be read is never written over.  It is kept as
``<file>.damaged``, and the game carries on from ``<file>.bak``, the copy before the last
write, which every ``synchronize`` keeps.
"""
from __future__ import annotations

import json
import logging
import os
import shutil

from .. import paths

log = logging.getLogger('defaults')

SAVE_FILE = 'save.json'
SETTINGS_FILE = 'settings.json'
#: The one file everything was kept in before the split, and what it becomes afterwards.
OLD_FILE = 'defaults.json'
OLD_KEPT = OLD_FILE + '.old'

#: The keys that are settings rather than progress, in the order settings.json lists them
#: (tsatria03, 2026-09-25).  A setting added later goes where it belongs in this list.
SETTINGS_KEYS = ('MASTERVOLUME', 'MENUMUSICVOLUME', 'LEVELMUSICVOLUME', 'AMBIENCEVOLUME',
                 'EYEMODE')


def _read(path):
    """The JSON object at ``path``, or None when it is missing or is not one."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            d = json.load(f)
    except FileNotFoundError:
        return None
    except Exception:
        log.exception('could not read %s', path)
        return None
    if not isinstance(d, dict):
        log.error('%s is not a save: %s', path, type(d).__name__)
        return None
    return d


class _File:
    """One JSON file of keys, with its backup, kept aside when it is damaged."""

    def __init__(self, path, order=None):
        self.path = path
        self.backup = path + '.bak'
        self.order = order          # the key order to write in; sorted by name when None
        self.d = {}
        self.recovered = False      # read from the backup, so it wants writing back
        if not os.path.exists(path):
            return                  # a new save, or one deleted to start over
        d = _read(path)
        if d is None:
            damaged = path + '.damaged'
            try:
                os.replace(path, damaged)
                log.error('%s could not be read; kept as %s', path, damaged)
            except OSError:
                log.exception('could not set the damaged %s aside', path)
            d = _read(self.backup)
            if d is not None:
                log.warning('carrying on from %s', self.backup)
                self.recovered = True
        self.d = d or {}

    def ordered(self):
        if self.order is None:
            return dict(sorted(self.d.items()))
        first = [(k, self.d[k]) for k in self.order if k in self.d]
        rest = sorted((k, v) for k, v in self.d.items() if k not in self.order)
        return dict(first + rest)

    def write(self):
        try:
            tmp = self.path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.ordered(), f, indent=1)
                f.flush()
                os.fsync(f.fileno())
            if os.path.exists(self.path):
                shutil.copyfile(self.path, self.backup)
            os.replace(tmp, self.path)
        except Exception:
            log.exception('could not write %s', self.path)


class UserDefaults:
    _instance = None

    @classmethod
    def standardUserDefaults(cls):
        if cls._instance is None:
            cls._instance = UserDefaults()
        return cls._instance

    def __init__(self):
        folder = paths.user_dir()
        self.path = os.path.join(folder, SAVE_FILE)
        self.backup = self.path + '.bak'
        moved = self._move_old_save(folder)
        self.save = _File(self.path)
        self.settings = _File(os.path.join(folder, SETTINGS_FILE), order=SETTINGS_KEYS)
        if moved is not None:
            # the settings the old file held, where settings.json does not have them yet
            for key, value in moved.items():
                self._file_for(key).d.setdefault(key, value)
        if moved is not None or self.save.recovered or self.settings.recovered:
            self.synchronize()      # or the next launch finds no save at all

    def _move_old_save(self, folder):
        """The keys of a ``defaults.json`` from before the split, when there is no
        ``save.json`` yet; None otherwise.  The old file is kept as ``defaults.json.old``,
        or, when it cannot be read, as ``defaults.json.damaged`` with its backup used."""
        old = os.path.join(folder, OLD_FILE)
        if os.path.exists(os.path.join(folder, SAVE_FILE)) or not os.path.exists(old):
            return None
        f = _File(old)              # a damaged one is set aside and its backup read here
        if os.path.exists(old):
            try:
                os.replace(old, os.path.join(folder, OLD_KEPT))
            except OSError:
                log.exception('could not keep %s as %s', old, OLD_KEPT)
        log.warning('moved %s into %s and %s', OLD_FILE, SAVE_FILE, SETTINGS_FILE)
        return dict(f.d)

    def _file_for(self, key):
        return self.settings if key in SETTINGS_KEYS else self.save

    # NSUserDefaults returns nil for a missing key and the game does
    # [[defaults objectForKey:k] intValue], which is 0 for nil.
    def objectForKey_(self, key):
        return self._file_for(key).d.get(key)

    def intForKey_(self, key):
        v = self.objectForKey_(key)
        if v is None:
            return 0
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    def stringForKey_(self, key):
        v = self.objectForKey_(key)
        return None if v is None else str(v)

    def setObject_forKey_(self, value, key):
        self._file_for(key).d[key] = value

    def setInteger_forKey_(self, value, key):
        self._file_for(key).d[key] = int(value)

    def removeObjectForKey_(self, key):
        self._file_for(key).d.pop(key, None)

    def synchronize(self):
        self.save.write()
        self.settings.write()
        return True


def standard() -> UserDefaults:
    return UserDefaults.standardUserDefaults()
