"""PORT ADDITION: a trim in decibels for each sound file, to even out the recordings.

The original's WAVs were never levelled against each other: the zombies' loops peak at
full scale while a zombie's death can sit many decibels under the one before it.  Every
file the game plays, the music and the ambience included, is brought here to one
loudness, -12 LUFS, as far as a 12 dB boost goes, except that the zombies, the bosses, the
monster and the woman are never cut, only boosted, since the player listens for them
(tunmi13productions, 2026-09-28); the binary's gains then set the mix on top, as they always
have.  The files on disk are never changed.
aidocks/project_sound_trims_plan.md has why.

    MEASURED    written by tools/sound_trims.py, never by hand
    BY_EAR      written by hand after listening; one here wins over MEASURED

Every trim multiplies the sound's ``AL_GAIN`` (``oal_playback._gain``, and
``MusicPlayer._heard`` for the music and the ambience).  A source's gain
stops at its ``AL_MAX_GAIN``, 1.0 unless raised, so each sound source is given
``MAX_GAIN`` and a boost can pass 1.0; the output limiter holds the peaks.
``volume.SOUND_TRIMS_ON`` turns them all off, and F8 flips it in debug mode.
"""
from __future__ import annotations

from . import volume

#: Each sound source's ``AL_MAX_GAIN``: room for the largest boost, 12 dB (3.98).
MAX_GAIN = 4.0
#: The dev's own trims, by file name without ``.wav``.  These win over MEASURED.
BY_EAR: dict[str, float] = {
    # The bosses' approach, the loudest loops, put back over the mix instead of cut 5 and
    # 6 dB (tunmi13productions, 2026-09-28; aidocks/project_boss_loudness_plan.md).
    'zombies_boss_1_coming_cave': 3.0,
    'zombies_boss_3_coming_forest': 3.0,
    # The woman who heals you, as recorded: her thank you boosted 11 dB was far too loud
    # (tunmi13productions, 2026-09-28: "I honeslty don't think we need to boost her").
    'woman_coming_cave': 0.0,
    'woman_die': 0.0,
    'woman_thank_u_kiss': 0.0,
}

