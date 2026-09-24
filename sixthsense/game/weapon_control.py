"""``WeaponControl`` - one weapon, loaded from its plist.

``-[WeaponControl loadWeaponForGun:fileType:]`` (0x220b4) reads ``<name>.plist`` with
``+[NSArray arrayWithContentsOfFile:]`` and pulls values out by *index*.  The plists are
flat label/value arrays written in Korean, so the labels are documentation and only the
odd indices are read:

     1  총 무기 번호            WeaponNumber
     3  무기 공격력             Damage
     5  유효사거리              Range          (cm)
     7  디폴트 총알수           BulletCount
     9  발사 속도               ShotSpeed
    11  무기 소리 번호          ShotSoundNumber
    13  무기 소리 크기          ShotSoundgain
    15  장전 소리 번호          ReloadSoundnumber
    17  장전 소리 크기          ReloadSoundGain
    19  무기 발사 음원시간      ShotTime
    21  무기 장전 음원 시간     ReloadTime
    23  무기 변경 소리번호      weaponChangeSoundNumber   (read as float, cast to int)
    25  무기 변경 소리 크기     weaponChangeSoundGain

and, only when ``WeaponNumber == 1`` (Knife) or the melee weapons, the attack-sound block
at 27 onwards (``att1SoundNumber``/``Gain``/``Time`` ...).

Two values in the shipped data are malformed and ``-[NSString floatValue]`` swallows them;
they are reproduced, not repaired - see aidocks/DIVERGENCES.md:

  * ``Knife.plist`` index 31 "공격 1 소리 길이" is ``"1,0"`` -> ``floatValue`` = 1.0
  * ``Shotgun.plist`` index 17 "장전 소리 크기" is ``"19"`` -> ReloadSoundGain = 19.0
  * every gun's "무기 소리 크기" is ``"0.2f"`` -> ``floatValue`` = 0.2
"""
from __future__ import annotations

import logging
import plistlib

from .. import paths

log = logging.getLogger('weapon')

# -[Stage_1_E weaponInit] 0x35008 builds this array and loads the first eight.
# 'powersaw' is the ninth entry of the array the original builds but its loop runs
# `cmp r4, 8` - so the saw is never loaded into weaponSource.  Kept as written.
WEAPON_FILES = ['Grenage', 'Knife', 'Colt', 'Shotgun', 'M4A1', 'AK47', 'MG80',
                'Japanese', 'powersaw']
WEAPON_SLOTS = 8                      # Stage_1_E.weaponSource[8]


def obj_float(v):
    """``-[NSString floatValue]``: leading numeric prefix, 0.0 when there is none."""
    if v is None:
        return 0.0
    s = str(v).strip()
    out = ''
    seen_dot = False
    for i, ch in enumerate(s):
        if ch in '+-' and i == 0:
            out += ch
        elif ch.isdigit():
            out += ch
        elif ch == '.' and not seen_dot:
            seen_dot = True
            out += ch
        else:
            break
    try:
        return float(out)
    except ValueError:
        return 0.0


def obj_int(v):
    """``-[NSString intValue]``."""
    return int(obj_float(v))


