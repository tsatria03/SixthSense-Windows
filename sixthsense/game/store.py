"""The shop: its front menu, the weapon list and a weapon's own page.

    -[mainStoreController ...]    0x1c8c8..0x1ef58    the shop's front menu
    -[StoreController ...]        0x12f88..0x16cd0    the weapon list
    -[DetailStoreController ...]  0x18b20..0x1c7c4    one weapon: its stats and Buy

Gold is local - ``NSUserDefaults`` key ``GOLD``, which ``Stage_1_E`` pays into at the
end of a run - so buying a weapon works here exactly as it did on the phone.  The two
things that do not are the gold store and the coin store, which were in-app purchases,
and *Purchase all weapons*, which was the StoreKit product ``SixthSense.AllWeapon``.
Those rows are kept, because removing them would change the menu, and they say they
are unavailable (``docs/DIVERGENCES.md``).

The weapon table below is not data: ``-[DetailStoreController viewDidLoad]`` sets it
out weaponType by weaponType in code (0x192f2..0x1a0ec), and the numbers here are the
literals from those branches.
"""
from __future__ import annotations

import logging

from ..platform.defaults import UserDefaults
from .blind_screen import BlindScreen, whole

log = logging.getLogger('store')

# --------------------------------------------------------------------------- data
#: weaponType -> what the shop says and charges for it.
#:
#:   name sound   the WAV that names the weapon, played when the row is read
#:   image sound  the WAV the weapon's own page opens with
#:   key          the NSUserDefaults key that means "owned"
#:
#: 0x19318 (shotgun), 0x194da (M4A1), 0x196a8 (AK47), 0x19872 (MG80),
#: 0x19ce0 (japanese sword) and 0x19ea4 (grenade).
SHOP = {
    1: dict(name='Shotgun', image=249, label=241, ammo=10, rng=50,
            damage=45, price=7000, key='SHOTGUN', use='SHOTGUNUSE'),
    2: dict(name='M4A1', image=250, label=242, ammo=25, rng=300,
            damage=50, price=13000, key='M4', use='M4USE'),
    3: dict(name='AK47', image=251, label=243, ammo=30, rng=300,
            damage=50, price=15000, key='AK47', use='AK47USE'),
    4: dict(name='MG80', image=252, label=244, ammo=50, rng=1500,
            damage=80, price=45000, key='MG80', use='MG80USE'),
    5: dict(name='Japanese sword', image=253, label=245, ammo=0, rng=3,
            damage=100, price=50000, key='JAPAN', use='JAPANUSE'),
    0: dict(name='Grenade', image=47, label=348, ammo=None, rng=10,
            damage=150, price=1000, key='GRENADECOUNT', use='GRENADEUSE'),
}

#: 0x19b32..0x19b66 - the four WAVs that name a number on a weapon's page.
SOUND_AMMO_CAPACITY = 255
SOUND_EFFECTIVE_RANGE = 256
SOUND_DAMAGE = 257
SOUND_PRICE = 258

SOUND_BACK = 13
SOUND_GOLD_LACKING = 259            # 0x1bc28
SOUND_PURCHASED_ALREADY = 359       # 0x1bb80
SOUND_PURCHASE_COMPLETE = 260       # 0x1bf9c
SOUND_BUY_BUTTON = 238
SOUND_TRY_BUTTON = 362
SOUND_GRENADE_COUNT = 369

BACK_TEXT = 'Back, Button'


def detail_row_text(page, row, name):
    """A weapon's page, shop or inventory, for the screen reader: rows 2 to 6 are its
    picture and its four numbers, each read with its label."""
    if row == 1:
        return BACK_TEXT
    if row == 2:
        return '%s, Image' % name
    if row == 3:
        if page.weaponType == 0:
            return 'Number of grenades, %s' % whole(page.ammocapacity)
        return 'Ammo capacity, %s' % whole(page.ammocapacity)
    if row == 4:
        return 'Effective range, %s' % whole(page.effetiverange)
    if row == 5:
        return 'Damage, %s' % whole(page.power)
    if row == 6:
        return 'Price, %s' % whole(page.price)
    return ''


