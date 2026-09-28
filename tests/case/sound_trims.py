"""The per-file trims that even out the recordings (platform/sound_trims.py).

A PORT ADDITION (tunmi13productions, 2026-09-27; aidocks/project_sound_trims_plan.md).  Every trim
multiplies the sound's AL_GAIN, a boost past 1.0 since each source's AL_MAX_GAIN is
raised; every file is brought to one level, the music and the ambience included, and loads
bit for bit; F8 in debug mode turns them off and on.

It opens the audio device on OpenAL's null driver and reads the gains back from it.
"""
from __future__ import annotations

import importlib.util
import math
import os
import sys
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import _scratch_save                                             # noqa: E402,F401  never the real save

from sixthsense import paths                                     # noqa: E402
from sixthsense.game import debug, oal_playback                  # noqa: E402
from sixthsense.game.app_delegate import AppDelegate             # noqa: E402
from sixthsense.platform import openal as al                     # noqa: E402
from sixthsense.platform import sound_trims, volume              # noqa: E402
from sixthsense.platform.keymap import DEBUG_IDS, DEFAULTS       # noqa: E402

# tools/sound_trims.py, loaded by its path: this file has the same name
_spec = importlib.util.spec_from_file_location('sound_trims_tool',
                                               os.path.join(ROOT, 'tools', 'sound_trims.py'))
tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tool)

USED = os.path.join(ROOT, 'game', 'sounds', 'used')
NOTE = 115                                  # clear of what the game uses
def _trimmed(sign):
    """The smallest file the table cuts (sign -1) or boosts (sign 1)."""
    names = [n for n, t in sound_trims.MEASURED.items()
             if (t > 0) == (sign > 0) and n not in sound_trims.BY_EAR
             and n not in oal_playback.MONO_AT_LOAD]
    return min(names, key=lambda n: os.path.getsize(paths.path_for_resource(n, 'wav')))


def _raw(name):
    with wave.open(paths.path_for_resource(name, 'wav'), 'rb') as w:
        return w.readframes(w.getnframes())


def _untrimmed():
    """The smallest file the game plays that the table leaves as it is."""
    names = [os.path.splitext(f)[0] for _d, _s, files in os.walk(USED) for f in files
             if os.path.splitext(f)[0] not in sound_trims.MEASURED]
    return min(names, key=lambda n: os.path.getsize(paths.path_for_resource(n, 'wav')))


class _Trims:
    """The switch and the hand-set trims as they were, put back afterwards."""

    def __enter__(self):
        self.on = volume.SOUND_TRIMS_ON
        self.by_ear = dict(sound_trims.BY_EAR)
        volume.SOUND_TRIMS_ON = True
        return self

    def __exit__(self, *exc):
        volume.SOUND_TRIMS_ON = self.on
        sound_trims.BY_EAR.clear()
        sound_trims.BY_EAR.update(self.by_ear)
        return False


def _app():
    app = AppDelegate.shared()
    if app.playback is None:
        app.didFinishLaunching()
    return app


def test_every_trim_names_a_file_the_game_plays():
    names = {os.path.splitext(f)[0] for _d, _s, files in os.walk(USED) for f in files}
    for table in (sound_trims.MEASURED, sound_trims.BY_EAR):
        missing = sorted(set(table) - names)
        assert not missing, 'no such file in used/: %s' % missing


def test_every_sound_is_brought_to_one_level():
    """No families and nothing left alone (tunmi13productions, 2026-09-27): every file is brought
    to -12 LUFS, as far as a 12 dB boost goes; silence and a file already there have no
    trim."""
    assert tool.TARGET_LUFS == -12.0
    assert tool.trim_for(-9.5) == -2.5            # the gun's hit
    assert tool.trim_for(-16.0) == 4.0            # the menu music
    assert tool.trim_for(-50.0) == 12.0           # the first breath, as far as it goes
    assert tool.trim_for(-12.2) == 0.0 and tool.trim_for(float('-inf')) == 0.0
    for name in ('player_breath_1', 'player_die', 'bgm_main_menu', 'bgm_cave_amb',
                 'effect_forest_rainng', 'bitbee_1', 'weapon_gun_att1', 'five'):
        assert name in sound_trims.MEASURED, '%s is not levelled' % name

