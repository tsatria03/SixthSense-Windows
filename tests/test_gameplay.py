"""A headless playthrough, to check the loop actually runs.

Opens the audio device, so it needs OpenAL Soft present. Takes about a minute.
"""
from __future__ import annotations

import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sixthsense.game import stage_1_e as S1E                    # noqa: E402
from sixthsense.game.app_delegate import AppDelegate            # noqa: E402
from sixthsense.game.stage_1_e import Stage_1_E                 # noqa: E402
from sixthsense.platform.defaults import UserDefaults           # noqa: E402
from sixthsense.platform.runloop import RunLoop                 # noqa: E402

LANE = {1: 180.0, 2: 123.0, 3: 90.0, 4: 57.0, 5: 0.0}
_REAL_LOADING_SECONDS = S1E.LOADING_SECONDS


def _new_stage():
    S1E.LOADING_SECONDS = 0.0
    d = UserDefaults.standardUserDefaults()
    d.setObject_forKey_('1', 'TUTORIAL')      # -[Stage_1_E tutorialEnd:] 0x33fc8
    d.synchronize()
    app = AppDelegate.shared()
    if app.playback is None:
        app.didFinishLaunching()
    RunLoop.main().reset()
    st = Stage_1_E()
    st.viewDidLoad()
    RunLoop.main().pump()                     # fire the (zeroed) loading delay
    return app, st


def _run(loop, seconds, until=None):
    t0 = time.monotonic()
    while time.monotonic() - t0 < seconds:
        loop.pump()
        if until is not None and until():
            return True
        time.sleep(0.004)
    return False


def test_the_level_waits_for_now_loading_to_finish():
    """0x2d45e: the level's own ambience and music used to start the instant
    MapInitInBundle ran, talking over Now Loading (46) played just before it."""
    S1E.LOADING_SECONDS = 0.3
    d = UserDefaults.standardUserDefaults()
    d.setObject_forKey_('1', 'TUTORIAL')
    d.synchronize()
    app = AppDelegate.shared()
    if app.playback is None:
        app.didFinishLaunching()
    RunLoop.main().reset()
    played = []
    real_play = app.playSound_Gain_Pos_z_reprats_
    app.playSound_Gain_Pos_z_reprats_ = \
        lambda num, *a, **k: (played.append(num), real_play(num, *a, **k))[-1]
    st = Stage_1_E()
    try:
        st.viewDidLoad()
        assert 46 in played, 'Now Loading did not play'
        assert st.stage is None, 'the level loaded before Now Loading had time to finish'
        _run(RunLoop.main(), 0.15)
        assert st.stage is None, 'MapInitInBundle ran before LOADING_SECONDS was up'
        _run(RunLoop.main(), 0.3)
        assert st.stage is not None, 'MapInitInBundle never ran'
    finally:
        app.playSound_Gain_Pos_z_reprats_ = real_play
        st.teardown()
        S1E.LOADING_SECONDS = _REAL_LOADING_SECONDS


def test_the_menu_music_does_not_stop_before_now_loading_plays():
    """viewDidLoad used to call BGMusicStop before Now Loading ever played, so the
    menu music could cut to silence before the player heard anything.  It must
    keep playing under Now Loading and only stop once MapInitInBundle runs."""
    S1E.LOADING_SECONDS = 0.3
    d = UserDefaults.standardUserDefaults()
    d.setObject_forKey_('1', 'TUTORIAL')
    d.synchronize()
    app = AppDelegate.shared()
    if app.playback is None:
        app.didFinishLaunching()
    RunLoop.main().reset()
    stopped = []
    real_stop = app.BGMusicStop
    app.BGMusicStop = lambda: stopped.append(True) or real_stop()
    st = Stage_1_E()
    try:
        st.viewDidLoad()
        assert not stopped, 'the menu music stopped before Now Loading played'
        _run(RunLoop.main(), 0.5, until=lambda: stopped)
        assert stopped, 'the menu music never stopped'
    finally:
        app.BGMusicStop = real_stop
        st.teardown()
        S1E.LOADING_SECONDS = _REAL_LOADING_SECONDS


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
    _run(loop, S1E.SHOT_TRAVEL + 0.2)
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
    _run(loop, S1E.SHOT_TRAVEL + 0.2)
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
    _run(loop, 0.3)                         # a swing resolves 0.1 s later
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


