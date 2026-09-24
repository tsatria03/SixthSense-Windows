"""Checks that anchor the port to the original data files.

These do not test the port's opinions; they test that the numbers the port hard-codes
still agree with what is in `game/`, the original app bundle.  If a table here fails,
the table in the code was read wrong.

    python tests/case/data.py
"""
from __future__ import annotations

import os
import plistlib
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import _scratch_save                                             # noqa: E402,F401  never the real save

from sixthsense import paths                                        # noqa: E402
from sixthsense.game.make_maps import MakeMaps                      # noqa: E402
from sixthsense.game.monster_control import MOVING_TYPE_ANGLE, START_POS  # noqa: E402
from sixthsense.game.stage_1_e import (MONSTER_ARRAY, MONSTER_SOUNDS,  # noqa: E402
                                       SHAKE_SOUNDS, MAKE_MONSTER_TIER)
from sixthsense.game.weapon_control import (WEAPON_FILES, WEAPON_SLOTS,  # noqa: E402
                                            WeaponControl, obj_float, obj_int)


def _read(name, ext=None):
    with open(paths.path_for_resource(name, ext), 'r', encoding='utf-8',
              errors='replace') as f:
        return f.read()


def _sound_list():
    with open(paths.path_for_resource('SoundList', 'plist'), 'rb') as f:
        return plistlib.load(f)


# --------------------------------------------------------------------- map
def test_map_shape():
    m = MakeMaps().initWithMapGroundFileString_soundPosFileName_actionPosFileName_(
        _read('g_CH1_E'), _read('s_CH1_E', 'txt'), _read('a_CH1_E', 'txt'))
    assert m.height == 701
    assert m.width == 42        # 41 values + the empty component the trailing space makes
    return m


def test_map_corridor():
    m = test_map_shape()
    # ground 21 for the whole corridor, at column 20
    assert m.movePlayGroundState_PlotY_(20, 21) == 21
    assert m.movePlayGroundState_PlotY_(20, 679) == 21
    assert m.movePlayGroundState_PlotY_(20, 20) == 0
    assert m.movePlayGroundState_PlotY_(20, 680) == 0
    assert m.movePlayGroundState_PlotY_(19, 400) == 0
    # the two odd cells
    assert m.movePlayGroundState_PlotY_(20, 387) == 23
    assert m.movePlayGroundState_PlotY_(20, 388) == 23


def test_action_layer():
    m = test_map_shape()
    actions = [(y, m.movePlayActionState_PlotY_(20, y))
               for y in range(m.height)
               if m.movePlayActionState_PlotY_(20, y)]
    assert actions == [
        (22, 7), (23, 10), (29, 8), (34, 9),
        (83, 7), (88, 10), (94, 8), (99, 9),
        (184, 6), (189, 10), (195, 8), (200, 9),
        (284, 5), (289, 10), (295, 8), (300, 9),
        (384, 4), (389, 10), (395, 8), (400, 9),
        (484, 3), (489, 10), (495, 8), (500, 9),
        (585, 2), (590, 10), (596, 8), (601, 9),
        (664, 1), (669, 10), (675, 8), (680, 9),
    ]


def test_sound_layer_is_empty():
    """The shipped sound layer places nothing, which is why mapPlotSound has no work."""
    m = test_map_shape()
    assert all(c.get('V', '0') in ('0', '') for row in m.maps for c in row)


# ----------------------------------------------------------------- weapons
EXPECTED_WEAPONS = {
    # file        num dmg range rounds shot  reload shotSnd reloadSnd
    'Grenage':   (0, 150, 1600, 1, 2.0, 2.0, 57, 57),
    'Knife':     (1, 30, 200, 1, 0.5, 1.0, 58, 58),
    'Colt':      (2, 30, 1000, 7, 0.5, 2.3, 61, 62),
    'Shotgun':   (3, 35, 1000, 10, 0.5, 1.5, 63, 64),
    'M4A1':      (4, 40, 1300, 25, 0.3, 2.4, 65, 66),
    'AK47':      (5, 40, 1300, 30, 0.3, 2.3, 67, 68),
    'MG80':      (6, 45, 1600, 50, 0.4, 3.0, 69, 70),
    'Japanese':  (7, 100, 300, 1, 0.5, 1.0, 71, 71),
    'powersaw':  (8, 200, 300, 1, 1.0, 1.0, 75, 75),
}


