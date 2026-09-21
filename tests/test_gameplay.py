"""A headless playthrough, to check the loop actually runs.

Opens the audio device, so it needs OpenAL Soft present. Takes about a minute.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sixthsense.game.app_delegate import AppDelegate            # noqa: E402
from sixthsense.game.stage_1_e import Stage_1_E                 # noqa: E402
from sixthsense.platform.defaults import UserDefaults           # noqa: E402
from sixthsense.platform.runloop import RunLoop                 # noqa: E402

LANE = {1: 180.0, 2: 123.0, 3: 90.0, 4: 57.0, 5: 0.0}


def _new_stage():
    d = UserDefaults.standardUserDefaults()
    d.setObject_forKey_('1', 'TUTORIAL')      # -[Stage_1_E tutorialEnd:] 0x33fc8
    d.synchronize()
    app = AppDelegate.shared()
    if app.playback is None:
        app.didFinishLaunching()
    RunLoop.main().reset()
    st = Stage_1_E()
    st.viewDidLoad()
    return app, st


def _run(loop, seconds, until=None):
    t0 = time.monotonic()
    while time.monotonic() - t0 < seconds:
        loop.pump()
        if until is not None and until():
            return True
        time.sleep(0.004)
    return False


def test_player_walks_one_cell_per_second():
    _app, st = _new_stage()
    loop = RunLoop.main()
    assert st.MotionSamplingTimer is not None
    start = st.gamePlayer.playerYplot
    assert start == 680
    _run(loop, 6.0)
    walked = start - st.gamePlayer.playerYplot
    assert 4 <= walked <= 7, 'walked %d cells in 6 s' % walked
    st.teardown()


def test_monsters_spawn_one_per_lane_and_close():
    _app, st = _new_stage()
    loop = RunLoop.main()
    st.monster_num = 7                      # the hardest tier, so something spawns fast
    got = _run(loop, 30.0, until=lambda: len(st.MonsterBuffer) >= 2)
    assert got, 'no monsters after 30 s'
    lanes = [m.MovingType for m in st.MonsterBuffer]
    assert len(lanes) == len(set(lanes)), 'two monsters in one lane: %r' % lanes
    # follow one monster; taking max() over the buffer would be reset by a new spawn
    m = st.MonsterBuffer[0]
    far = m.monsterRange
    _run(loop, 6.0)
    assert m.monsterRange < far,         'the monster did not close: %.0f -> %.0f' % (far, m.monsterRange)
    st.teardown()


def test_headshot_window_opens_and_closes():
    _app, st = _new_stage()
    loop = RunLoop.main()
    st.MonsterInit_(1)
    m = st.MonsterBuffer[0]
    opened = _run(loop, 12.0, until=lambda: m.headShotFlag)
    assert opened, 'headShotFlag never went up'
    closed = _run(loop, 6.0, until=lambda: not m.headShotFlag)
    assert closed, 'headShotFlag never came down'
    st.teardown()


def test_a_shot_in_the_lane_does_damage():
    _app, st = _new_stage()
    loop = RunLoop.main()
    st.MonsterInit_(4)                      # type4: kind 1, lane 4
    m = st.MonsterBuffer[0]
    _run(loop, 1.5)                         # let it take one footstep so it has a bearing
    assert m.MovingPosAngle == 57, m.MovingPosAngle
    hp0 = m.HP
    w = st.weaponSource[st.gamePlayer.useWepon]
    st.MovingShot_(LANE[4])
    loop.pump()
    assert st.shotMonster == 4
    assert m.HP == hp0 - w.Damage or m.HP == hp0 - w.Damage * 2, \
        'HP %d -> %d with damage %d' % (hp0, m.HP, w.Damage)
    st.teardown()


def test_a_shot_in_the_wrong_lane_misses():
    _app, st = _new_stage()
    loop = RunLoop.main()
    st.MonsterInit_(4)                      # lane 4
    m = st.MonsterBuffer[0]
    _run(loop, 1.5)
    hp0 = m.HP
    st.MovingShot_(LANE[1])                 # aim hard left instead
    loop.pump()
    assert st.shotMonster == 1
    assert m.HP == hp0
    st.teardown()


def test_out_of_range_misses():
    _app, st = _new_stage()
    loop = RunLoop.main()
    st.gamePlayer.useWepon = 1              # knife: 200 cm
    st.MonsterInit_(4)
    m = st.MonsterBuffer[0]
    _run(loop, 1.5)
    hp0 = m.HP
    st.MovingShot_(LANE[4])
    loop.pump()
    assert m.HP == hp0, 'the knife reached %.0f cm' % m.monsterRange
    st.teardown()


def test_a_sound_number_is_one_voice():
    """-[AppDelegate playSoundBufNumber:] 0x6370: a sound number keeps its slot, and
    two numbers never share one."""
    app, st = _new_stage()
    i1 = app.playSoundBufNumber_(93)
    i2 = app.playSoundBufNumber_(93)
    assert i1 == i2, 'the same sound number got two slots'
    i3 = app.playSoundBufNumber_(94)
    assert i3 != i1, 'two sound numbers landed on one slot'
    assert app.aSoundBufControlData[i1].iFileNumber == 93
    assert app.aSoundBufControlData[i3].iFileNumber == 94
    st.teardown()


def test_a_freed_slot_is_reused_before_the_array_grows():
    """findBufFlagNO (0x62e8) hands back the first entry with bIsPlaying == NO, so a
    stopped sound's voice is taken over rather than a new one allocated."""
    app, st = _new_stage()
    taken = app.playSoundBufNumber_(93)
    app.stopSoundBufNumber_(93)                    # frees that slot
    assert not app.aSoundBufControlData[taken].bIsPlaying
    grown = len(app.aSoundBufControlData)
    reused = app.playSoundBufNumber_(108)          # a number not yet allocated
    assert reused == taken, 'took slot %d instead of the free %d' % (reused, taken)
    assert len(app.aSoundBufControlData) == grown, 'the array grew anyway'
    assert app.aSoundBufControlData[taken].iFileNumber == 108
    st.teardown()