# ------------------------------------------------------------- the front menu
class MainStoreController(BlindScreen):
    """-[mainStoreController selectTapPointSoundStart] 0x1dce4, tapCount 0x1d970.

    Six rows, and one of them cannot be reached: ``selectMenu`` is never set to 3
    anywhere in the class, so sound 236 ``Gold shop Button`` is never played even
    though ``glodShopAction:`` and its ``tbb`` case both exist.  The same shape as
    ``MainController``'s unreachable Exit - **reproduced**, the row is not offered.
    """

    ROWS = (1, 2, 4, 5, 6)                       # 3 is the unreachable gold shop
    TITLE_SOUND = 18                             # "Store Button", as the menu row said
    ROW_SOUND = {1: SOUND_BACK,                  # 0x1dffa back button
                 2: 235,                         # 0x1e276 Weapon shop Button
                 4: 237,                         # 0x1e33c Inventory Button
                 5: 342,                         # 0x1e214 coin store button
                 6: 370}                         # 0x1df9a restore button
    STOP_SOUNDS = (13, 18, 235, 236, 237, 342, 370)     # 0x1dc88, plus the title
    TITLE_TEXT = 'Store.'
    ROW_TEXT = {1: BACK_TEXT,
                2: 'Weapon shop, Button',
                4: 'Inventory, Button',
                5: 'Coin store, Button',
                6: 'Restore, Button'}

    #: The row the gold shop would have been, kept so the tbb below reads the way the
    #: binary's does.
    GOLD_SHOP_ROW = 3

    def activate(self):
        """0x1d9c2: 04 ... six cases, 1..6."""
        self.StopElseSpeak()
        row = self.selectMenu
        if row == 1:
            self.goBackAction_()
        elif row == 2:
            self.weaponShopAction_()
        elif row == 3:
            self.glodShopAction_()
        elif row == 4:
            self.inventoryAction_()
        elif row == 5:
            self.coinShopAction_()
        elif row == 6:
            self.restoreAction_()
        return row

    # -[mainStoreController weaponShopAction:] 0x1e554
    def weaponShopAction_(self, *_):
        self.ui_select()
        self.push('store_weapons')

    # -[mainStoreController inventoryAction:] 0x1e868
    def inventoryAction_(self, *_):
        self.ui_select()
        self.push('inventory')

    # -[mainStoreController glodShopAction:] 0x1e6e0 - GoldStoreController, in-app
    # purchases.  Unreachable in the original as well; see the class docstring.
    def glodShopAction_(self, *_):
        self.ui_select()
        self.say('The gold store needs in-app purchases and is not available.')

    # -[mainStoreController coinShopAction:] 0x1e9f0 - CoinStoreController, likewise.
    def coinShopAction_(self, *_):
        self.ui_select()
        self.say('The coin store needs in-app purchases and is not available.')

    # -[mainStoreController restoreAction:] 0x1eb78 - restores StoreKit purchases.
    def restoreAction_(self, *_):
        self.ui_select()
        self.say('Restoring purchases needs the App Store and is not available.')

    # -[mainStoreController itemShopAction:] 0x1e6dc..0x1e6e0 is four bytes long: it
    # returns.  There is no item shop.
    def itemShopAction_(self, *_):
        pass


