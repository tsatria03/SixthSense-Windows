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
- **Four keys per weapon (three for the grenade, see Decided)**, the four numbers a weapon's page reads aloud (`detail_row_text`: "Ammo capacity", "Effective range", "Damage", "Price"). Named after the weapon's own save key, in the original's style of capitals with no separators: `<W>AMMOCAPACITY`, `<W>RANGE`, `<W>DAMAGE`, `<W>PRICE`, where `<W>` is `GRENADE`, `KNIFE`, `COLT`, `SHOTGUN`, `M4`, `AK47`, `MG80` or `JAPAN` (the keys `GRENADEUSE`, `KNIFEUSE`, ... already use). All go to `save.json`, as progress.
- **When:**
  - buying a weapon in the shop (`DetailStoreController`'s buy, `store.py`), grenades included;
  - equipping one in the inventory (`inventory.py`, where a `*USE` key is switched on);
  - a new save: the grenade, the knife and the colt, beside the block that equips them (`app_delegate.py`, "a fresh install has nothing equipped", 0x52xx). That covers a first start and a save the player deleted.
  - any start: whatever an existing save owns or has equipped and has no keys for (see Decided).
- **Never read:** no code reads these keys. A test checks that editing them changes nothing the pages say or the stage uses.

## Decided
- **The shop's numbers, always** (the dev, 2026-09-25: "go ahead with the shop stats"). Where the shop and the inventory disagree (`aidocks/DIVERGENCES.md`, "The shop and the inventory disagree about the same weapons": the shotgun, M4A1, AK47, MG80 and sword), the keys hold `store.SHOP`'s, the ones `buyAction:` charges, whichever page the weapon was bought or equipped from, so a weapon's keys never change. The knife and the colt, which the shop does not sell, take `inventory.SLOTS`'s. The grenade is the same in both. So, as ammo capacity, range, damage and price:
  - grenade: no ammo capacity key (see below), 10, 150, 1000
  - knife: 0, 2, 30, 0 (inventory)
  - colt: 7, 50, 30, 0 (inventory)
  - shotgun: 10, 50, 45, 7000
  - M4A1: 25, 300, 50, 13000
  - AK47: 30, 300, 50, 15000
  - MG80: 50, 1500, 80, 45000
  - Japanese sword: 0, 3, 100, 50000

  Checked on 2026-09-25 against `DetailStoreController` (0x19334..0x19f38) and `DetailInventoryController` (0x27684..0x28622); the Python tables match. None of these is what the stage plays with: that comes from the weapon plists (the shotgun plays at 35 damage and 1000 range), so the keys are a spec sheet on both counts.

- **Saves that already own weapons are filled in on the start** (the dev, 2026-09-25: "Yes. It should if possible."). When the game starts, every weapon the save owns (`SHOTGUN`, `M4`, `AK47`, `MG80`, `JAPAN`) or has equipped (a `*USE` key at 1) and has no stats keys for yet gets its four, so an older save is complete from the first start after the change. It fills only what is missing, so a later start never rewrites them, and a hand edit stays in the file doing nothing.

- **The grenade gets three keys, not four** (the dev, 2026-09-25: "Yes."): `GRENADERANGE`, `GRENADEDAMAGE` and `GRENADEPRICE`, and no `GRENADEAMMOCAPACITY`. Its ammo capacity is the count in hand, `GRENADECOUNT`, which the game already keeps in the save and really reads (buying adds one, `store.py`, 0x1c144; throwing takes one, `stage_1_e._throw_grenade`). A copy would either be rewritten on every throw and purchase for nothing, or drift from the real count.
- **No save protection** (the dev, 2026-09-25: "I do not want the save protection"). Offered: a checksum over the progress keys, so a hand-edited save could be detected. Declined. The progress keys stay plain and trusted, as in the original: `GOLD`, `COIN`, `FIREST`, `GRENADECOUNT`, the owned weapons, `TUTORIAL` and the top scores can all be changed by hand and the game honours them. Don't propose it again unless asked. The stats keys stop only one kind of edit, the numbers a weapon's page speaks.

## Tests and docs
- A new test: a new save has the three starting weapons' keys; buying and equipping write a weapon's four (the grenade's three, and never a `GRENADEAMMOCAPACITY`); an existing save that owns weapons gets theirs on the start, and a later start leaves them as they are; editing them by hand changes nothing the page says or the stage uses.
- `aidocks/DIVERGENCES.md` (a port addition: the original writes no such keys), `platform/defaults.py`'s key list, and a changelog entry.
