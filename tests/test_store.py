"""The shop and the inventory: rows, prices, buying and equipping.

Checked against ``-[mainStoreController ...]`` (0x1c8c8), ``-[StoreController ...]``
(0x12f88), ``-[DetailStoreController ...]`` (0x18b20), ``-[InventoryController ...]``
(0x2415c) and ``-[DetailInventoryController ...]`` (0x274a0).
"""
from __future__ import annotations

import os
import plistlib
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sixthsense import paths                                      # noqa: E402
from sixthsense.game.app_delegate import AppDelegate              # noqa: E402
from sixthsense.game.inventory import (SLOTS, DetailInventoryController,  # noqa: E402
                                       InventoryController)
from sixthsense.game.store import (SHOP, DetailStoreController,   # noqa: E402
                                   MainStoreController, StoreController)
from sixthsense.platform.defaults import UserDefaults             # noqa: E402
from sixthsense.platform.runloop import RunLoop                   # noqa: E402

OWNED = ('SHOTGUN', 'M4', 'AK47', 'MG80', 'JAPAN')
EQUIPPED = ('GRENADEUSE', 'KNIFEUSE', 'COLTUSE', 'SHOTGUNUSE',
            'M4USE', 'AK47USE', 'MG80USE', 'JAPANUSE')


class _Recorder:
    def __init__(self):
        self.said = []

    def speak(self, text, interrupt=True):
        self.said.append(text)
        return True

    def stop(self):
        pass


def _app(gold=0, grenades=0):
    d = UserDefaults.standardUserDefaults()
    for key in OWNED:
        d.removeObjectForKey_(key)
    for key in EQUIPPED:
        d.removeObjectForKey_(key)
    d.setObject_forKey_('%d' % gold, 'GOLD')
    d.setObject_forKey_('%d' % grenades, 'GRENADECOUNT')
    d.synchronize()
    app = AppDelegate.shared()
    if app.playback is None:
        app.didFinishLaunching()
    app.haveGold = gold
    app.weaponHave()
    RunLoop.main().reset()
    return app


def test_every_row_has_a_wav_behind_it():
    sl = plistlib.load(open(paths.path_for_resource('SoundList', 'plist'), 'rb'))
    for cls in (MainStoreController, StoreController, DetailStoreController,
                InventoryController, DetailInventoryController):
        for row, sound in cls.ROW_SOUND.items():
            name = sl[sound]
            assert paths.path_for_resource(name, 'wav'), \
                '%s row %d -> %d %s' % (cls.__name__, row, sound, name)


def test_the_gold_shop_row_is_unreachable():
    """selectMenu is never set to 3 anywhere in mainStoreController, so sound 236
    Gold shop Button is never played - even though glodShopAction: and its tbb case
    both exist."""
    _app()
    m = MainStoreController()
    try:
        assert m.GOLD_SHOP_ROW not in m.rows()
        assert 236 not in m.ROW_SOUND.values()
        assert hasattr(m, 'glodShopAction_'), 'the action itself should still be here'
    finally:
        m.teardown()


def test_the_shop_menu_pushes_the_two_screens_that_work():
    _app()
    m = MainStoreController(speech=_Recorder())
    try:
        m.select(2)
        m.activate()
        assert m.next_screen == ('store_weapons', None)
        m.next_screen = None
        m.select(4)
        m.activate()
        assert m.next_screen == ('inventory', None)
        m.next_screen = None
        for row in (5, 6):                       # coin store, restore purchases
            m.select(row)
            m.activate()
            assert m.next_screen is None, 'row %d pushed a screen' % row
        assert len(m.speech.said) == 2
    finally:
        m.teardown()


def test_the_weapon_list_opens_each_weapons_page():
    """0x15a90 and its copies: Item1..Item6Action pass 1, 2, 3, 4, 5 and 0."""
    _app()
    s = StoreController(speech=_Recorder())
    try:
        assert s.ROW_WEAPON == {3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 8: 0}
        s.select(3)
        s.activate()
        assert s.next_screen == ('store_detail', 1)
        s.next_screen = None
        s.select(8)
        s.activate()
        assert s.next_screen == ('store_detail', 0)      # the grenade
        s.next_screen = None
        s.select(9)                                      # buy every weapon
        s.activate()
        assert s.next_screen is None
        assert s.speech.said
    finally:
        s.teardown()


def test_a_weapon_page_reads_its_own_numbers():
    """0x19318: the shotgun is 10 rounds, 50 m, 45 damage, 7000 gold."""
    app = _app()
    p = DetailStoreController(1)
    try:
        assert (p.ammocapacity, p.effetiverange, p.power, p.price) == \
            (10, 50, 45, 7000)
        assert p.row_sound(2) == 249                    # shotgun image
        assert p.row_sound(3) == 255                    # ammo capacity
        assert p.row_sound(6) == 258                    # price
        assert p.selectMenu == 1                        # 0x19b90
    finally:
        p.teardown()
    assert app is not None


