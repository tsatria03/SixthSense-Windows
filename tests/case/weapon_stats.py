"""Each weapon's spoken stats in save.json: written, and never read back.

A PORT ADDITION (tsatria03, 2026-09-25; aidocks/project_weapon_stats_in_save_plan.md).
The four numbers a weapon's page reads aloud - ammo capacity, range, damage and price -
are written into the save for every weapon owned or equipped: the grenade, the knife and
the colt in a new save, a bought weapon after buying, an equipped one after equipping,
and anything an older save owns on the next start.  They are the shop's numbers (the
inventory's for the knife and the colt), the grenade has no ammo capacity key, and a hand
edit changes nothing the game says or plays.

Each test runs on a new, empty save folder of its own.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import _scratch_save                                             # noqa: E402,F401  never the real save

from sixthsense import paths                                     # noqa: E402
from sixthsense.game import weapon_stats                         # noqa: E402
from sixthsense.game.app_delegate import AppDelegate             # noqa: E402
from sixthsense.game.inventory import DetailInventoryController  # noqa: E402
from sixthsense.game.store import DetailStoreController          # noqa: E402
from sixthsense.game.weapon_control import WeaponControl         # noqa: E402
from sixthsense.platform.defaults import UserDefaults            # noqa: E402
from sixthsense.platform.runloop import RunLoop                  # noqa: E402

#: as ammo capacity, range, damage and price; checked against the binary on 2026-09-25
EXPECTED = {
    'GRENADE': (None, 10, 150, 1000),
    'KNIFE': (0, 2, 30, 0),
    'COLT': (7, 50, 30, 0),
    'SHOTGUN': (10, 50, 45, 7000),
    'M4': (25, 300, 50, 13000),
    'AK47': (30, 300, 50, 15000),
    'MG80': (50, 1500, 80, 45000),
    'JAPAN': (0, 3, 100, 50000),
}


class _NewSave:
    """A new, empty save folder, with the save read from it afresh."""

    def __enter__(self):
        self.old = os.environ.get(paths.USER_DIR_ENV)
        self.top = tempfile.mkdtemp()
        os.environ[paths.USER_DIR_ENV] = os.path.join(self.top, 'SixthSense')
        UserDefaults._instance = None
        self.d = UserDefaults.standardUserDefaults()
        self.app = AppDelegate.shared()
        if self.app.playback is None:
            self.app.didFinishLaunching()
        self.app.mode = 1
        RunLoop.main().reset()
        return self

    def __exit__(self, *exc):
        if self.old is None:
            os.environ.pop(paths.USER_DIR_ENV, None)
        else:
            os.environ[paths.USER_DIR_ENV] = self.old
        UserDefaults._instance = None
        shutil.rmtree(self.top, ignore_errors=True)

    def stats(self, name):
        return tuple(self.d.objectForKey_(name + s) for s in weapon_stats.STATS)


def _as_saved(name):
    ammo, rng, damage, price = EXPECTED[name]
    return (ammo, rng, damage, price)


def test_the_numbers_are_the_shops_and_the_grenade_has_no_ammo_key():
    for name, (ammo, rng, damage, price) in EXPECTED.items():
        keys = weapon_stats.stats(name)
        want = {name + 'RANGE': rng, name + 'DAMAGE': damage, name + 'PRICE': price}
        if ammo is not None:
            want[name + 'AMMOCAPACITY'] = ammo
        assert keys == want, (name, keys)
    assert 'GRENADEAMMOCAPACITY' not in weapon_stats.stats('GRENADE')


def test_a_new_save_has_the_three_starting_weapons_stats():
    with _NewSave() as s:
        s.app.weaponHave()                     # as every start does
        for name in ('GRENADE', 'KNIFE', 'COLT'):
            assert s.stats(name) == _as_saved(name), (name, s.stats(name))
        for name in ('SHOTGUN', 'M4', 'AK47', 'MG80', 'JAPAN'):
            assert s.stats(name) == (None, None, None, None), name
        assert s.d.objectForKey_('GRENADEAMMOCAPACITY') is None


def test_they_are_in_save_json_not_settings_json():
    import json
    with _NewSave() as s:
        s.app.weaponHave()
        with open(s.d.path, encoding='utf-8') as fh:
            saved = json.load(fh)
        assert saved['COLTDAMAGE'] == 30 and saved['KNIFEPRICE'] == 0, saved


def test_buying_a_weapon_writes_its_stats():
    with _NewSave() as s:
        s.app.haveGold = 20000
        s.app.weaponHave()
        page = DetailStoreController(1)        # the shotgun
        try:
            assert page.buyAction_() is True
        finally:
            page.teardown()
        assert s.stats('SHOTGUN') == _as_saved('SHOTGUN'), s.stats('SHOTGUN')
        assert s.stats('M4') == (None, None, None, None)


def test_equipping_writes_the_shops_numbers_not_the_inventory_pages():
    """The inventory's page says the shotgun holds 9 and costs 50,000; the save holds the
    shop's 10 and 7,000, whichever page wrote it."""
    with _NewSave() as s:
        s.d.setObject_forKey_('1', 'SHOTGUN')  # bought, not equipped
        s.app.weaponHave()
        for key in weapon_stats.stats('SHOTGUN'):
            s.d.removeObjectForKey_(key)       # so only equipping can write them
        page = DetailInventoryController(3)    # the shotgun's slot
        try:
            assert page.equipToggleAction_() == 1
        finally:
            page.teardown()
        assert s.stats('SHOTGUN') == (10, 50, 45, 7000), s.stats('SHOTGUN')


def test_an_older_save_is_filled_in_on_the_next_start():
    with _NewSave() as s:
        for key in ('MG80', 'JAPAN', 'AK47USE'):
            s.d.setObject_forKey_('1', key)
        s.d.synchronize()
        s.app.weaponHave()
        for name in ('MG80', 'JAPAN', 'AK47'):
            assert s.stats(name) == _as_saved(name), name
        assert s.stats('M4') == (None, None, None, None)


def test_a_hand_edit_stays_and_changes_nothing():
    with _NewSave() as s:
        s.d.setObject_forKey_('1', 'SHOTGUN')
        s.app.weaponHave()
        for key, value in (('SHOTGUNDAMAGE', 9999), ('SHOTGUNPRICE', 1),
                           ('SHOTGUNAMMOCAPACITY', 500), ('COLTRANGE', 99999)):
            s.d.setObject_forKey_(value, key)
        s.d.synchronize()
        s.app.weaponHave()                     # the next start
        assert s.d.objectForKey_('SHOTGUNDAMAGE') == 9999, 'the edit was written over'
        shop = DetailStoreController(1)
        inv = DetailInventoryController(2)     # the colt
        try:
            assert (shop.ammocapacity, shop.effetiverange, shop.power, shop.price) \
                == (10, 50, 45, 7000), 'the shop page read the edited save'
            assert inv.effetiverange == 50, 'the inventory page read the edited save'
        finally:
            shop.teardown()
            inv.teardown()
        gun = WeaponControl()
        gun.loadWeaponForGun_fileType_('Shotgun')
        assert (gun.Damage, gun.BulletCount) == (35, 10), 'the stage would use the edit'


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
