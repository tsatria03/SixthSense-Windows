"""Zombie sounds really move: checked in OpenAL itself, not in the monster's numbers.

Each footstep is read back from the OpenAL source the zombie is playing on: where the
source is, how loud it is set, whether it is still playing and whether anything
restarted it.  -[oalPlayback startSound:Postion:soundGain:] (0xe524) moves a playing
source and never restarts it, so a zombie closes in, gets louder and keeps breathing.

Opens the audio device, so it needs OpenAL Soft present.
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sixthsense.game import stage_1_e as S1E                    # noqa: E402
from sixthsense.game.app_delegate import AppDelegate            # noqa: E402
from sixthsense.game.monster_control import (WOMAN_GROWL,         # noqa: E402
                                             ZIGZAG_ANGLE)
from sixthsense.game.stage_1_e import Stage_1_E                 # noqa: E402
from sixthsense.platform import openal as al                    # noqa: E402
from sixthsense.platform.defaults import UserDefaults           # noqa: E402
from sixthsense.platform.runloop import RunLoop                 # noqa: E402

#: -[oalPlayback queueNote:...] 0xe0de: AL_REFERENCE_DISTANCE
REFERENCE = 40.0


def _new_stage():
    S1E.LOADING_SECONDS = 0.0
    d = UserDefaults.standardUserDefaults()
    d.setObject_forKey_('1', 'TUTORIAL')
    d.synchronize()
    app = AppDelegate.shared()
    if app.playback is None:
        app.didFinishLaunching()
    RunLoop.main().reset()
    st = Stage_1_E()
    st.viewDidLoad()
    RunLoop.main().pump()
    return app, st


class _Watch:
    """Reads one zombie's source back out of OpenAL, and counts every restart."""

    def __init__(self, app, m):
        self.pb = app.playback
        self.AL = self.pb.al
        self.sid = self.pb._sources[m.comingMonsterStopSoundNumber].sourceId
        self.restarts = 0
        self._play = self.AL.alSourcePlay
        self._rewind = self.AL.alSourceRewind

        def play(sid):
            if sid == self.sid:
                self.restarts += 1
            return self._play(sid)

        def rewind(sid):
            if sid == self.sid:
                self.restarts += 1
            return self._rewind(sid)
        self.AL.alSourcePlay = play
        self.AL.alSourceRewind = rewind

    def close(self):
        self.AL.alSourcePlay = self._play
        self.AL.alSourceRewind = self._rewind

    def read(self):
        """(horizontal distance, bearing in degrees, loudness after distance)"""
        x, height, y = self.AL.source_position(self.sid)
        flat = math.hypot(x, y)
        dist = max(REFERENCE, math.sqrt(x * x + height * height + y * y))
        gain = self.AL.source_float(self.sid, al.AL_GAIN)
        # AL_INVERSE_DISTANCE_CLAMPED with rolloff 1: ref / clamp(dist, ref, max)
        loud = gain * REFERENCE / dist
        bearing = math.degrees(math.atan2(y, x)) % 360.0
        return flat, bearing, loud

    def playing(self):
        return self.AL.source_state(self.sid) == al.AL_PLAYING


def test_a_zombie_closes_in_and_gets_louder_without_restarting():
    """The walk sample is started once and then only moved.  The port used to
    restart it on every step at the spot it came in, so it stayed 33 dB down and
    never came any closer."""
    app, st = _new_stage()
    st.MonsterInit_(2)                      # type2: kind 1, lane 2, 123 degrees
    m = st.MonsterBuffer[0]
    w = _Watch(app, m)
    try:
        assert w.playing(), 'the walk sample is not playing'
        steps = [w.read()]
        for _ in range(6):
            m.MonsterMoving_(None)
            assert w.playing(), 'a footstep stopped the walk sample'
            steps.append(w.read())
        assert w.restarts == 0, 'the walk sample was restarted %d times' % w.restarts
        for (d0, _b0, l0), (d1, _b1, l1) in zip(steps, steps[1:]):
            assert d1 < d0, 'the source did not come closer: %.0f -> %.0f cm' % (d0, d1)
            assert l1 > l0, 'the zombie did not get louder: %.4f -> %.4f' % (l0, l1)
        for _d, bearing, _l in steps[1:]:
            assert abs(bearing - 123.0) < 0.5, 'the source left lane 2: %.1f' % bearing
        rise = 20 * math.log10(steps[-1][2] / steps[0][2])
        assert rise > 3.0, 'six steps only made it %.1f dB louder' % rise
    finally:
        w.close()
        st.teardown()