def test_the_player_breathes_every_four_seconds():
    """MainControl breathes on every second tick, but breath: holds brearhFlag up
    for 3 s (0x31964), so every other chance is skipped: one breath per 4 s."""
    app, st = _new_stage()
    breaths = []
    real = app.playSound_Gain_Pos_z_reprats_
    app.playSound_Gain_Pos_z_reprats_ = lambda n, *a: (
        n in (80, 81, 82) and breaths.append(round(time.monotonic() - t0, 1)),
        real(n, *a))[-1]
    try:
        t0 = time.monotonic()
        _run(RunLoop.main(), 8.5)
        assert len(breaths) == 2, 'breathed at %r' % breaths
        assert 3.5 < breaths[1] - breaths[0] < 4.5, breaths
    finally:
        del app.playSound_Gain_Pos_z_reprats_
        st.teardown()


def test_shaking_free_is_heard_where_you_are():
    """PORT DIVERGENCE: the push plays at the player, not at the monster."""
    app, st = _new_stage()
    calls = []
    real = app.playSound_Gain_Pos_z_reprats_
    app.playSound_Gain_Pos_z_reprats_ = lambda n, g, pos, z, r: (
        calls.append((n, pos)), real(n, g, pos, z, r))[-1]
    try:
        st.MonsterInit_(72)
        m = st.MonsterBuffer[0]
        m.monsterRange = 10.0
        st.MonsterAttPlayer()
        for _ in range(10):
            st.shake_step()
        _run(RunLoop.main(), 1.0, until=lambda: not st.isShake)
        push = [pos for n, pos in calls if n == m.shakeMonsterPushSound]
        assert push == [(0.0, 0.0)], push
    finally:
        del app.playSound_Gain_Pos_z_reprats_
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


def test_check_boos_die_waits_for_this_levels_boss():
    """checkBoosDie (0x3604c) blocks on monsterNumber 5001 in gameModes 2 and 3
    (0x360d4) and 5000 in gameMode 1 (0x360e8) - the two bosses - and on nothing
    else."""
    _app, st = _new_stage()
    assert st.checkBoosDie(), 'an empty buffer should not block the level'
    st.MonsterInit_(1)                      # an ordinary zombie
    for mode in (1, 2, 3):
        st.gameMode = mode
        assert st.checkBoosDie(), 'gameMode %d blocked on a kind-1 zombie' % mode
    st.gameMode = 2
    st.MonsterInit_(S1E.BOSS_FOREST)
    assert st.MonsterBuffer[-1].monsterNumber == 5001
    assert not st.checkBoosDie(), 'the forest boss did not hold the level'
    st.gameMode = 1
    assert st.checkBoosDie(), 'the forest boss held the cave level'
    st.MonsterInit_(S1E.BOSS_CAVE)
    assert not st.checkBoosDie(), 'the cave boss did not hold the level'
    st.teardown()


def _step_to(st, y):
    """Put the player one cell before ``y`` and take one tick of MainControl."""
    st.gamePlayer.playerYplot = y + 1
    st.walkXFlag = False
    st.MainControl()


def test_the_alarm_then_the_boss_then_the_level_waits():
    """MainControl 0x31ab2..0x31e2e: row 29 sounds the alarm, row 23 sends the
    boss down lane 3 and stops the alarm, and at row 22 the level waits for it."""
    app, st = _new_stage()
    played, stopped = [], []
    real_play, real_stop = app.playSound_Gain_Pos_z_reprats_, app.stopSoundBufNumber_
    app.playSound_Gain_Pos_z_reprats_ = lambda n, *a: (played.append(n), real_play(n, *a))[-1]
    app.stopSoundBufNumber_ = lambda n: (stopped.append(n), real_stop(n))[-1]
    try:
        st.gameMode = 1
        _step_to(st, 29)
        assert S1E.SOUND_WARNING in played, 'no alarm at row 29'
        _step_to(st, 23)
        bosses = [m for m in st.MonsterBuffer if m.monsterNumber == 5000]
        assert bosses, 'no boss at row 23'
        assert bosses[0].MovingType == 3, 'the boss is not in the middle lane'
        assert S1E.SOUND_WARNING in stopped, 'the alarm kept playing over the boss'
        st.MainControl()                    # 23 -> 22
        st.walkXFlag = False
        st.MainControl()                    # at 22: the boss is alive
        assert st.gamePlayer.playerYplot == 22
        assert st.MotionSamplingTimer is not None, 'the level ended with the boss alive'
    finally:
        del app.playSound_Gain_Pos_z_reprats_
        del app.stopSoundBufNumber_
        st.teardown()