# ------------------------------------------------------------ the weapon list
class StoreController(BlindScreen):
    """-[StoreController selectTapPointSoundStart] 0x14968, tapCount 0x14310.

    Nine rows: back, the gold you have, the six weapons for sale, and the StoreKit
    bundle.  The weapon rows push ``DetailStoreController`` with the weaponType their
    ``ItemNAction:`` passes to ``setWeaponType:`` - 0x15a98 and its copies.
    """

    ROWS = (1, 2, 3, 4, 5, 6, 7, 8, 9)
    TITLE_SOUND = 235                # "Weapon shop Button"
    ROW_SOUND = {1: SOUND_BACK,      # 0x159a8 back button
                 2: 233,             # obtained gold
                 3: 241,             # shotgun button
                 4: 242,             # M4A1 button
                 5: 243,             # AK47 button
                 6: 244,             # MG80 button
                 7: 245,             # japanese sword button
                 8: 348,             # Grenade button
                 9: 366}             # Purchase all weapons change
    ROW_READER = {2: 'readgold'}
    STOP_SOUNDS = (13, 233, 235, 241, 242, 243, 244, 245, 246, 366, 261, 10, 348)
    TITLE_TEXT = 'Weapon shop.'
    ROW_TEXT = {1: BACK_TEXT,
                3: 'Shotgun, Button',
                4: 'M4A1, Button',
                5: 'AK47, Button',
                6: 'MG80, Button',
                7: 'Japanese sword, Button',
                8: 'Grenade, Button',
                9: 'Purchase all weapons, Button'}

    #: 0x15a90, 0x15c4c, ... - Item1..Item6Action's argument to setWeaponType:.
    ROW_WEAPON = {3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 8: 0}

    def activate(self):
        """0x1436a: 05 38 56 5c 62 68 6e 74 7a - nine cases, 1..9."""
        self.StopElseSpeak()
        row = self.selectMenu
        if row == 1:
            self.goBackAction_()
        elif row == 2:
            self.readgold()
        elif row in self.ROW_WEAPON:
            self.ItemAction_(self.ROW_WEAPON[row])
        elif row == 9:
            self.ItemAllAction_()
        return row

    def row_text(self, row):
        if row == 2:
            return 'Obtained gold, %s' % whole(self.app.haveGold)
        return BlindScreen.row_text(self, row)

    # -[StoreController readgold] 0x15720
    def readgold(self, *_):
        if self.screen_reader:
            self.say(self.row_text(2))
        else:
            self.app.TTSNumber_type_(self.app.haveGold, 1)
        return self.app.haveGold

    # -[StoreController reloadGold] 0x13640 - the label, which there is none of here.
    def reloadGold(self):
        pass

    # -[StoreController Item1Action:] 0x15a14 and its five copies
    def ItemAction_(self, weapon_type):
        self.ui_select()
        self.push('store_detail', weapon_type)

    # -[StoreController ItemAllAction:] 0x1647c - BuyItem:@"SixthSense.AllWeapon"
    def ItemAllAction_(self, *_):
        self.ui_select()
        self.say('Buying every weapon at once was an in-app purchase '
                 'and is not available.')