def test_a_zombie_on_top_of_you_is_close_and_loud():
    """Walked all the way in, the source ends 20 cm out in its lane (0x11032)."""
    app, st = _new_stage()
    st.MonsterInit_(4)                      # lane 4, 57 degrees
    m = st.MonsterBuffer[0]
    w = _Watch(app, m)
    try:
        far = w.read()
        for _ in range(200):
            m.MonsterMoving_(None)
            if m.monsterRange <= 25.0:
                break
        m.MonsterMoving_(None)
        near = w.read()
        assert w.restarts == 0
        assert w.playing()
        assert abs(near[0] - 20.0) < 0.5, 'it stopped %.1f cm out' % near[0]
        assert abs(near[1] - 57.0) < 0.5, 'it left its lane: %.1f' % near[1]
        assert near[2] > far[2] * 4, 'it is barely louder close up'
    finally:
        w.close()
        st.teardown()


def test_a_zigzag_walker_sweeps_across_in_openal():
    """MovingType 11 swings between 185 and 120 degrees, one bearing a step, and
    the source it plays on goes with it."""
    app, st = _new_stage()
    st.MonsterInit_(6)                      # type6: MovingType 11
    m = st.MonsterBuffer[0]
    assert m.MovingType == 11, m.MovingType
    w = _Watch(app, m)
    try:
        m.MovingCount = 0
        m.MovingAngleTurn = False
        m.comingSoundInWalk = 99            # keep the cycle from resetting mid-sweep
        heard = []
        for _ in range(4):
            m.MonsterMoving_(None)
            heard.append(round(w.read()[1]) % 360)
        assert w.restarts == 0
        want = [a % 360 for a in ZIGZAG_ANGLE[11]]
        assert heard == want, 'the source swept %r, the walk says %r' % (heard, want)
    finally:
        w.close()
        st.teardown()


def test_the_breathing_is_not_cut_short():
    """The sample keeps running across footsteps, so its breathing - the headshot
    window - is heard whole instead of being clipped at every step."""
    app, st = _new_stage()
    st.MonsterInit_(3)
    m = st.MonsterBuffer[0]
    w = _Watch(app, m)
    try:
        t0 = w.AL.source_float(w.sid, al.AL_SEC_OFFSET)
        import time
        time.sleep(0.3)
        for _ in range(3):
            m.MonsterMoving_(None)
        t1 = w.AL.source_float(w.sid, al.AL_SEC_OFFSET)
        assert w.restarts == 0
        assert t1 >= t0, 'the sample went back to the start: %.2f -> %.2f s' % (t0, t1)
    finally:
        w.close()
        st.teardown()


def test_the_bullet_hit_is_heard_where_the_zombie_is():
    """gun_att_sound_1 (56) is a stereo file, and OpenAL never places a stereo
    sound, so it played in the middle of your head.  It is folded to mono as it
    loads, and its source sits where the zombie was hit."""
    app, st = _new_stage()
    st.MonsterInit_(5)                      # lane 5, hard right
    m = st.MonsterBuffer[0]
    m.MonsterMoving_(None)
    try:
        m.MonsterHitSound_(None)
        note = app.CheckSoundBuf_(56)
        assert note != -1, 'the hit never played'
        pb = app.playback
        assert pb._buffers[note].channels == 1, 'the hit sound is still stereo'
        x, _h, y = pb.al.source_position(pb._sources[note].sourceId)
        assert x > 100 and abs(y) < 1.0, 'the hit is at (%.0f, %.0f)' % (x, y)
    finally:
        st.teardown()