def test_the_level_ends_once_the_boss_is_dead():
    """0x31afc..0x31e00: every zombie left dies and is counted, the ambience
    changes at 0.3, and ChangeLevel: 2 s later loops the other level's ambience as
    a note (0x32362) and starts the walk again."""
    app, st = _new_stage()
    pb = app.playback
    amb = []
    pb.startAMBPlayer_type_soundGain_Loop_ = lambda n, t, g, l: amb.append((n, round(g, 3)))
    try:
        st.gameMode = 1
        st.MonsterInit_(1)
        st.MonsterInit_(12)
        kills = st.gamePlayer.killMonsterCount
        st.gamePlayer.playerYplot = 22
        st.walkXFlag = False
        st.MainControl()
        assert st.MonsterBuffer == [], 'zombies followed you into the next level'
        assert st.gamePlayer.killMonsterCount == kills + 2
        assert st.gameMode == 2 and st.LVUP == 2
        assert amb == [('bgm_forest_amb', 0.3)], amb
        assert st.MotionSamplingTimer is None
        _run(RunLoop.main(), 3.0, until=lambda: st.MotionSamplingTimer is not None)
        assert st.gamePlayer.playerYplot == 680, 'ChangeLevel: never ran'
        assert abs(st.monsterHPGain - 1.5) < 1e-6
        assert app.CheckSoundBuf_(S1E.SOUND_CAVE_AMB) != -1, 'no ambience note'
    finally:
        del pb.startAMBPlayer_type_soundGain_Loop_
        st.teardown()


def test_the_girls_and_the_woman_zombie():
    """10001..10005 are the girl who heals you and 10006..10010 the woman zombie
    (0x38aae), each with her own voice."""
    _app, st = _new_stage()
    st.gameMode = 1
    st.MonsterInit_(10003)
    st.MonsterInit_(10008)
    girl, woman = st.MonsterBuffer
    assert girl.monsterNumber == 21 and girl.comingSound == 267
    assert girl.playerHitSound == 270, 'reaching you is not her thank you'
    assert woman.monsterNumber == 22 and woman.comingSound == 271
    st.teardown()


def test_action_cell_8_sends_a_girl_in_a_normal_game():
    """0x320e6..0x322da: past the tutorial, cell 8 picks one of the ten at random."""
    _app, st = _new_stage()
    assert st.isTutorialEnd == 0
    st._action_girl()
    assert len(st.MonsterBuffer) == 1
    assert st.MonsterBuffer[0].monsterNumber in (21, 22)
    st.teardown()


def test_the_girl_heals_and_says_thank_you():
    """0x3b28e: reaching you, she gives a heart back and plays 270 through
    hitPlayer, not her death."""
    app, st = _new_stage()
    played = []
    real = app.playSound_Gain_Pos_z_reprats_
    app.playSound_Gain_Pos_z_reprats_ = lambda n, *a: (played.append(n), real(n, *a))[-1]
    try:
        st.MonsterInit_(10003)
        st.gamePlayer.HP = 2
        st.MonsterBuffer[0].monsterRange = 10.0
        played.clear()
        st.MonsterAttPlayer()
        assert st.gamePlayer.HP == 3
        assert 270 in played and 269 not in played, played
        assert st.MonsterBuffer == []
    finally:
        del app.playSound_Gain_Pos_z_reprats_
        st.teardown()


def test_shooting_the_girl_costs_a_heart():
    """0x3a850..0x3a97a: killing her takes a heart and is not a kill."""
    _app, st = _new_stage()
    loop = RunLoop.main()
    st.MonsterInit_(10003)                  # lane 3
    _freeze(st.MonsterBuffer[0], 100.0)
    hp0, kills = st.gamePlayer.HP, st.gamePlayer.killMonsterCount
    st.MovingShot_(LANE[3])
    _run(loop, S1E.SHOT_TRAVEL + 0.2)
    assert st.MonsterBuffer == [], 'the shot missed her'
    assert st.gamePlayer.HP == hp0 - 1, 'shooting her cost nothing'
    assert st.gamePlayer.killMonsterCount == kills, 'she counted as a kill'
    st.teardown()


def test_a_zombie_that_reaches_you_in_the_tutorial_costs_nothing():
    """0x3b2e6: a heart is only lost once isTutorial is set."""
    _app, st = _new_stage()
    st.isTutorial = 0
    st.MonsterInit_(1)
    st.MonsterBuffer[0].monsterRange = 10.0
    st.MonsterAttPlayer()
    assert st.gamePlayer.HP == 3
    st.isTutorial = 1
    st.MonsterInit_(1)
    st.MonsterBuffer[0].monsterRange = 10.0
    st.MonsterAttPlayer()
    assert st.gamePlayer.HP == 2
    st.teardown()


