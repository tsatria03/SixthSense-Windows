---
name: project_weapon_stats_in_save_plan
description: "PLANNED 2026-09-25, not built. Each weapon's four spoken stats (ammo capacity, effective range, damage, price) are written into save.json when it is bought or equipped, and the three starting weapons' in every new save; the game never reads them back, so editing them by hand does nothing. Needs [[project_save_split_plan]] first."
metadata:
  type: project
---

**Status: PLANNED, 2026-09-25.** Agreed with the dev, recorded before any code ([[feedback_record_plans_first]]), and in the todo list as unfinished. Mark it finished only once the dev says it works. Built after [[project_save_split_plan]], since it writes into `save.json`.

**The dev's request:** "You know how when you hover over a weapon, and you see there stats like ammo cap, damage, range, and price? I want those to be set in the file as well. These will do nothing when modified by hand. This makes it so people cannot cheat there saves easyly by modifying weapons that the game's human speech speaks. They will be written when a weapon has been bought and or equipped. For the 3 default weapons, those keys should already be there if the user starts a new game for example. Or if the save gets recreated if the user deletes it, and then starts a new game."

**The point:** a player who opens `save.json` sees each weapon's numbers and may try to change them. The game keeps reading its own numbers (`SHOP` in `game/store.py`, `INVENTORY` in `game/inventory.py`, the weapon plists through `WeaponControl`), so a hand edit changes nothing the game plays or says. The keys are written, never read.

## What it writes
- **Four keys per weapon**, the four numbers a weapon's page reads aloud (`detail_row_text`: "Ammo capacity", "Effective range", "Damage", "Price"). Named after the weapon's own save key, in the original's style of capitals with no separators: `<W>AMMOCAPACITY`, `<W>RANGE`, `<W>DAMAGE`, `<W>PRICE`, where `<W>` is `GRENADE`, `KNIFE`, `COLT`, `SHOTGUN`, `M4`, `AK47`, `MG80` or `JAPAN` (the keys `GRENADEUSE`, `KNIFEUSE`, ... already use). All go to `save.json`, as progress.
- **When:**
  - buying a weapon in the shop (`DetailStoreController`'s buy, `store.py`), grenades included;
  - equipping one in the inventory (`inventory.py`, where a `*USE` key is switched on);
  - a new save: the grenade, the knife and the colt, beside the block that equips them (`app_delegate.py`, "a fresh install has nothing equipped", 0x52xx). That covers a first start and a save the player deleted.
- **Never read:** no code reads these keys. A test checks that editing them changes nothing the pages say or the stage uses.

## Still to decide with the dev
- **Which numbers, where the shop and the inventory disagree.** Their tables differ for the same weapon (`aidocks/DIVERGENCES.md`, "The shop and the inventory disagree about the same weapons"): the shotgun is 10 rounds and 7,000 in the shop, 9 and 50,000 in the inventory, and the M4A1, AK47, MG80 and sword differ too. Either the numbers of the page the weapon was bought or equipped from, or one table for both.
- **Saves that already own weapons.** As asked, keys are written on buying and equipping; a weapon bought before this change would get its keys the next time it is equipped. Filling them in on the first start was not asked for.
- **The grenade's ammo capacity** is the count in hand (`GRENADECOUNT`), which changes as grenades are thrown and bought; the page reads the count at that moment.

## Tests and docs
- A new test: a new save has the three starting weapons' keys; buying and equipping write a weapon's four; editing them by hand changes nothing the page says or the stage uses.
- `aidocks/DIVERGENCES.md` (a port addition: the original writes no such keys), `platform/defaults.py`'s key list, and a changelog entry.
