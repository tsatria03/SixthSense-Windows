"""The inventory: what you own, and which of it you carry.

    -[InventoryController ...]        0x2415c..0x26e30   the eight slots
    -[DetailInventoryController ...]  0x274a0..0x2a1c0   one slot, and Equip

Equipping writes the same ``...USE`` keys ``-[AppDelegate weaponHave]`` (0x4ee8) reads
and ``-[Stage_1_E gunChangeAction:]`` cycles through, so what is equipped here is what
the stage hands you.

The table is read out of ``-[DetailInventoryController viewDidLoad]`` (0x27632
onward), which sets it out slot by slot in code.  Its numbers do **not** agree with
the shop's for the same weapons - see ``docs/DIVERGENCES.md``; both are reproduced as
they stand.
"""
from __future__ import annotations

import logging

from ..platform.defaults import UserDefaults
from .blind_screen import BlindScreen
from .store import (SOUND_AMMO_CAPACITY, SOUND_BACK, SOUND_DAMAGE,
                    SOUND_EFFECTIVE_RANGE, SOUND_GRENADE_COUNT, SOUND_PRICE)

log = logging.getLogger('inventory')

SOUND_NOT_EQUIPPED = 351        # 0x2adb4
SOUND_BEING_EQUIPPED = 352      # 0x2acf0
SOUND_STATE = 353
SOUND_NOT_USE = 349
SOUND_USE = 350

#: weaponType -> the slot's page.  0x27664 (knife), 0x27874 (grenade),
#: 0x27b1c (colt), 0x27d42 (shotgun), 0x27f5e (M4A1), 0x28184 (AK47),
#: 0x283aa (MG80), 0x285cc (japanese sword).
SLOTS = {
    0: dict(name='Grenade', image=47, label=348, ammo=None, rng=10,
            damage=150, price=1000, use='GRENADEUSE'),
    1: dict(name='Knife', image=247, label=239, ammo=0, rng=2,
            damage=30, price=0, use='KNIFEUSE'),
    2: dict(name='Colt', image=248, label=240, ammo=7, rng=50,
            damage=30, price=0, use='COLTUSE'),
    3: dict(name='Shotgun', image=249, label=241, ammo=9, rng=50,
            damage=45, price=50000, use='SHOTGUNUSE'),
    4: dict(name='M4A1', image=250, label=242, ammo=30, rng=300,
            damage=50, price=70000, use='M4USE'),
    5: dict(name='AK47', image=251, label=243, ammo=30, rng=300,
            damage=50, price=70000, use='AK47USE'),
    6: dict(name='MG80', image=252, label=244, ammo=50, rng=1500,
            damage=80, price=10000, use='MG80USE'),
    7: dict(name='Japanese sword', image=253, label=245, ammo=0, rng=3,
            damage=80, price=150000, use='JAPANUSE'),
}


class InventoryController(BlindScreen):
    """-[InventoryController selectTapPointSoundStart] 0x25128, tapCount 0x24408.

    Nine rows: back, then the eight slots in the order the weapon wheel carries them.
    ``tapCount`` answers row 2 before its ``tbb`` (0x24452) and leaves that slot of
    the table unused, which is why the table looks as though it skips the grenade.
    """

    ROWS = (1, 2, 3, 4, 5, 6, 7, 8, 9)
    ROW_SOUND = {1: SOUND_BACK,
                 2: 348,            # Grenade button
                 3: 239,            # knife button
                 4: 240,            # colt button
                 5: 241,            # shotgun button
                 6: 242,            # M4A1 button
                 7: 243,            # AK47 button
                 8: 244,            # MG80 button
                 9: 245}            # japanese sword button
    STOP_SOUNDS = (13, 233, 348, 239, 240, 241, 242, 243, 244, 245, 246)

    #: 0x25c72, 0x25e2a ... 0x2687a - ItemNAction:'s argument to setWeaponType:.
    ROW_WEAPON = {2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 8: 6, 9: 7}

    def activate(self):
        self.StopElseSpeak()
        row = self.selectMenu
        if row == 1:
            self.goBackAction_()
        elif row in self.ROW_WEAPON:
            self.ItemAction_(self.ROW_WEAPON[row])
        return row

    # -[InventoryController Item1Action:] 0x25b90 and its seven copies
    def ItemAction_(self, weapon_type):
        self.ui_select()
        self.push('inventory_detail', weapon_type)