def test_debug_mode_takes_no_heart_and_counts_nothing():
    """--debug: a zombie still reaches you and a kill still happens, but no heart
    is lost and no kill, headshot, score or gold is counted."""
    app, st = _new_stage()
    loop = RunLoop.main()
    app.debug = True
    try:
        st.MonsterInit_(1)
        m = st.MonsterBuffer[0]
        m.monsterRange = 10.0
        st.MonsterAttPlayer()
        assert m not in st.MonsterBuffer, 'the zombie did not reach you'
        assert st.gamePlayer.HP == 3, 'a zombie took a heart'
        st.MonsterInit_(10001)              # the girl reaches you, lane 1
        girl = st.MonsterBuffer[0]
        girl.monsterRange = 10.0
        st.MonsterAttPlayer()
        assert girl not in st.MonsterBuffer, 'the girl did not reach you'
        assert st.gamePlayer.HP == 3, 'the girl gave a heart'
        st.MonsterInit_(10003)              # the girl, lane 3
        _freeze(st.MonsterBuffer[0], 100.0)
        st.MovingShot_(LANE[3])
        _run(loop, S1E.SHOT_TRAVEL + 0.2)
        assert st.MonsterBuffer == [], 'the shot missed her'
        assert st.gamePlayer.HP == 3, 'shooting her took a heart'
        st.MonsterInit_(3)                  # lane 3
        m = st.MonsterBuffer[0]
        _freeze(m, 100.0)
        m.HP = 1
        m.headShotFlag = True
        st.MovingShot_(LANE[3])
        _run(loop, S1E.SHOT_TRAVEL + 0.2)
        assert m not in st.MonsterBuffer, 'the shot missed'
        p = st.gamePlayer
        assert p.killMonsterCount == 0, 'the kill counted'
        assert p.HeadShotCount == 0, 'the headshot counted'
        assert st.ReadScore() == 0 and st.ObtainedGold() == 0
    finally:
        app.debug = False
        st.teardown()


def test_a_zombie_that_reaches_you_dies_in_debug_mode():
    """--debug: a zombie that reaches you, or a grab that lands, plays its death
    alone - no hit on you and no player_damage."""
    app, st = _new_stage()
    loop = RunLoop.main()
    app.debug = True
    played = []
    real = app.playSound_Gain_Pos_z_reprats_
    app.playSound_Gain_Pos_z_reprats_ = lambda n, *a: (played.append(n), real(n, *a))
    try:
        st.MonsterInit_(1)
        m = st.MonsterBuffer[0]
        _freeze(m, 10.0)
        played.clear()
        st.MonsterAttPlayer()
        _run(loop, 0.3)
        assert m not in st.MonsterBuffer
        assert played == [m.dieSound], played
        assert st.gamePlayer.HP == 3

        st.MonsterInit_(71)                 # the one that grabs you
        g = st.MonsterBuffer[0]
        g.shakeMonsterApproachTime = 0.3
        g.monsterRange = 10.0
        st.MonsterAttPlayer()
        assert st.isShake
        _run(loop, 2.0, until=lambda: not st.isShake)
        assert not st.isShake and g not in st.MonsterBuffer
        assert g.dieSound in played, played
        assert g.playerHitSound not in played, played
        assert S1E.SOUND_PLAYER_DAMAGE not in played, played
        assert st.gamePlayer.HP == 3
    finally:
        del app.playSound_Gain_Pos_z_reprats_
        app.debug = False
        st.teardown()


def test_the_girl_and_the_woman_keep_level_1s_speed():
    """0x38d8c / 0x39034: MonsterInit: builds the girl and the woman zombie with an
    HPGain of 1.0, so their step and health do not grow with the level.  Zombies and
    the boss do (0x37730, 0x38f68)."""
    for type_id in (10001, 10006, 1, S1E.BOSS_CAVE):
        base = {}
        for gain in (1.0, 3.375):
            _app, st = _new_stage()
            st.monsterHPGain = gain
            st.MonsterInit_(type_id)
            m = st.MonsterBuffer[0]
            base[gain] = (m.comingRange, m.HP)
            st.teardown()
        if type_id >= 10001:
            assert base[3.375] == base[1.0], '%d grew with the level: %r' % (type_id, base)
        else:
            assert base[3.375][0] > base[1.0][0], '%d did not speed up' % type_id