def test_the_bosses_approach_stands_out():
    """tunmi13productions, 2026-09-28: levelling had cut both bosses' approach loops, 286
    and 290, under the mix; they are boosted 3 dB instead."""
    with _Trims():
        for name in ('zombies_boss_1_coming_cave', 'zombies_boss_3_coming_forest'):
            assert sound_trims.trim_db(name) == 3.0, name


def test_the_woman_plays_as_recorded():
    """tunmi13productions, 2026-09-28: her thank you, boosted 11 dB, was a lot louder."""
    with _Trims():
        for name in ('woman_coming_cave', 'woman_coming_forest', 'woman_die',
                     'woman_thank_u_kiss'):
            assert sound_trims.gain(name) == 1.0, name


def test_no_zombie_boss_monster_or_woman_sound_is_ever_cut():
    """tunmi13productions, 2026-09-28: they are what you listen for, so levelling only boosts
    them.  Zombie 10's approach, at -5.5 LUFS, would be cut 6.5 dB."""
    assert tool.trim_for(-5.5, 'sfx/zombies/normal') == 0.0
    assert tool.trim_for(-5.5, 'sfx/monsters') == 0.0
    assert tool.trim_for(-5.5, 'sfx/characters') == 0.0
    assert tool.trim_for(-5.5, 'sfx/weapons') == -6.5
    assert tool.trim_for(-20.0, 'sfx/zombies/bosses') == 8.0
    with _Trims():
        for _d, _s, files in os.walk(USED):
            for f in files:
                name = os.path.splitext(f)[0]
                path = paths.path_for_resource(name, 'wav')
                if volume.group_of(name, path) == volume.ENTITIES and '/sfx/weapons/' not in                         path.replace(os.sep, '/'):
                    assert sound_trims.trim_db(name) >= 0, name


def test_no_boost_is_past_the_cap():
    top = max(list(sound_trims.MEASURED.values()) + list(sound_trims.BY_EAR.values()))
    assert top <= tool.MAX_BOOST_DB, top
    assert volume.gain(tool.MAX_BOOST_DB) <= sound_trims.MAX_GAIN


def test_every_file_loads_as_it_is():
    with _Trims():
        for name in (_untrimmed(), _trimmed(-1), _trimmed(1)):
            path = paths.path_for_resource(name, 'wav')
            _fmt, pcm, _rate, _ch = oal_playback._load_wav(path, name)
            assert pcm == _raw(name), '%s did not load bit for bit' % name


def _heard(pb, note):
    return pb.al.source_float(pb._sources[note].sourceId, al.AL_GAIN)


def _load(pb, notes):
    for note, name in notes.items():
        pb.initBufferOne_FileName_Type_(note, name, 'wav')
        pb.initSourceOne_(note)


def _free(pb, notes):
    for note in notes:
        pb.freeSourceOne(note)
        pb.freeBufferOne(note)


def test_a_trim_is_heard_on_the_gain_and_a_boost_passes_one():
    pb = _app().playback
    with _Trims():
        notes = {NOTE: _trimmed(-1), NOTE + 1: _trimmed(1), NOTE + 2: _untrimmed()}
        _load(pb, notes)
        try:
            for note, name in notes.items():
                sid = pb._sources[note].sourceId
                assert pb.al.source_float(sid, al.AL_MAX_GAIN) == sound_trims.MAX_GAIN, name
                pb.queueNote_gain_sourcePos_defaultZ_repeats_(note, 1.0, (0.0, 0.0), 0, False)
                want = volume.gain(sound_trims.MEASURED.get(name, 0.0))
                assert abs(_heard(pb, note) - want) < 1e-5, (name, _heard(pb, note), want)
            assert _heard(pb, NOTE + 1) > 1.0, 'the boost did not pass 1.0'
            assert _heard(pb, NOTE + 2) == 1.0, 'a file with no trim moved'
        finally:
            _free(pb, notes)