class WeaponControl:
    def __init__(self):
        self.firstFlag = False
        self.WeaponNumber = 0
        self.Damage = 0
        self.Range = 0
        self.BulletCount = 0
        self.ShotSpeed = 0.0
        self.ShotSoundNumber = 0
        self.ShotSoundgain = 0.0
        self.ReloadSoundnumber = 0
        self.ReloadSoundGain = 0.0
        self.ShotTime = 0.0
        self.ReloadTime = 0.0
        self.weaponChangeSoundNumber = 0
        self.weaponChangeSoundGain = 0.0
        self.array = None
        self.att1SoundNumber = 0
        self.att2SoundNumber = 0
        self.att3SoundNumber = 0
        self.att4SoundNumber = 0
        self.att5SoundNumber = 0
        self.att1SoundGain = 0.0
        self.att2SoundGain = 0.0
        self.att3SoundGain = 0.0
        self.att4SoundGain = 0.0
        self.att5SoundGain = 0.0
        self.att1SoundTime = 0.0
        self.att2SoundTime = 0.0
        self.att3SoundTime = 0.0
        self.att4SoundTime = 0.0
        self.att5SoundTime = 0.0

    # -[WeaponControl loadWeaponForGun:fileType:] 0x220b4
    #
    # Note how the attack block reads its gains and times: `intValue` followed by
    # `vcvt.f32.s32` (0x223f8, 0x2242c, ...), i.e. the string is parsed as an *integer*
    # and then widened to float.  Japanese.plist's "공격 1 소리 시간" of "1.9" therefore
    # becomes 1.0, and Knife.plist's "1,0" becomes 1.0 as well.  Reproduced.
    def loadWeaponForGun_fileType_(self, name, filetype='plist'):
        path = paths.path_for_resource(name, 'plist')
        if path is None:
            log.error('weapon plist missing: %s', name)
            return
        with open(path, 'rb') as f:
            a = plistlib.load(f)
        self.array = a
        if not a:
            return
        self.WeaponNumber = obj_int(a[1])
        self.Damage = obj_int(a[3])
        self.Range = obj_int(a[5])
        self.BulletCount = obj_int(a[7])
        self.ShotSpeed = obj_float(a[9])
        self.ShotSoundNumber = obj_int(a[11])
        self.ShotSoundgain = obj_float(a[13])
        self.ReloadSoundnumber = obj_int(a[15])
        self.ReloadSoundGain = obj_float(a[17])
        self.ShotTime = obj_float(a[19])
        self.ReloadTime = obj_float(a[21])
        # 0x2235a: floatValue then vcvt.s32.f32 - read as float, stored as int.
        self.weaponChangeSoundNumber = int(obj_float(a[23]))
        self.weaponChangeSoundGain = obj_float(a[25])

        # 0x223b2  cmp WeaponNumber, 1 ; bne 0x224da   -> Knife reads att1/att2 only
        # 0x224de  cmp WeaponNumber, 7 / 8            -> sword and saw read att1..att4
        if self.WeaponNumber == 1:
            self.att1SoundNumber = obj_int(a[27])
            self.att1SoundGain = float(obj_int(a[29]))
            self.att1SoundTime = float(obj_int(a[31]))
            self.att2SoundNumber = obj_int(a[33])
            self.att2SoundGain = float(obj_int(a[35]))
            self.att2SoundTime = float(obj_int(a[37]))
        elif self.WeaponNumber in (7, 8):
            self.att1SoundNumber = obj_int(a[27])
            self.att1SoundGain = float(obj_int(a[29]))
            self.att1SoundTime = float(obj_int(a[31]))
            self.att2SoundNumber = obj_int(a[33])
            self.att2SoundGain = float(obj_int(a[35]))
            self.att2SoundTime = float(obj_int(a[37]))
            self.att3SoundNumber = obj_int(a[39])
            self.att3SoundGain = float(obj_int(a[41]))
            self.att3SoundTime = float(obj_int(a[43]))
            self.att4SoundNumber = obj_int(a[45])
            self.att4SoundGain = float(obj_int(a[47]))
            self.att4SoundTime = float(obj_int(a[49]))

    # -[WeaponControl ReloadGun] 0x2274c
    #   return [[array objectAtIndex:7] intValue];
    # It only *returns* the default count; the caller assigns it, e.g.
    # -[Stage_1_E startWeapon] 0x358b4: [w setBulletCount:[w ReloadGun]].
    def ReloadGun(self):
        if not self.array:
            return 0
        return obj_int(self.array[7])

    def __repr__(self):
        return '<Weapon %d dmg=%d range=%d bullets=%d>' % (
            self.WeaponNumber, self.Damage, self.Range, self.BulletCount)
