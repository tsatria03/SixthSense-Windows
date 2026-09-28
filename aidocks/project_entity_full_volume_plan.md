---
name: project_entity_full_volume_plan
description: "PLANNED 2026-09-28. The zombies, bosses, monster and woman always play at full volume: the entity volume setting (Control+Page Up/Down, ENTITYVOLUME) is removed, and the sound trims never cut an entity sound, only boost."
metadata:
  type: project
---

**Status: planned 2026-09-28.** Follows [[project_sound_trims_plan]], [[project_boss_loudness_plan]] and [[project_gameplay_gain_plan]].

## Why
tunmi13productions, 2026-09-28, with friends: "why on earth would you want to turn down the volume of zombies? especially since you're listening for them? it's like saying I'm going to turn down the volume of someone yelling about an emergency." Then: "make zombie volume default 100. it should be 100. then remove ozmbie volume adjustment. that way it still sticks."

The entity setting already defaulted to 100 and only turned sounds down, so removing it stops a player lowering the zombies. The quiet zombies come from the trims, though: levelling to -12 LUFS cut zombie 9's approach 4 to 5.5 dB, zombie 10's 6.5 to 7, four zombies' being-hurt sounds 0.5 to 2.5, zombie 9's hit on you 3, the woman in the forest 3.5, and the bosses' hit on you 3 and death 0.5. Asked whether to stop those cuts too, the dev chose "Also stop the cuts", then "let's try 1 first. if it breaks things, we can just do a git restore and try 2" (2 being the knob alone).

## The plan
- **No entity volume.** `ENTITYVOLUME` leaves `volume.VOLUME_KEYS`, `GROUP_KEY` and `defaults.SETTINGS_KEYS`, so the entities group's gain is always 1.0. The group itself stays (`volume.ENTITIES`, `group_of`), since nothing else hangs on it.
- **Control+Page Up and Page Down do nothing in play** rather than falling through to the gain, so a player used to them changes nothing by surprise. They leave `ui/input.py`'s `VOLUME_MODIFIERS` and the F1 screen's `FIXED_IN_PLAY`.
- **An old `ENTITYVOLUME` is dropped** from settings.json when the game starts (`defaults.RETIRED_KEYS`), so a lowered value from before can't linger in the file.
- **The trims never cut an entity sound.** `tools/sound_trims.py` holds every file under `sfx/zombies`, `sfx/monsters` and `sfx/characters` at 0 where the level would cut it; boosts stay. The tool is rerun to rewrite `MEASURED`. The bosses' +3 dB in `BY_EAR` stays.
- **Left alone:** the weapons' trims, the gun's hit on a zombie (-2.5), the headshot call (-4, played at 0.2), the master volume and the gameplay gain.
- **Tests:** `gameplay_volume.py`, `volume.py`, `sound_trims.py` and `input.py` follow. **Docs:** `docks/readme.txt`, `README.md`, `aidocks/DIVERGENCES.md`, the volume docstring, [[project_gameplay_gain_plan]] and [[project_sound_trims_plan]] get a pointer, and two changelog lines.