def test_a_grabber_takes_hold_and_can_be_shaken_off():
    """zombie_8 has shakeMonsterFlag: at 25 cm it grabs (0x3b5ee), and ten shakes
    clear shakeFlag so shakingFind (0x3b95c) frees you and kills it."""
    _app, st = _new_stage()
    loop = RunLoop.main()
    st.MonsterInit_(71)                     # type71: kind 8, the grabber
    m = st.MonsterBuffer[0]
    assert m.shakeMonsterFlag, 'type71 is not a shake monster'
    m.monsterRange = 10.0                   # put it on top of the player
    st.MonsterAttPlayer()
    assert st.isShake, 'it did not grab'
    assert st.shakeFlag == 1
    assert st.shakeMonsterTimer is not None
    kills = st.gamePlayer.killMonsterCount
    for _ in range(10):                     # ten shakes
        st.shake_step()
    assert st.shakeFlag == 0, 'ten shakes did not clear shakeFlag'
    _run(loop, 1.0, until=lambda: not st.isShake)
    assert not st.isShake, 'shakingFind never freed the player'
    assert m not in st.MonsterBuffer, 'the grabber survived'
    assert st.gamePlayer.killMonsterCount == kills + 1
    st.teardown()


def test_a_grab_that_is_not_shaken_off_lands():
    """NonShaking (0x3b6f8) fires after shakeMonsterApproachTime and the grab hits."""
    _app, st = _new_stage()
    loop = RunLoop.main()
    st.MonsterInit_(71)
    m = st.MonsterBuffer[0]
    m.shakeMonsterApproachTime = 0.3        # do not wait the full 2.5 s
    m.monsterRange = 10.0
    st.MonsterAttPlayer()
    assert st.isShake
    hp0 = st.gamePlayer.HP
    _run(loop, 2.0, until=lambda: not st.isShake)
    assert not st.isShake, 'still held after the timer ran out'
    assert m not in st.MonsterBuffer
    assert st.gamePlayer.HP == hp0 - 1, 'the grab did no damage'
    st.teardown()


def test_check_boos_die_compares_against_gamemode_minus_two():
    """checkBoosDie (0x3604c) tests monsterNumber against gameMode - 2, which only
    ever matches in gameMode 3 - see docs/DIVERGENCES.md."""
    _app, st = _new_stage()
    assert st.checkBoosDie(), 'an empty buffer should not block the level'
    st.MonsterInit_(1)                      # kind 1
    st.gameMode = 3
    assert not st.checkBoosDie(), 'gameMode 3 should block on a kind-1 zombie'
    st.gameMode = 2
    assert st.checkBoosDie(), 'gameMode 2 compares against 0, which nothing is'
    st.gameMode = 1
    assert st.checkBoosDie(), 'gameMode 1 compares against -1'
    st.teardown()


def test_six_oclock_reloads_a_gun():
    """0x2f9e4 - a gun swiped into the gap between the bands (about 242.5..300.5,
    which is 6 o'clock) reloads instead of firing.  tutorialSix teaches it."""
    _app, st = _new_stage()
    loop = RunLoop.main()
    w = st.weaponSource[st.gamePlayer.useWepon]
    assert w.WeaponNumber not in (1, 7), 'expected a gun'
    assert st._lane_for_angle(270.0, melee=False) == 'reload'
    assert st._lane_for_angle(270.0, melee=True) == 3, 'melee should attack ahead'
    w.BulletCount = 0
    st.shotFlag = False
    st.MovingShot_(270.0)
    t0 = time.monotonic()
    while time.monotonic() - t0 < w.ReloadTime + 0.5:
        loop.pump()
        time.sleep(0.004)
    assert w.BulletCount == w.ReloadGun(), 'the 6 oclock swipe did not reload'
    st.teardown()


def test_hrtf_is_off():
    """The original had no binaural rendering - it imports only core AL/ALC and no
    ALC_ASA_* extension, and iOS OpenAL pans plain core AL in stereo.  HRTF must stay
    off or the port is somewhere the game never was."""
    app, st = _new_stage()
    assert app.playback.al.hrtf is False, 'HRTF got switched back on'
    st.teardown()


def test_weapon_cycling_only_picks_equipped():
    app, st = _new_stage()
    app.useWeapon = ['1', '1', '1', '0', '0', '0', '0', '0']
    seen = set()
    for _ in range(8):
        st.gunChangeAction_(1)
        seen.add(st.gamePlayer.useWepon)
    assert seen <= {0, 1, 2}, 'cycled onto an unequipped weapon: %r' % seen
    st.teardown()


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
