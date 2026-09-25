"""Equipping and unequipping through the inventory's own screens.

tsatria03 unequipped every weapon from the inventory, equipped only the shotgun, and
Tab still offered the AK47 and the MG80; their save had AK47USE, MG80USE and JAPANUSE
still at 1.  These tests walk the screens the way a player does - the inventory's row
for a weapon, its page, Enter on the equip row - and print every equip key after each
step, so what the save holds can be read step by step.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import _scratch_save                                             # noqa: E402,F401  never the real save

from sixthsense.game.app_delegate import AppDelegate              # noqa: E402
from sixthsense.game.inventory import (SLOTS, DetailInventoryController,  # noqa: E402
                                       InventoryController)
from sixthsense.platform.defaults import UserDefaults             # noqa: E402
from sixthsense.platform.runloop import RunLoop                   # noqa: E402

OWNED = ('SHOTGUN', 'M4', 'AK47', 'MG80', 'JAPAN')
EQUIP_KEYS = [SLOTS[w]['use'] for w in range(8)]
NAMES = [SLOTS[w]['name'] for w in range(8)]


def _everything_owned_and_equipped():
    d = UserDefaults.standardUserDefaults()
    for key in OWNED:
        d.setObject_forKey_('1', key)
    for key in EQUIP_KEYS:
        d.setObject_forKey_('1', key)
    d.synchronize()
    app = AppDelegate.shared()
    if app.playback is None:
        app.didFinishLaunching()
    app.mode = 1
    app.weaponHave()
    RunLoop.main().reset()
    return app, d


def _keys(d):
    return ''.join('1' if d.intForKey_(k) else '0' for k in EQUIP_KEYS)


def _show(step, d):
    on = [NAMES[w] for w in range(8) if d.intForKey_(EQUIP_KEYS[w])]
    print('      %-38s %s  equipped: %s' % (step, _keys(d), ', '.join(on) or 'nothing'))


def _toggle_from_the_inventory(weapon):
    """The inventory's row for ``weapon``, Enter; its page, the equip row, Enter."""
    inv = InventoryController()
    row = next(r for r, w in InventoryController.ROW_WEAPON.items() if w == weapon)
    inv.selectMenu = row
    inv.activate()
    name, arg = inv.next_screen
    assert name == 'inventory_detail' and arg == weapon, (row, inv.next_screen)
    inv.teardown()
    page = DetailInventoryController(arg)
    page.selectMenu = 8                                 # equip / unequip
    page.activate()
    page.teardown()


def test_unequipping_each_weapon_turns_off_only_its_own_key():
    app, d = _everything_owned_and_equipped()
    print('      %-38s %s' % ('(keys, grenade to sword)', 'GKCSMAMJ'))
    _show('start', d)
    for w in range(8):
        before = _keys(d)
        _toggle_from_the_inventory(w)
        _show('unequip %s' % NAMES[w], d)
        after = _keys(d)
        if w < 7:
            want = before[:w] + '0' + before[w + 1:]
            assert after == want, 'unequipping %s: %s -> %s' % (NAMES[w], before, after)
    # 0x52xx: with nothing left equipped, the grenade, knife and colt come back
    assert _keys(d) == '11100000', _keys(d)
    assert app.useWeapon == ['1', '1', '1', '0', '0', '0', '0', '0'], app.useWeapon


def test_unequipping_all_but_the_shotgun_leaves_only_the_shotgun():
    """tsatria03's case, through the screens: every weapon unequipped but the shotgun."""
    app, d = _everything_owned_and_equipped()
    _show('start', d)
    for w in range(8):
        if w != 3:
            _toggle_from_the_inventory(w)
            _show('unequip %s' % NAMES[w], d)
    assert _keys(d) == '00010000', _keys(d)
    assert app.useWeapon == ['0', '0', '0', '1', '0', '0', '0', '0'], app.useWeapon


if __name__ == '__main__':
    fns = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    bad = 0
    for fn in fns:
        print('%s:' % fn.__name__)
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