def test_weapon_plists():
    for name, want in EXPECTED_WEAPONS.items():
        w = WeaponControl()
        w.loadWeaponForGun_fileType_(name, 'plist')
        got = (w.WeaponNumber, w.Damage, w.Range, w.BulletCount,
               round(w.ShotTime, 3), round(w.ReloadTime, 3),
               w.ShotSoundNumber, w.ReloadSoundnumber)
        assert got == want, '%s: %r != %r' % (name, got, want)


def test_weapon_quirks():
    """The three malformed values the original swallows - see aidocks/DIVERGENCES.md."""
    assert obj_float('0.2f') == 0.2          # every gun's shot gain
    assert obj_float('1,0') == 1.0           # Knife.plist index 31
    shotgun = WeaponControl()
    shotgun.loadWeaponForGun_fileType_('Shotgun', 'plist')
    assert shotgun.ReloadSoundGain == 19.0   # Shotgun.plist index 17 is "19"
    katana = WeaponControl()
    katana.loadWeaponForGun_fileType_('Japanese', 'plist')
    assert katana.att1SoundTime == 1.0       # "1.9" read with intValue


def test_weapon_slots():
    assert WEAPON_SLOTS == 8
    assert WEAPON_FILES[WEAPON_SLOTS] == 'powersaw'   # in the array, never loaded


# ---------------------------------------------------------------- monsters
def test_monster_array():
    assert len(MONSTER_ARRAY) == 50
    assert MONSTER_ARRAY[:5] == ['1', '2', '3', '4', '5']
    assert MONSTER_ARRAY[5:10] == ['11', '12', '13', '14', '15']
    assert MONSTER_ARRAY[-5:] == ['91', '92', '93', '94', '95']
    # index -> kind, lane
    for i, tid in enumerate(MONSTER_ARRAY):
        assert int(tid) % 10 == i % 5 + 1, tid