def test_the_debug_commands():
    """sixthsense/game/debug.py: F6 holds zombies at their range, F11 reads them out,
    F2 moves on a level."""
    from sixthsense.game import debug
    _app, st = _new_stage()
    loop = RunLoop.main()
    said = []
    st._say = said.append                   # never the real screen reader
    try:
        debug.toggle_freeze(st)
        st.debugSpawn = 2                   # zombie 3
        debug.spawn(st, 3)
        m = st.MonsterBuffer[0]
        assert m.frozen, 'a zombie spawned while frozen walks'
        start = m.monsterRange
        _run(loop, 2.5)
        assert m.monsterRange == start, 'a frozen zombie walked'
        assert debug.monsters_text(st).startswith("Zombie 3, 12 o'clock, "), said
        debug.toggle_freeze(st)
        assert not m.frozen

        assert debug.sections(st) == [680, 601, 500, 400, 300, 200, 99, 34]
        debug.spawn(st, 3)
        st.MonsterInit_(10001)              # the girl, lane 1
        girl = st.MonsterBuffer[-1]
        debug.next_section(st)
        assert st.gamePlayer.playerYplot == 601
        assert st.MonsterBuffer == [girl], 'the girl died, or a zombie lived'
        assert said[-1] == 'Section 2 of 8.', said
        st.gamePlayer.playerYplot = 30
        debug.next_section(st)
        assert st.gamePlayer.playerYplot == 30, 'went past the last section'
        assert said[-1].startswith('This is the last section'), said

        lv = st.LVUP
        debug.next_level(st)
        assert st.LVUP == lv + 1 and st.MonsterBuffer == []
        assert said[-1].startswith('Level %d, ' % (lv + 1)), said
        debug.next_level(st)                # the change has not landed yet
        assert st.LVUP == lv + 1, 'F2 skipped two levels at once'
        assert debug.monsters_text(st) == 'No zombies.'
    finally:
        st.teardown()


def test_every_spawn_attempt_resets_the_count():
    """MakeMonster: 0x3623a / 0x3625a - once LVCount reaches 3 it starts again,
    whether a zombie came of it or not."""
    _app, st = _new_stage()
    st.LVUP = 0                             # a cap of 2
    st.MonsterInit_(1)
    st.MonsterInit_(2)                      # the buffer is full
    st.LVCount = 2
    st.MakeMonster_(1)
    assert st.LVCount == 0, 'a full buffer left LVCount at %d' % st.LVCount
    st.teardown()


def test_action_cell_9_opens_a_quiet_stretch():
    """0x31e70 falls into the store at 0x31f06, so tier 9 spawns nothing until the
    section's own tier cell."""
    _app, st = _new_stage()
    st.monster_num = 3
    st.gamePlayer.playerYplot = 601         # cell 9
    st.walkXFlag = False
    st.stage.movePlayGroundState_PlotY_ = lambda x, y: 0     # stand still on it
    st.MainControl()
    assert st.monster_num == 9
    n = len(st.MonsterBuffer)
    for _ in range(6):
        st.walkXFlag = False
        st.MainControl()
    assert len(st.MonsterBuffer) == n, 'zombies came during the quiet stretch'
    st.teardown()


def test_a_new_zombie_is_in_its_lane_at_once():
    """MonsterComing: 0x1194c takes the first step straight away."""
    _app, st = _new_stage()
    st.MonsterInit_(4)
    m = st.MonsterBuffer[0]
    assert m.MovingPosAngle == 57, 'a new zombie reads as bearing %d' % m.MovingPosAngle
    st.teardown()


def _freeze(m, rng):
    """Stop a monster walking and put it ``rng`` cm out, so running the clock does
    not move it."""
    m.StopPlayGame()
    RunLoop.main().cancelPerform(m)
    m.monsterRange = rng


def _swing(st, lane, useWepon=1):
    st.gamePlayer.useWepon = useWepon
    st.shotFlag = False
    st.MovingShot_(LANE[lane])
    _run(RunLoop.main(), 0.3)


def test_the_knife_never_doubles_and_sounds_each_outcome():
    """MonsterDamageKnife 0x392fc: plain Damage even in a headshot window; att2 on a
    hit that leaves it standing, att1 on the kill, the swish only on a miss."""
    app, st = _new_stage()
    played = []
    real = app.playSound_Gain_Pos_z_reprats_
    app.playSound_Gain_Pos_z_reprats_ = lambda n, *a: (played.append(n), real(n, *a))[-1]
    try:
        knife = st.weaponSource[1]
        st.MonsterInit_(3)
        m = st.MonsterBuffer[0]
        _freeze(m, 50.0)
        m.HP = knife.Damage * 3
        m.headShotFlag = True
        played.clear()
        _swing(st, 3)
        assert m.HP == knife.Damage * 2, 'the knife did %d' % (knife.Damage * 3 - m.HP)
        assert knife.att2SoundNumber in played and knife.ShotSoundNumber not in played
        played.clear()
        m.HP = knife.Damage
        _swing(st, 3)
        assert m not in st.MonsterBuffer
        assert knife.att1SoundNumber in played, played
        played.clear()
        _swing(st, 1)
        assert knife.ShotSoundNumber in played, played
        assert knife.att1SoundNumber not in played and knife.att2SoundNumber not in played
    finally:
        del app.playSound_Gain_Pos_z_reprats_
        st.teardown()


