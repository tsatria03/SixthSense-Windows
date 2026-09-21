"""``NSUserDefaults`` - a JSON file in ``%APPDATA%\\SixthSense``.

The keys are the ones the binary writes, with the classes that own them:

    TUTORIAL        int    ``-[Stage_1_E viewDidLoad]``     0 until the tutorial is finished
    GRENADECOUNT    int    ``-[Stage_1_E MovingShot:]``     grenades in hand
    STAGE           int    ``-[MainController ...]``        highest stage unlocked
    GOLD / COIN     int    ``AppDelegate.haveGold``, ``.Coin``
    WEAPON%d        int    owned weapons, ``-[AppDelegate weaponHave]``
    USEWEAPON%d     int    equipped weapons
    VOICEOVER       int    ``AppDelegate.CheckVoiceOver``

``synchronize`` writes the file; the original's does the same thing.
"""
from __future__ import annotations

import json
import logging
import os

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
        self._d = {}
        try:
            if os.path.exists(self.path):
                with open(self.path, 'r', encoding='utf-8') as f:
                    self._d = json.load(f)
        except Exception:
            log.exception('could not read %s', self.path)
            self._d = {}

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
            os.replace(tmp, self.path)
        except Exception:
            log.exception('could not write %s', self.path)
        return True


def standard() -> UserDefaults:
    return UserDefaults.standardUserDefaults()
