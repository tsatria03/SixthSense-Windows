"""``NSUserDefaults`` - a JSON file in ``%APPDATA%\\SixthSense``.

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

``synchronize`` writes the file; the original's does the same thing.

PORT ADDITION: a save that cannot be read is never written over.  It is kept as
``defaults.json.damaged``, and the game carries on from ``defaults.json.bak``, the save
before the last one, which every ``synchronize`` keeps.
"""
from __future__ import annotations

import json
import logging
import os
import shutil

from .. import paths

log = logging.getLogger('defaults')


class UserDefaults:
    _instance = None

    @classmethod
    def standardUserDefaults(cls):
        if cls._instance is None:
            cls._instance = UserDefaults()
        return cls._instance

    def __init__(self):
        self.path = os.path.join(paths.user_dir(), 'defaults.json')
        self.backup = self.path + '.bak'
        self._d = {}
        if not os.path.exists(self.path):
            return                      # a new save, or one deleted to start over
        d = self._read(self.path)
        if d is None:
            damaged = self.path + '.damaged'
            try:
                os.replace(self.path, damaged)
                log.error('the save could not be read; kept as %s', damaged)
            except OSError:
                log.exception('could not set the damaged save aside')
            d = self._read(self.backup)
            if d is not None:
                log.warning('carrying on from %s', self.backup)
                self._d = d
                self.synchronize()      # or the next launch finds no save at all
                return
        self._d = d or {}

    @staticmethod
    def _read(path):
        """The save at ``path``, or None when it is missing or is not a JSON object."""
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

    # NSUserDefaults returns nil for a missing key and the game does
    # [[defaults objectForKey:k] intValue], which is 0 for nil.
    def objectForKey_(self, key):
        return self._d.get(key)

    def intForKey_(self, key):
        v = self._d.get(key)
        if v is None:
            return 0
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    def stringForKey_(self, key):
        v = self._d.get(key)
        return None if v is None else str(v)

    def setObject_forKey_(self, value, key):
        self._d[key] = value

    def setInteger_forKey_(self, value, key):
        self._d[key] = int(value)

    def removeObjectForKey_(self, key):
        self._d.pop(key, None)

    def synchronize(self):
        try:
            tmp = self.path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self._d, f, indent=1, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            if os.path.exists(self.path):
                shutil.copyfile(self.path, self.backup)
            os.replace(tmp, self.path)
        except Exception:
            log.exception('could not write %s', self.path)
        return True


def standard() -> UserDefaults:
    return UserDefaults.standardUserDefaults()