def test_two_zombies_at_once_and_the_grabber_is_the_one_held():
    """MonsterAttPlayer defers its removals (0x3b44e), so the zombie that grabs
    is the one freed and killed, even when another hit you on the same tick."""
    _app, st = _new_stage()
    loop = RunLoop.main()
    st.MonsterInit_(1)                      # an ordinary zombie, first in the list
    st.MonsterInit_(72)                     # the grabber
    plain, grabber = st.MonsterBuffer
    assert grabber.shakeMonsterFlag
    plain.monsterRange = grabber.monsterRange = 10.0
    st.MonsterAttPlayer()
    assert st.isShake
    assert plain not in st.MonsterBuffer
    for _ in range(10):
        st.shake_step()
    _run(loop, 1.0, until=lambda: not st.isShake)
    assert grabber not in st.MonsterBuffer, 'the grabber survived'
    st.teardown()


def test_the_shake_count_carries_over():
    """Nothing that clears shakeCount is ever called (0x323d8, 0x324f8), so after
    one escape the next grab breaks on the first shake."""
    _app, st = _new_stage()
    loop = RunLoop.main()
    for _ in range(2):
        st.MonsterInit_(72)
        st.MonsterBuffer[-1].monsterRange = 10.0
        st.MonsterAttPlayer()
        assert st.isShake
        st.shake_step()
        if st.shakeCount < 10:
            for _ in range(9):
                st.shake_step()
        _run(loop, 1.0, until=lambda: not st.isShake)
        assert not st.isShake
    assert st.shakeCount == 11, st.shakeCount
    st.teardown()


def test_kill_tallies():
    """MonsterKillCount: 0x3a04c counts the woman zombie (22) as kind 11; kind 11
    itself is not tallied."""
    _app, st = _new_stage()

    class M:
        pass
    for n, attr in ((22, 'killMonster11count'), (5001, 'killMonster5000count'),
                    (4, 'killMonster4count')):
        m = M()
        m.monsterNumber = n
        before = getattr(st.gamePlayer, attr)
        st.MonsterKillCount_(m)
        assert getattr(st.gamePlayer, attr) == before + 1, n
    m = M()
    m.monsterNumber = 11
    before = st.gamePlayer.killMonster11count
    st.MonsterKillCount_(m)
    assert st.gamePlayer.killMonster11count == before
    st.teardown()


def test_the_sword_is_drawn_with_its_own_sound():
    """gunChangeAction: 0x35eac plays 329 on the sword."""
    app, st = _new_stage()
    played = []
    real = app.playSound_Gain_Pos_z_reprats_
    app.playSound_Gain_Pos_z_reprats_ = lambda n, *a: (played.append(n), real(n, *a))[-1]
    try:
        app.useWeapon = ['0'] * 8
        app.useWeapon[2] = app.useWeapon[7] = '1'
        st.gamePlayer.useWepon = 2
        st.gunChangeAction_(1)
        assert st.gamePlayer.useWepon == 7
        assert S1E.SOUND_SWORD_START in played
    finally:
        del app.playSound_Gain_Pos_z_reprats_
        st.teardown()


def test_a_shot_goes_off_down_its_lane():
    """PORT DIVERGENCE: the shot is placed along the lane's bearing, 40 cm out."""
    app, st = _new_stage()
    calls = []
    real = app.playSound_Gain_Pos_z_reprats_
    app.playSound_Gain_Pos_z_reprats_ = lambda n, g, pos, z, r: (
        calls.append((n, pos, z)), real(n, g, pos, z, r))[-1]
    try:
        w = st.weaponSource[st.gamePlayer.useWepon]
        for lane, bearing in LANE.items():
            calls.clear()
            st.shotFlag = False
            st.MovingShot_(LANE[lane])
            shot = [c for c in calls if c[0] == w.ShotSoundNumber]
            assert shot, 'lane %d fired nothing' % lane
            (x, y), z = shot[0][1], shot[0][2]
            got = math.degrees(math.atan2(y, x)) % 360.0
            assert abs(got - bearing) < 0.5 and z == 0, (lane, x, y, z)
    finally:
        del app.playSound_Gain_Pos_z_reprats_
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