def test_monster_plists_exist_and_agree():
    """Every id the spawner can pick has a plist, and its 몬스터종류 matches the kind
    the sound tables are keyed on."""
    for i, tid in enumerate(MONSTER_ARRAY):
        p = paths.path_for_resource('type%s' % tid, 'plist')
        assert p is not None, 'type%s.plist missing' % tid
        with open(p, 'rb') as f:
            a = plistlib.load(f)
        kind_in_plist = obj_int(a[41])
        assert kind_in_plist == i // 5 + 1, \
            'type%s says kind %d, index %d implies %d' % (tid, kind_in_plist, i, i // 5 + 1)
        lane = obj_int(a[1])
        assert lane in MOVING_TYPE_ANGLE or lane % 11 == 0, \
            'type%s has MovingType %d' % (tid, lane)


def test_spawn_tiers_stay_in_range():
    for tier, (mod, off) in MAKE_MONSTER_TIER.items():
        assert 0 <= off < len(MONSTER_ARRAY)
        assert off + mod - 1 < len(MONSTER_ARRAY), \
            'tier %d can index %d' % (tier, off + mod - 1)


def test_monster_sounds_resolve_to_wavs():
    sl = _sound_list()
    missing = []
    for kind, groups in MONSTER_SOUNDS.items():
        for group in groups:
            for n in group:
                name = sl[n]
                if paths.path_for_resource(name, 'wav') is None:
                    missing.append((kind, n, name))
    for kind, groups in SHAKE_SOUNDS.items():
        for group in groups:
            for n in group:
                name = sl[n]
                if paths.path_for_resource(name, 'wav') is None:
                    missing.append((kind, n, name))
    assert not missing, 'no WAV for %r' % (missing,)


def test_start_positions_are_1000cm():
    for mt, (x, y) in START_POS.items():
        r = (x * x + y * y) ** 0.5
        assert abs(r - 1000.0) < 1.0, 'MovingType %d starts at %.1f cm' % (mt, r)


# ------------------------------------------------------------------ sounds
def test_sound_list_covers_the_wavs():
    sl = _sound_list()
    assert len(sl) == 371
    missing = sorted({n for n in sl if paths.path_for_resource(n, 'wav') is None})
    # The stage-select buttons and zombie_5_hit_player were already missing in the
    # bundle; see aidocks/DIVERGENCES.md.
    expected_missing = {'Stage %d Button' % i for i in range(1, 20)}
    expected_missing |= {'Stage is locked Clear the previous stage',
                         'Endless Mode Button', 'Endless Mode is locked',
                         'zombie_5_hit_player'}
    assert set(missing) == expected_missing, missing


def test_positional_sounds_are_mono():
    """OpenAL only spatialises mono buffers; the game relies on that split."""
    sl = _sound_list()
    positional = set()
    for groups in MONSTER_SOUNDS.values():
        for g in groups[:4]:            # coming, coming, damage, die
            positional.update(g)
    stereo = []
    for n in sorted(positional):
        p = paths.path_for_resource(sl[n], 'wav')
        if p is None:
            continue
        with wave.open(p, 'rb') as w:
            if w.getnchannels() != 1:
                stereo.append((n, sl[n]))
    assert not stereo, 'positional sound is stereo: %r' % (stereo,)


def test_every_sound_comes_from_the_sounds_folders():
    """The sounds are organized into game/sounds/used, and those the game never plays
    into game/sounds/unused (aidocks/DIVERGENCES.md), so every one the sound list names
    is found in one of the two - none is left in the top folder."""
    inside = tuple(os.path.join(paths.game(), folder, '') for folder in paths.SOUND_FOLDERS)
    for n in sorted(set(_sound_list())):
        p = paths.path_for_resource(n, 'wav')
        if p is not None:
            assert p.startswith(inside), '%s was found at %s' % (n, p)


#: The WAVs in game/sounds/unused that are not the original's own.  The sound list names
#: none of them, so searching that folder can never put one in the game.
NOT_THE_ORIGINALS = {'hurt1', 'hurt2', 'grenadereload', 'yes', 'no', 'question', 'gamestart',
                     'welcome', 'main menu'}


def test_no_sound_list_name_is_a_file_that_is_not_the_originals():
    assert not {n.lower() for n in _sound_list()} & NOT_THE_ORIGINALS


# ------------------------------------------------------------------- score
def test_score_formula():
    """-[Stage_1_E ReadScore] 0x3bf38 - the per-kind weights and the string-built
    headshot multiplier."""
    from sixthsense.game.stage_1_e import Stage_1_E
    assert Stage_1_E.headshot_multiplier(0) == 1.0
    assert Stage_1_E.headshot_multiplier(5) == 1.05
    assert Stage_1_E.headshot_multiplier(9) == 1.09
    assert Stage_1_E.headshot_multiplier(10) == 1.10
    assert Stage_1_E.headshot_multiplier(42) == 1.42
    assert Stage_1_E.headshot_multiplier(99) == 1.99
    assert Stage_1_E.headshot_multiplier(150) == 2.50
    assert Stage_1_E.headshot_multiplier(100) == 2.0

    class P:
        pass
    p = P()
    for n in list(range(1, 12)) + [5000]:
        setattr(p, 'killMonster%dcount' % n, 0)
    p.HeadShotCount = 0
    st = Stage_1_E.__new__(Stage_1_E)
    st.gamePlayer = p
    p.killMonster1count = 2      # 2 * 150
    p.killMonster9count = 1      # 1 * 300
    p.killMonster5000count = 1   # 1 * 2000
    assert st.score_now() == 300 + 300 + 2000
    p.HeadShotCount = 10         # x1.10
    assert st.score_now() == int(2600 * 1.10)


def test_the_zigzag_walks_sweep_and_turn_round():
    """-[MonsterControl MonsterMoving:] 0x1155e..0x1187c.

    Half the shipped monster types walk one of these, so this is not a corner case.
    """
    from sixthsense.game.monster_control import MonsterControl, ZIGZAG_ANGLE
    import glob
    import plistlib as _pl

    using = {}
    for path in glob.glob(os.path.join(paths.game(), 'type*.plist')):
        try:
            a = _pl.load(open(path, 'rb'))
        except Exception:
            continue
        if isinstance(a, list) and len(a) > 1:
            try:
                mt = int(str(a[1]))
            except ValueError:
                continue
            using[mt] = using.get(mt, 0) + 1
    for mt in ZIGZAG_ANGLE:
        assert using.get(mt), 'no shipped type uses MovingType %d' % mt

    for mt, ladder in ZIGZAG_ANGLE.items():
        m = MonsterControl()
        m.MovingType = mt
        walk = []
        for step in range(8):
            m.MovingCount = (step % 4) + 1
            walk.append(m._zigzag_step())
        assert walk == list(ladder) + list(reversed(ladder)), (mt, walk)
        # and a count outside 1..4 leaves the bearing where it was (0x1187c)
        m.MovingCount = 7
        assert m._zigzag_step() == walk[-1]


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