def test_the_games_own_gain_is_still_capped_at_one_before_the_trim():
    """OpenAL capped a source at 1.0 before AL_MAX_GAIN was raised, so a gain the game
    asks for above 1.0 plays at 1.0, times the file's trim, as it always did."""
    pb = _app().playback
    with _Trims():
        notes = {NOTE: _untrimmed(), NOTE + 1: _trimmed(1)}
        _load(pb, notes)
        try:
            for note, name in notes.items():
                pb.queueNote_gain_sourcePos_defaultZ_repeats_(note, 1.7, (0.0, 0.0), 0, False)
                want = volume.gain(sound_trims.MEASURED.get(name, 0.0))
                assert abs(_heard(pb, note) - want) < 1e-5, (name, _heard(pb, note), want)
        finally:
            _free(pb, notes)


def test_the_music_and_the_ambience_hear_their_trim():
    pb = _app().playback
    with _Trims():
        name = 'bgm_main_menu'
        path = paths.path_for_resource(name, 'wav')
        try:
            pb.bgPlayer.play(path, 0.2, -1)
            src = pb.bgPlayer.source
            assert pb.al.source_float(src, al.AL_MAX_GAIN) == sound_trims.MAX_GAIN
            want = 0.2 * volume.gain(sound_trims.MEASURED[name])
            heard = pb.al.source_float(src, al.AL_GAIN)
            assert abs(heard - want) < 1e-5, (heard, want)
            assert pb.bgPlayer.volume == 0.2, 'the gain the game asked for was changed'
            pb.setSoundTrims_(False)
            assert abs(pb.al.source_float(src, al.AL_GAIN) - 0.2) < 1e-6
        finally:
            pb.backgroundSoundStop()


def test_by_ear_wins_and_the_switch_turns_everything_off():
    with _Trims():
        name = _trimmed(-1)
        sound_trims.BY_EAR[name] = 2.0
        assert sound_trims.trim_db(name) == 2.0
        assert sound_trims.gain(name) == volume.gain(2.0)
        volume.SOUND_TRIMS_ON = False
        assert sound_trims.trim_db(name) == 0.0 and sound_trims.gain(name) == 1.0
        assert sound_trims.gain(_trimmed(1)) == 1.0


class _Stage:
    def __init__(self, app, tutorial=False):
        self.app = app
        self.said = []
        self.ESCAPE_LEAVES = tutorial

    def _say(self, text):
        self.said.append(text)


def test_f8_turns_the_trims_off_and_on_for_playing_sounds_too():
    assert 'debug_sound_trims' in DEBUG_IDS
    assert DEFAULTS['debug_sound_trims'] == [('f8',)]
    app = _app()
    pb = app.playback
    with _Trims():
        cut, boosted = _trimmed(-1), _trimmed(1)
        notes = {NOTE: cut, NOTE + 1: boosted}
        _load(pb, notes)
        for note in notes:
            pb.queueNote_gain_sourcePos_defaultZ_repeats_(note, 0.5, (0.0, 0.0), 0, True)
            pb.startSound_Postion_(note, (0.0, 0.0))
        try:
            st = _Stage(app, tutorial=True)         # it works in the tutorial too
            debug.perform(st, 'debug_sound_trims', 3)
            assert not volume.SOUND_TRIMS_ON and st.said == ['Sound trims off.'], st.said
            for note in notes:
                assert abs(_heard(pb, note) - 0.5) < 1e-6, 'a trim stayed on'
                assert pb.is_note_playing(note), 'a sound stopped'
            debug.perform(st, 'debug_sound_trims', 3)
            assert volume.SOUND_TRIMS_ON and st.said[-1] == 'Sound trims on.', st.said
            for note, name in notes.items():
                assert abs(_heard(pb, note) - 0.5 * sound_trims.gain(name)) < 1e-6, name
        finally:
            _free(pb, notes)


def test_the_measuring_matches_the_standard():
    """A 997 Hz sine at -20 dBFS in one channel is -23.0 LUFS (ITU-R BS.1770)."""
    for rate in (44100, 22050):
        s = [round(0.1 * 32767 * math.sin(2 * math.pi * 997 * i / rate))
             for i in range(rate * 2)]
        assert abs(tool.loudness([s], rate) + 23.0) < 0.1, rate
    assert tool.loudness([[0] * 44100], 44100) == float('-inf')


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