def _gun_stage():
    app, st = _new_stage()
    st.gamePlayer.useWepon = 2              # the colt
    w = st.weaponSource[2]
    st.shotFlag = False
    return app, st, w


def test_a_two_window_zombie_opens_both_windows_every_cycle():
    """MonsterComing: (0x11a18..0x11ad8) starts the list "0.3,1.3" only while
    headShotTimer is nil, and headShot: (0x11b30) sets it back to nil as it fires, so
    both windows open again in every cycle, each lasting headShotTimeEndHowLong."""
    _app, st = _new_stage()
    loop = RunLoop.main()
    st.MonsterInit_(73)                     # "0.3,1.3", comingSoundTime 1.88
    m = st.MonsterBuffer[0]
    assert [float(t) for t in m.monsterHeadShotArray] == [0.3, 1.3]
    m.comingRange = 0                       # keep it out there; only its timers run
    st.MotionSamplingTimer.invalidate()     # and nothing reaches you meanwhile
    t0 = time.monotonic()
    opens, closes, was = [], [], m.headShotFlag
    while time.monotonic() - t0 < 3.9:
        loop.pump()
        now = m.headShotFlag
        if now != was:
            (opens if now else closes).append(time.monotonic() - t0)
            was = now
        time.sleep(0.002)
    cycle = m.comingSoundTime
    want = [0.3, 1.3, cycle + 0.3, cycle + 1.3]
    assert len(opens) == 4, 'windows opened at %r' % opens
    for got, exp in zip(opens, want):
        assert abs(got - exp) < 0.08, 'windows opened at %r, wanted %r' % (opens, want)
    for o, c in zip(opens, closes):
        assert abs((c - o) - m.headShotTimeEndHowLong) < 0.08, (opens, closes)
    st.teardown()


def test_a_shot_lands_half_a_second_later():
    """MovingShot: 0x2fd70 - MonsterDamage comes 0.5 s after the shot, for every gun."""
    _app, st, w = _gun_stage()
    loop = RunLoop.main()
    st.MonsterInit_(3)
    m = st.MonsterBuffer[0]
    _freeze(m, 100.0)
    hp0 = m.HP
    st.MovingShot_(LANE[3])
    _run(loop, S1E.SHOT_TRAVEL - 0.25)
    assert m.HP == hp0, 'the hit landed before the shot got there'
    _run(loop, 0.5)
    assert m.HP < hp0, 'the shot never landed'
    st.teardown()


def test_a_headshot_is_judged_when_you_fire():
    """0x2fc0e..0x2fc48: the breathing gap at the trigger decides the headshot, even
    if it has closed by the time the shot lands."""
    _app, st, w = _gun_stage()
    loop = RunLoop.main()
    st.MonsterInit_(3)
    m = st.MonsterBuffer[0]
    _freeze(m, 100.0)
    m.HP = w.Damage * 10
    m.headShotFlag = True
    st.MovingShot_(LANE[3])
    m.headShotFlag = False                  # the gap closes in flight
    _run(loop, S1E.SHOT_TRAVEL + 0.2)
    assert m.HP == w.Damage * 8, 'not a headshot: %d damage' % (w.Damage * 10 - m.HP)
    assert st.gamePlayer.HeadShotCount == 1
    st.teardown()


def test_no_firing_while_reloading():
    """GunReloadAction: leaves shotFlag up until reloadGun: (0x35f24) drops it, so
    a shot fired during the reload does nothing and wastes nothing."""
    _app, st, w = _gun_stage()
    loop = RunLoop.main()
    w.BulletCount = 1
    assert st.ReloadGesture()
    st.MovingShot_(LANE[3])
    assert w.BulletCount == 1, 'a round was fired during the reload'
    _run(loop, w.ReloadTime + 0.3)
    assert w.BulletCount == w.ReloadGun()
    assert st.shotFlag is False, 'firing is still barred after the reload'
    st.teardown()


def test_no_reload_while_grabbed_dying_or_mid_shot():
    """The reload key goes through MovingShot:'s guards, like the 6 o'clock swipe."""
    app, st, w = _gun_stage()
    reloads = []
    real = st.GunReloadAction_
    st.GunReloadAction_ = lambda *a: (reloads.append(1), real(*a))[-1]
    try:
        st.isShake = True
        assert not st.ReloadGesture(), 'reloaded while held'
        st.isShake = False
        st.missionCompletSounding = True
        assert not st.ReloadGesture(), 'reloaded once the game was over'
        st.missionCompletSounding = False
        st.shotFlag = True
        assert not st.ReloadGesture(), 'reloaded in the middle of a shot'
        st.shotFlag = False
        assert reloads == []
    finally:
        del st.GunReloadAction_
        st.teardown()