# ----------------------------------------------------------- one weapon's page
class DetailStoreController(BlindScreen):
    """-[DetailStoreController selectTapPointSoundStart] 0x1ab84, tapCount 0x1a578.

    Eight rows: back, the weapon's name, then its four numbers, then Buy and Try.
    ``tapCount`` here is an if/else chain rather than a table (0x1a5d0), and it only
    answers three of them - buy, try and back.
    """

    ROWS = (1, 2, 3, 4, 5, 6, 7, 8)
    ROW_SOUND = {1: SOUND_BACK, 7: SOUND_BUY_BUTTON, 8: SOUND_TRY_BUTTON}
    ROW_READER = {3: 'nameAmmocapacity', 4: 'nameEffectiverange',
                  5: 'nameDamage', 6: 'namePrice'}
    STOP_SOUNDS = (13, 238, 260, 259, 362, 369,
                   255, 256, 257, 258,
                   47, 249, 250, 251, 252, 253)

    def __init__(self, weaponType=1, speech=None):
        BlindScreen.__init__(self, speech=speech)
        self.weaponType = weaponType
        self.viewDidLoad()

    # -[DetailStoreController viewDidLoad] 0x190dc
    def viewDidLoad(self):
        item = SHOP[self.weaponType]
        self.type_image_sound = item['image']                 # 0x19318
        self.names = item['label']
        self.effetiverange = item['rng']
        self.power = item['damage']
        self.price = item['price']
        if self.weaponType == 0:                              # 0x19ea4, the grenade
            self.ammocapacity = self.defaults.intForKey_('GRENADECOUNT')
        else:
            self.ammocapacity = item['ammo']
        self.type_ammocapacity = SOUND_AMMO_CAPACITY          # 0x19b66
        self.type_effectiverange = SOUND_EFFECTIVE_RANGE      # 0x19b56
        self.type_power = SOUND_DAMAGE                        # 0x19b32
        self.type_price = SOUND_PRICE                         # 0x19b44
        self.selectMenu = 1                                   # 0x19b90
        self.message = ''                                     # maskLabel

    def title_sound(self):
        """A weapon's page names the weapon as it opens."""
        return self.type_image_sound

    def title_text(self):
        return '%s.' % SHOP[self.weaponType]['name']

    def row_text(self, row):
        if row == 7:
            return 'Buy, Button'
        if row == 8:
            return 'Try, Button'
        return detail_row_text(self, row, SHOP[self.weaponType]['name'])

    def row_sound(self, row):
        """Rows 2..6 name themselves with the weapon's own WAVs, 0x1afbc onward."""
        if row == 2:
            return self.type_image_sound
        if row == 3:
            # 0x1b00c: the grenade has no magazine, so its count is read as a count.
            return (SOUND_GRENADE_COUNT if self.weaponType == 0
                    else self.type_ammocapacity)
        if row == 4:
            return self.type_effectiverange
        if row == 5:
            return self.type_power
        if row == 6:
            return self.type_price
        return BlindScreen.row_sound(self, row)

    def activate(self):
        self.StopElseSpeak()
        row = self.selectMenu
        if row == 1:
            self.goBackAction_()
        elif row == 7:
            self.buyAction_()
        elif row == 8:
            self.testAction_()
        return row

    # the four number readers, 0x1b8c8..0x1b988
    def nameAmmocapacity(self, *_):
        self.app.TTSNumber_type_(self.ammocapacity, 1)

    def nameEffectiverange(self, *_):
        self.app.TTSNumber_type_(self.effetiverange, 1)

    def nameDamage(self, *_):
        self.app.TTSNumber_type_(self.power, 1)

    def namePrice(self, *_):
        self.app.TTSNumber_type_(self.price, 1)

    # -[DetailStoreController buyAction:] 0x1b9e4
    def buyAction_(self, *_):
        item = SHOP[self.weaponType]
        d = UserDefaults.standardUserDefaults()

        if self.weaponType != 0 and d.intForKey_(item['key']) != 0:   # 0x1bb58
            self.play(SOUND_PURCHASED_ALREADY)
            self.message = 'This weapon has been purchased.'
            return False

        if self.app.haveGold < self.price:                            # 0x1bbd4
            # 0x1bbee: only the self-voiced mode plays it.  With voice over off the
            # original left VoiceOver to read the label, so the screen reader says it.
            self.play(SOUND_GOLD_LACKING)
            self.message = 'Gold is lacking.'
            return False

        self.app.haveGold -= self.price                               # 0x1bd42
        d.setObject_forKey_('%d' % self.app.haveGold, 'GOLD')         # 0x1bdb8
        if self.weaponType == 0:
            # 0x1c144 `adds r3, r0, #1` - a thousand gold buys one grenade.
            count = d.intForKey_('GRENADECOUNT') + 1
            d.setObject_forKey_('%d' % count, 'GRENADECOUNT')
            self.ammocapacity = count                                 # 0x1c1b8
        else:
            d.setObject_forKey_('1', item['use'])                     # 0x1be08
            d.setObject_forKey_('1', item['key'])
        d.synchronize()
        self.play(SOUND_PURCHASE_COMPLETE)                            # 0x1bf9c
        self.message = 'Purchase has completed.'
        self.app.weaponHave()                                         # 0x1c0a8
        return True

    # -[DetailStoreController testAction:] 0x1c1c0
    def testAction_(self, *_):
        """The Try button pushes ``Stage_1_TEST``, the weapon test range, holding the
        weapon on this page (``setTestWeapon:``, 0x1c3d6; the slot for each weaponType
        is ``stage_1_test.TEST_WEAPON``).  It is the one door into the range.

        The original first refuses while VoiceOver is running, with an alert asking
        for it to be turned off (0x1c20a).  The port leaves that out: a player here
        always has a screen reader running, and the range speaks for itself."""
        from .stage_1_test import test_weapon_for
        self.StopElseSpeak()                                          # 0x1c280
        self.ui_select()                                              # 10, 0x1c2a6
        self.push('weapon_test', test_weapon_for(self.weaponType))
