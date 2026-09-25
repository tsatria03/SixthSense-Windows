"""PORT ADDITION: each weapon's spoken stats, written into save.json and never read back.

A weapon's page reads four numbers aloud: ammo capacity, effective range, damage and
price.  tsatria03 (2026-09-25) wanted them in the save too, so that a player who opens it
and changes them finds they do nothing: the game keeps reading its own numbers
(``store.SHOP``, ``inventory.SLOTS`` and the weapon plists), so a hand edit changes
nothing it plays or says.  aidocks/project_weapon_stats_in_save_plan.md has the plan.

The keys are the weapon's own save name - the one ``GRENADEUSE``, ``KNIFEUSE`` and the
rest already use - and the stat, in the original's capitals: ``SHOTGUNAMMOCAPACITY``,
``SHOTGUNRANGE``, ``SHOTGUNDAMAGE``, ``SHOTGUNPRICE``.  The numbers are always the shop's,
the ones buying charges, even where the inventory's page says otherwise; the knife and
the colt, which the shop does not sell, take the inventory's.  The grenade has no ammo
capacity key: its capacity is ``GRENADECOUNT``, the real count, already in the save.

They are written for every weapon the player owns or has equipped that has none yet, each
time ``AppDelegate.weaponHave`` runs: on every start (so a new save gets the grenade's,
the knife's and the colt's, and an older save is filled in), after buying and after
equipping.  Only missing keys are written, so a hand edit stays in the file, doing nothing.
"""
from __future__ import annotations

#: The eight weapons in slot order (``AppDelegate.haveWeapon`` and ``.useWeapon``), by
#: the name their save keys use.
NAMES = ('GRENADE', 'KNIFE', 'COLT', 'SHOTGUN', 'M4', 'AK47', 'MG80', 'JAPAN')

STATS = ('AMMOCAPACITY', 'RANGE', 'DAMAGE', 'PRICE')


def stats(name):
    """``{key: value}`` for one weapon, from the shop where it sells it, else the
    inventory; no ammo capacity for the grenade."""
    from .inventory import SLOTS
    from .store import SHOP
    shop = {item['use'][:-len('USE')]: item for item in SHOP.values()}
    slot = {item['use'][:-len('USE')]: item for item in SLOTS.values()}
    item = shop.get(name) or slot[name]
    values = {'AMMOCAPACITY': item['ammo'], 'RANGE': item['rng'],
              'DAMAGE': item['damage'], 'PRICE': item['price']}
    return {name + stat: int(values[stat]) for stat in STATS
            if not (name == 'GRENADE' and stat == 'AMMOCAPACITY')}


def fill(defaults, have, use):
    """Write the missing stats of every weapon owned (``have``) or equipped (``use``),
    both lists of '1' and '0' in slot order.  True when anything was written."""
    wrote = False
    for i, name in enumerate(NAMES):
        if not ((i < len(have) and have[i] == '1') or (i < len(use) and use[i] == '1')):
            continue
        for key, value in stats(name).items():
            if defaults.objectForKey_(key) is None:
                defaults.setInteger_forKey_(value, key)
                wrote = True
    return wrote