def test_reload_does_nothing_with_the_grenade_or_a_blade():
    """GunReloadAction: returns for the grenade (0x351c8), and a blade has no
    magazine; the port used to play the grenade's blast."""
    app, st, w = _gun_stage()
    played = []
    real = app.playSound_Gain_Pos_z_reprats_
    app.playSound_Gain_Pos_z_reprats_ = lambda n, *a: (played.append(n), real(n, *a))[-1]
    try:
        for weapon in (0, 1):
            st.gamePlayer.useWepon = weapon
            st.shotFlag = False
            assert not st.ReloadGesture()
            assert st.shotFlag is False
        assert played == [], played
    finally:
        del app.playSound_Gain_Pos_z_reprats_
        st.teardown()


def test_a_reload_refills_the_gun_it_was_started_with():
    """reloadGun: refills weaponSource[reloadWeaponNumber] (0x35f2a)."""
    app, st, colt = _gun_stage()
    loop = RunLoop.main()
    colt.BulletCount = 0
    st.ReloadGesture()
    app.useWeapon = ['1'] * 8
    st.gunChangeAction_(1)                  # switch away mid-reload
    other = st.weaponSource[st.gamePlayer.useWepon]
    other.BulletCount = 0
    _run(loop, colt.ReloadTime + 0.3)
    assert colt.BulletCount == colt.ReloadGun(), 'the colt was not refilled'
    assert other.BulletCount == 0, 'the gun switched to was refilled instead'
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


def test_switching_weapons_keeps_each_magazine():
    """gunChangeAction: (0x35a08) never calls ReloadGun: each weapon keeps its rounds."""
    app, st = _new_stage()
    app.useWeapon = ['1', '1', '1', '0', '0', '0', '0', '0']
    st.gamePlayer.useWepon = 2
    w = st.weaponSource[2]
    w.BulletCount = 1
    st.gunChangeAction_(1)
    assert st.gamePlayer.useWepon != 2, 'the weapon did not change'
    for _ in range(8):                      # round the equipped three, back to 2
        if st.gamePlayer.useWepon == 2:
            break
        st.gunChangeAction_(1)
    assert st.gamePlayer.useWepon == 2
    assert w.BulletCount == 1, 'switching weapons refilled the magazine'
    st.teardown()


def test_the_ambience_is_quiet_and_the_rain_is_ambience():
    """MapInitInBundle 0x2dd96..0x2de10: gameMode 3 plays the rain alone, on the
    ambience player, at 0.5 (0x3f000000); the forest and the cave play their ambience
    at 0.2 (0x3e4ccccd).  Nothing starts on the music player."""
    app, st = _new_stage()
    pb = app.playback
    calls = []
    pb.startAMBPlayer_type_soundGain_Loop_ = lambda n, t, g, l: calls.append(('amb', n, g))
    pb.startBGPlayer_type_soundGain_Loop_ = lambda n, t, g, l: calls.append(('bg', n, g))
    try:
        for mode, want in ((3, [('amb', 'effect_forest_rainng', 0.5)]),
                           (2, [('amb', 'bgm_forest_amb', 0.2)]),
                           (1, [('amb', 'bgm_cave_amb', 0.2)])):
            calls.clear()
            st.gameMode = mode
            st.MapInitInBundle()
            assert calls == want, 'gameMode %d played %r' % (mode, calls)
    finally:
        del pb.startAMBPlayer_type_soundGain_Loop_      # back to the real players
        del pb.startBGPlayer_type_soundGain_Loop_
        st.teardown()


def test_leaving_a_stage_silences_it():
    """teardown stops each monster's walking loop, the ambience and the music, or
    they play on under the menu after Escape."""
    app, st = _new_stage()
    pb = app.playback
    stopped = []
    pb.AMBSoundStop = lambda: stopped.append('ambience')
    pb.backgroundSoundStop = lambda: stopped.append('music')
    try:
        st.MonsterInit_(1)
        st.MonsterBuffer[-1].StopPlayGame = lambda: stopped.append('footsteps')
        st.teardown()
        assert 'footsteps' in stopped, "a monster's footsteps kept walking"
        assert 'ambience' in stopped, 'the ambience kept playing'
        assert 'music' in stopped, 'the music kept playing'
    finally:
        del pb.AMBSoundStop                     # back to the real players
        del pb.backgroundSoundStop


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