def test_the_grenade_page_counts_instead_of_a_magazine():
    """0x19ea4 reads GRENADECOUNT, and 0x1b00c reads it as a count, not a capacity."""
    _app(grenades=4)
    p = DetailStoreController(0)
    try:
        assert p.ammocapacity == 4
        assert p.row_sound(3) == 369                    # number of greades
        assert p.price == 1000
    finally:
        p.teardown()


def test_buying_a_weapon_spends_the_gold_and_equips_it():
    app = _app(gold=20000)
    p = DetailStoreController(3)                        # AK47, 15000
    d = UserDefaults.standardUserDefaults()
    try:
        assert p.buyAction_() is True
        assert app.haveGold == 5000
        assert d.intForKey_('GOLD') == 5000
        assert d.intForKey_('AK47') == 1
        assert d.intForKey_('AK47USE') == 1, 'a bought weapon is equipped, 0x1be08'
        assert app.haveWeapon[5] == '1'
        assert p.message == 'Purchase has completed.'
        # 0x1bb58: buying it again is refused, and costs nothing
        assert p.buyAction_() is False
        assert app.haveGold == 5000
        assert p.message == 'This weapon has been purchased.'
    finally:
        p.teardown()


def test_buying_without_the_gold_is_refused():
    app = _app(gold=100)
    p = DetailStoreController(4)                        # MG80, 45000
    try:
        assert p.buyAction_() is False
        assert app.haveGold == 100
        assert p.message == 'Gold is lacking.'
        assert UserDefaults.standardUserDefaults().intForKey_('MG80') == 0
    finally:
        p.teardown()


def test_a_thousand_gold_buys_one_grenade():
    """0x1c144, `adds r3, r0, #1`."""
    app = _app(gold=2500, grenades=2)
    p = DetailStoreController(0)
    d = UserDefaults.standardUserDefaults()
    try:
        assert p.buyAction_() is True
        assert d.intForKey_('GRENADECOUNT') == 3
        assert app.haveGold == 1500
        assert p.ammocapacity == 3, 'the page did not update its own count'
        assert p.buyAction_() is True                   # grenades stack
        assert d.intForKey_('GRENADECOUNT') == 4
    finally:
        p.teardown()


def test_the_try_button_wants_the_test_stage():
    """0x1c1c0 pushes Stage_1_TEST - the only way into it."""
    _app()
    p = DetailStoreController(2)
    try:
        p.select(8)
        p.activate()
        assert p.next_screen == ('weapon_test', 2)
    finally:
        p.teardown()


def test_the_inventory_lists_all_eight_slots():
    """0x25c72 .. 0x2687a: Item1..Item8Action pass 0 through 7."""
    _app()
    inv = InventoryController()
    try:
        assert inv.ROW_WEAPON == {2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 8: 6, 9: 7}
        assert len(SLOTS) == 8
        inv.select(2)
        inv.activate()
        assert inv.next_screen == ('inventory_detail', 0)
    finally:
        inv.teardown()


def test_equipping_writes_the_key_the_stage_reads():
    app = _app()
    p = DetailInventoryController(6)                    # MG80
    d = UserDefaults.standardUserDefaults()
    try:
        assert p.used == 0
        assert p.row_sound(8) == 350                    # "use"
        assert p.equipToggleAction_() == 1
        assert d.intForKey_('MG80USE') == 1
        assert app.useWeapon[6] == '1'
        assert p.row_sound(8) == 349                    # now it offers "not use"
        assert p.equipToggleAction_() == 0
        assert d.intForKey_('MG80USE') == 0
        assert app.useWeapon[6] == '0'
    finally:
        p.teardown()


def test_the_inventory_and_the_shop_disagree_about_prices():
    """Reproduced, not fixed: -[DetailInventoryController viewDidLoad] hard-codes a
    different price, and for the sword a different damage, from the shop's."""
    assert SHOP[1]['price'] == 7000 and SLOTS[3]['price'] == 50000    # shotgun
    assert SHOP[4]['price'] == 45000 and SLOTS[6]['price'] == 10000   # MG80
    assert SHOP[5]['price'] == 50000 and SLOTS[7]['price'] == 150000  # sword
    assert SHOP[5]['damage'] == 100 and SLOTS[7]['damage'] == 80
    assert SHOP[1]['ammo'] == 10 and SLOTS[3]['ammo'] == 9


def test_escape_backs_out_of_every_screen():
    _app()
    for screen in (MainStoreController(), StoreController(),
                   DetailStoreController(1), InventoryController(),
                   DetailInventoryController(0)):
        try:
            assert screen.done is False
            screen.goBackAction_()
            assert screen.done is True, screen.__class__.__name__
        finally:
            screen.teardown()


if __name__ == '__main__':
    fns = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    bad = 0
    for fn in fns:
        try:
            fn()
            print('ok    %s' % fn.__name__)
        except AssertionError as e:
            bad += 1
            print('FAIL  %s: %s' % (fn.__name__, e))
        except Exception as e:
            bad += 1
            print('ERROR %s: %r' % (fn.__name__, e))
    print('%d/%d passed' % (len(fns) - bad, len(fns)))
    sys.exit(1 if bad else 0)