def test_the_headshot_announcement_is_centred():
    """headshot_4 (330) is stereo, and OpenAL never places a stereo sound, so the
    announcement is heard in the centre at 0.1 wherever the zombie is (0x3a24a)."""
    app, st = _new_stage()
    loop = RunLoop.main()
    st.MonsterInit_(1)                      # lane 1, hard left, far out
    m = st.MonsterBuffer[0]
    m.StopPlayGame()
    loop.cancelPerform(m)
    m.monsterRange = 800.0
    m.Pos = (-800.0, 0.0)
    m.MovingPosAngle = 180
    m.HP = 1000
    m.headShotFlag = True
    try:
        st.gamePlayer.useWepon = 2
        st.shotFlag = False
        st.MovingShot_(180.0)
        import time
        t0 = time.monotonic()
        while time.monotonic() - t0 < S1E.SHOT_TRAVEL + 0.3:
            loop.pump()
            time.sleep(0.004)
        assert st.gamePlayer.HeadShotCount == 1, 'it was not a headshot'
        note = app.CheckSoundBuf_(330)
        pb = app.playback
        sid = pb._sources[note].sourceId
        assert pb._buffers[note].channels == 2, 'the announcement was made mono'
        gain = pb.al.source_float(sid, al.AL_GAIN)
        assert abs(gain - 0.1) < 1e-6, 'the announcement is at %.3f' % gain
    finally:
        st.teardown()


def test_a_monster_never_passes_through_you_on_its_last_step():
    """The girl's 50 cm step took her from 50 cm to 0, dead centre, and the next step
    put her back out at 20 cm in her lane: a step sideways.  She keeps level 1's step
    on every level (0x38d8c); the gains are run anyway.  Walked in at each level, in
    every lane, the source stays on its own side and never comes closer
    than 20 cm."""
    for gain in (1.0, 1.5, 2.25):
        for type_id, lane in ((10001, 1), (10003, 3), (10005, 5)):
            app, st = _new_stage()
            st.monsterHPGain = gain
            st.MonsterInit_(type_id)
            m = st.MonsterBuffer[0]
            w = _Watch(app, m)
            try:
                for _ in range(60):
                    m.MonsterMoving_(None)
                    x, _h, y = w.AL.source_position(w.sid)
                    flat = math.hypot(x, y)
                    assert flat >= 19.99, \
                        'lane %d at gain %.2f came %.1f cm close' % (lane, gain, flat)
                    if lane == 1:
                        assert x < 0, 'lane 1 crossed to the right at gain %.2f' % gain
                    elif lane == 5:
                        assert x > 0, 'lane 5 crossed to the left at gain %.2f' % gain
                    if m.monsterRange <= 25.0:
                        break
                else:
                    raise AssertionError('lane %d never arrived' % lane)
            finally:
                w.close()
                st.teardown()


def test_the_woman_zombie_growls_before_she_reaches_you():
    """Her walk sounds are footsteps with the growl at the end.  She keeps level 1's
    step on every level (0x39034), so her sample starts at the top on every level, as
    in the original, and the growl lands 3.5 to 5 m out, in the cave and the forest
    alike; the next time round comes after she has reached you."""
    for mode, sound in ((1, 271), (2, 272)):
        for level in (1, 2, 3, 4):
            gain = 1.5 ** (level - 1)
            app, st = _new_stage()
            st.gameMode = mode
            st.monsterHPGain = gain
            st.MonsterInit_(10006)          # the woman zombie, lane 1
            m = st.MonsterBuffer[0]
            try:
                assert m.comingSound == sound, 'she walks on %d' % m.comingSound
                w = _Watch(app, m)
                try:
                    assert w.playing(), 'her walk sample is not playing'
                    start = w.AL.source_float(w.sid, al.AL_SEC_OFFSET)
                    interval = (m.comingSoundTime - 0.1) / m.comingSoundInWalk
                    growl = WOMAN_GROWL[sound] - start      # seconds from now
                    steps = 1 + int(growl / interval)       # the first was at once
                    at = 1000.0 - m.comingRange * steps
                    where = '%s level %d: the growl is %.0f cm out' % (sound, level, at)
                    # 520: the cave's level 1 is the original's own, about 4.5 to 5 m
                    assert 250.0 <= at <= 520.0, where
                    arrive = math.ceil((1000.0 - 25.0) / m.comingRange)
                    loop = 5.23 if sound == 271 else 6.29
                    again = 1 + int((growl + loop) / interval)
                    assert again >= arrive, where + ', and again before she arrives'
                    assert start < 0.3, \
                        'level %d starts %.2f s in, not at the top' % (level, start)
                finally:
                    w.close()
            finally:
                st.teardown()

    app, st = _new_stage()
    st.gameMode = 1
    st.MonsterInit_(1)
    m = st.MonsterBuffer[0]
    w = _Watch(app, m)
    try:
        t = w.AL.source_float(w.sid, al.AL_SEC_OFFSET)
        assert t < 0.5, 'an ordinary zombie starts %.2f s into its sample' % t
    finally:
        w.close()
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