# The block between these two lines is rewritten by tools/sound_trims.py.
# ---- MEASURED begin ----
MEASURED: dict[str, float] = {
    # sfx/characters
    'woman_coming_cave': 2.0,
    'woman_die': 1.0,
    'woman_thank_u_kiss': 11.0,
    # sfx/misc
    'bgm_cave_amb': 12.0,
    'bgm_forest': 2.0,
    'bgm_forest_amb': 12.0,
    'bgm_game_complete': 4.5,
    'bgm_main_menu': 4.0,
    'bgm_start_end': 1.0,
    'effect_forest_rainng': 12.0,
    'player_breath_1': 12.0,
    'player_breath_2': 12.0,
    'player_breath_3': 12.0,
    'player_damage': 12.0,
    'player_die': 4.0,
    'ui_select': 8.0,
    'warring': 11.5,
    # sfx/monsters
    'man_coming_cave_monster': 4.0,
    'man_coming_forest_Monster': 1.0,
    'man_monster_die': 7.0,
    'man_monster_hit': 1.0,
    # sfx/weapons
    'weapon_ak_fire': 2.0,
    'weapon_ak_reload': 10.0,
    'weapon_colt_fire': 5.0,
    'weapon_colt_reload': 9.0,
    'weapon_grenade_fire': 7.0,
    'weapon_gun_att1': -2.5,
    'weapon_gun_att2': 0.5,
    'weapon_gun_nonbullets': 6.0,
    'weapon_japen_knife_att1': 1.5,
    'weapon_japen_knife_att2': 6.5,
    'weapon_japen_knife_draw': 4.5,
    'weapon_japen_knife_fire': 6.5,
    'weapon_knife_att2': 1.5,
    'weapon_knife_fire': 5.0,
    'weapon_m4_fire': 2.0,
    'weapon_m4_reload': 10.5,
    'weapon_mg80_reload': 6.5,
    'weapon_shotgun_fire': -0.5,
    'weapon_shotgun_reload': 12.0,
    # sfx/zombies/bosses
    'zombies_boss_1_damage': 11.5,
    # sfx/zombies/normal
    'zombie_10_hit_player': 3.5,
    'zombie_1_coming_cave': 1.0,
    'zombie_1_coming_forest': 5.5,
    'zombie_1_die': 9.0,
    'zombie_1_hit_player': 3.5,
    'zombie_2_coming_cave': 3.0,
    'zombie_2_coming_forest': 7.0,
    'zombie_2_damage': 5.0,
    'zombie_2_die': 8.5,
    'zombie_2_hit_player': 9.0,
    'zombie_3_coming_cave': 1.5,
    'zombie_3_coming_forest': 2.5,
    'zombie_3_die': 7.0,
    'zombie_3_hit_player': 6.0,
    'zombie_4_coming_cave': 6.0,
    'zombie_4_coming_forest': 3.5,
    'zombie_4_damage': 5.0,
    'zombie_4_die': 11.5,
    'zombie_5_coming_forest': 2.5,
    'zombie_5_die': 12.0,
    'zombie_6_coming_cave': 7.0,
    'zombie_6_coming_forest': 9.0,
    'zombie_6_damage': 3.5,
    'zombie_6_die': 12.0,
    'zombie_6_hit_player': 6.5,
    'zombie_7_coming_cave': 3.0,
    'zombie_7_coming_forest': 2.0,
    'zombie_7_damage': 1.0,
    'zombie_7_die': 6.5,
    'zombie_8_approach': 5.0,
    'zombie_8_coming_cave': 12.0,
    'zombie_8_coming_forest': 10.0,
    'zombie_8_die': 7.5,
    'zombie_8_hit_player': 7.5,
    'zombie_8_push': 1.0,
    'zombie_9_damage': 11.5,
    'zombie_9_die': 7.5,
    # speech/game
    'As the ozone': 5.5,
    'Now Loading': 4.0,
    'Welcome to': 6.0,
    'You can skip by using double tab': 4.0,
    'game over': 3.0,
    'headshot': 1.5,
    'headshot_4': -4.0,
    'hours': 6.0,
    'minutes': 3.5,
    'mission fail': 2.5,
    'mission success': 2.0,
    'mission success image': 4.0,
    'no coin': 7.5,
    'number of coins': 7.0,
    'number of greades': 6.0,
    'number of killed zombies': 5.5,
    'obtained gold': 3.5,
    'paused': 7.0,
    'score': 4.5,
    'seconds': 8.0,
    'the coin is charged after': 6.5,
    'the coin is full': 8.5,
    'top score': 5.5,
    'voice over off': 9.5,
    'voice over on': 9.0,
    'you must use earphone': 6.5,
    'zombies are coming': 5.0,
    # speech/logos
    'bitbee_1': 9.0,
    # speech/menus/main
    'Game Start Button': 8.0,
    'Inventory Button': 1.5,
    'Six Sense _ The Zombies': 6.0,
    'Store Button': 6.5,
    'Tutorial Button': 7.0,
    'Weapon shop Button': 3.5,
    'back button': 8.5,
    'buy button': 5.0,
    'continue button': 1.0,
    'main menu button': 3.0,
    'restart button': 5.5,
    'voice over off button': 10.0,
    'voice over on button': 9.5,
    # speech/menus/store
    'ammo capacity': 4.5,
    'being equipped': 3.5,
    'damage': 4.5,
    'effective range': 5.5,
    'gold is lacking': 5.0,
    'not equipped': 9.5,
    'not use': 9.5,
    'price': 6.5,
    'purchase has been completed': 3.5,
    'state': 6.5,
    'this weapon has been purchased': 7.5,
    'try button': 1.5,
    'use': 8.5,
    # speech/numbers
    'eight': 8.0,
    'five': 6.5,
    'four': 6.5,
    'nine': 4.0,
    'one': 4.5,
    'seven': 4.0,
    'six': 9.5,
    'three': 6.0,
    'two': 5.5,
    'zero': 3.5,
    # speech/tutorials
    'if an animal zombie approaches': 3.5,
    'if you make your finger 10_30': 5.0,
    'if you make your finger 12': 5.5,
    'if you make your finger 1_30': 5.0,
    'if you make your finger 3': 5.0,
    'if you make your finger 6': 5.0,
    'if you make your finger 9': 6.0,
    'if you tab the screen using three finger twice': 5.5,
    'if you tab the screen with two': 5.0,
    'stamina of zomblies increasingly': 7.5,
    'tutorial success': 7.0,
    # speech/weapons
    'AK47': 4.5,
    'AK47 button': 3.0,
    'AK47 image': 3.0,
    'Grenade button': 2.0,
    'M4A1': 4.0,
    'M4A1 button': 2.0,
    'M4A1 image': 3.0,
    'MG80 button': 2.0,
    'MG80 image': 1.5,
    'colt': 5.5,
    'colt button': 7.5,
    'colt image': 4.0,
    'grenade': 3.0,
    'grenade image': 3.5,
    'japanese sword': 3.0,
    'japanese sword button': 3.0,
    'japanese sword image': 2.5,
    'knife': 4.0,
    'knife button': 5.0,
    'knife image': 6.0,
    'shotgun': 5.0,
    'shotgun button': 0.5,
    'shotgun image': 3.0,
}
# ---- MEASURED end ----


def trim_db(name) -> float:
    """The trim for the file ``name``, or 0.0 if it has none or the trims are off."""
    if not volume.SOUND_TRIMS_ON or not name:
        return 0.0
    if name in BY_EAR:
        return float(BY_EAR[name])
    return float(MEASURED.get(name, 0.0))


def gain(name) -> float:
    """What the sound's ``AL_GAIN`` is multiplied by: exactly 1.0 with no trim."""
    db = trim_db(name)
    return volume.gain(db) if db else 1.0