class DetailInventoryController(BlindScreen):
    """-[DetailInventoryController selectTapPointSoundStart] 0x296c4,
    tapCount 0x290c8.

    The same eight rows as a shop page, but the last two are *state* and *equip*
    rather than *buy* and *try*.
    """

    ROWS = (1, 2, 3, 4, 5, 6, 7, 8)
    ROW_SOUND = {1: SOUND_BACK, 7: SOUND_STATE}
    ROW_READER = {3: 'nameAmmocapacity', 4: 'nameEffectiverange',
                  5: 'nameDamage', 6: 'namePrice', 7: 'nameState'}
    STOP_SOUNDS = (13, 238, 260, 259, 349, 350, 351, 352, 353, 369,
                   255, 256, 257, 258,
                   47, 247, 248, 249, 250, 251, 252, 253)

    def __init__(self, weaponType=0, speech=None):
        BlindScreen.__init__(self, speech=speech)
        self.weaponType = weaponType
        self.viewDidLoad()

    # -[DetailInventoryController viewDidLoad] 0x274a0
    def viewDidLoad(self):
        slot = SLOTS[self.weaponType]
        self.type_image_sound = slot['image']
        self.names = slot['label']
        self.effetiverange = slot['rng']
        self.power = slot['damage']
        self.price = slot['price']
        d = UserDefaults.standardUserDefaults()
        if self.weaponType == 0:                              # 0x278dc
            self.ammocapacity = d.intForKey_('GRENADECOUNT')
        else:
            self.ammocapacity = slot['ammo']
        self.used = d.intForKey_(slot['use'])                 # 0x27820 and its copies
        self.type_ammocapacity = SOUND_AMMO_CAPACITY          # 0x2888c
        self.type_effectiverange = SOUND_EFFECTIVE_RANGE      # 0x28874
        self.type_power = SOUND_DAMAGE                        # 0x28850
        self.type_price = SOUND_PRICE                         # 0x28862
        self.selectMenu = 1                                   # 0x28aca

    def row_sound(self, row):
        if row == 2:
            return self.type_image_sound
        if row == 3:
            return (SOUND_GRENADE_COUNT if self.weaponType == 0
                    else self.type_ammocapacity)
        if row == 4:
            return self.type_effectiverange
        if row == 5:
            return self.type_power
        if row == 6:
            return self.type_price
        if row == 8:
            # 0x2acd0 / 0x2ad94: the button says what pressing it would do.
            return SOUND_NOT_USE if self.used else SOUND_USE
        return BlindScreen.row_sound(self, row)

    def activate(self):
        """0x290c8 - an if/else chain: equip, or back."""
        self.StopElseSpeak()
        row = self.selectMenu
        if row == 1:
            self.goBackAction_()
        elif row == 8:
            self.equipToggleAction_()
        return row

    def nameAmmocapacity(self, *_):
        self.app.TTSNumber_type_(self.ammocapacity, 1)

    def nameEffectiverange(self, *_):
        self.app.TTSNumber_type_(self.effetiverange, 1)

    def nameDamage(self, *_):
        self.app.TTSNumber_type_(self.power, 1)

    def namePrice(self, *_):
        self.app.TTSNumber_type_(self.price, 1)

    # -[DetailInventoryController nameState] 0x2a498
    def nameState(self, *_):
        self.play(SOUND_BEING_EQUIPPED if self.used else SOUND_NOT_EQUIPPED)

    # -[DetailInventoryController equipToggleAction:] 0x2a620
    def equipToggleAction_(self, *_):
        """Flip the slot's ``...USE`` key and say what it is now."""
        self.ui_select()
        slot = SLOTS[self.weaponType]
        d = UserDefaults.standardUserDefaults()
        self.used = 0 if d.intForKey_(slot['use']) else 1     # 0x2a6ce
        d.setObject_forKey_('1' if self.used else '0', slot['use'])
        d.synchronize()
        self.play(SOUND_BEING_EQUIPPED if self.used else SOUND_NOT_EQUIPPED)
        self.app.weaponHave()
        return self.used
