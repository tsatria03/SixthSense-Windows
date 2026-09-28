"""The gameplay gain and the weapons, entities and player volumes, set in play.

A PORT ADDITION (tunmi13productions, 2026-09-26; aidocks/project_gameplay_gain_plan.md).  The gain
is OpenAL's listener gain, 0 to 6 dB, heard only in play, and it leaves the music and the
ambience where they were; the three groups are percentages that move only their own
sounds; Page Up and Page Down step them, with Shift, Control or Alt for a group.

It opens the audio device on OpenAL's null driver and reads the gains back from it, so
what is checked is what would be heard.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import _scratch_save                                             # noqa: E402,F401  never the real save

from sixthsense import paths                                     # noqa: E402
from sixthsense.game.app_delegate import AppDelegate             # noqa: E402
from sixthsense.platform import openal as al                     # noqa: E402
from sixthsense.platform import volume                           # noqa: E402
from sixthsense.platform.defaults import UserDefaults            # noqa: E402
from sixthsense.platform.keymap import FIXED_IN_PLAY             # noqa: E402
from sixthsense.ui.input import Input, gameplay_volume_key       # noqa: E402

#: note -> (file, the group it should land in).  High notes, clear of what the game uses.
SOUNDS = {110: ('weapon_ak_fire', volume.WEAPONS),
          111: ('man_monster_hit', volume.ENTITIES),
          112: ('player_breath_1', volume.PLAYER),
          113: ('bgm_cave_amb', volume.BACKDROP),
          114: ('ui_select', None)}


class _Recorder:
    def __init__(self):
        self.said = []

    def speak(self, text, interrupt=True):
        self.said.append(text)
        return True

    def stop(self):
        pass


class _Pygame:
    """Just enough of pygame for the stage's keyboard."""
    KEYDOWN, KEYUP, QUIT = 1, 2, 3
    KMOD_SHIFT, KMOD_CTRL, KMOD_ALT = 0x3, 0xC0, 0x300

    class key:
        @staticmethod
        def name(k):
            return k


class _Key:
    def __init__(self, name, mod=0):
        self.type = _Pygame.KEYDOWN
        self.key = name
        self.mod = mod


class _Stage:
    """What the keys reach on a stage: the app, ``_say`` and the state of play."""

    def __init__(self, app):
        self.app = app
        self.gameState = 0
        self.said = []

    def _say(self, text):
        self.said.append(text)


def _app():
    app = AppDelegate.shared()
    if app.playback is None:
        app.didFinishLaunching()
    return app


class _Saved:
    """Every volume setting as it was, put back afterwards.  The per-file trims are held
    off meanwhile, so the gains checked are the settings' alone; tests/case/sound_trims.py
    checks the trims."""

    def __enter__(self):
        self.percents = dict(volume.percents)
        self.db = volume.gameplay_gain_db
        self.trims = volume.SOUND_TRIMS_ON
        volume.SOUND_TRIMS_ON = False
        return self

    def __exit__(self, *exc):
        volume.SOUND_TRIMS_ON = self.trims
        volume.percents.update(self.percents)
        volume.gameplay_gain_db = self.db
        app = _app()
        app.playback.setGameplayGain_(False)
        d = UserDefaults.standardUserDefaults()
        for key in volume.VOLUME_KEYS:
            d.setInteger_forKey_(volume.percents[key], key)
        d.setInteger_forKey_(self.db, volume.GAMEPLAY_GAIN_KEY)
        d.synchronize()
        return False


def _load_sounds(pb, gain=0.5):
    for note, (name, _group) in SOUNDS.items():
        pb.initBufferOne_FileName_Type_(note, name, 'wav')
        pb.initSourceOne_(note)
        pb.queueNote_gain_sourcePos_defaultZ_repeats_(note, gain, (0.0, 0.0), 0, False)


def _heard(pb, note):
    return pb.al.source_float(pb._sources[note].sourceId, al.AL_GAIN)


def _free(pb):
    for note in SOUNDS:
        pb.freeSourceOne(note)
        pb.freeBufferOne(note)


def test_each_sound_lands_in_its_group():
    for name, group in SOUNDS.values():
        assert volume.group_of(name, paths.path_for_resource(name, 'wav')) == group, name
    # the shop naming a weapon is speech, not a weapon
    assert volume.group_of('x', os.path.join('game', 'sounds', 'used', 'speech',
                                             'weapons', 'x.wav')) is None
    # a weapon's hit is the zombie being struck, so it goes with the entities
    for name in ('weapon_gun_att1', 'weapon_gun_att2', 'weapon_knife_att1',
                 'weapon_japen_knife_att2'):
        assert volume.group_of(name, paths.path_for_resource(name, 'wav')) == volume.ENTITIES, name
    for name in ('weapon_gun_nonbullets', 'weapon_knife_fire', 'weapon_m4_reload'):
        assert volume.group_of(name, paths.path_for_resource(name, 'wav')) == volume.WEAPONS, name
    for name in ('woman_die', 'man_coming_cave_monster'):
        assert volume.group_of(name, paths.path_for_resource(name, 'wav')) == volume.ENTITIES
    assert volume.group_of('player_die') == volume.PLAYER
    assert volume.group_of('effect_forest_rainng') == volume.BACKDROP


def test_at_their_defaults_every_sound_is_the_binarys_gain():
    app = _app()
    pb = app.playback
    with _Saved():
        for key in volume.VOLUME_KEYS:
            volume.percents[key] = 100
        volume.gameplay_gain_db = 0
        pb.setGameplayGain_(True)
        _load_sounds(pb)
        try:
            assert abs(pb.al.listener_float(al.AL_GAIN) - 1.0) < 1e-6
            for note in SOUNDS:
                assert abs(_heard(pb, note) - 0.5) < 1e-6, SOUNDS[note]
        finally:
            _free(pb)


def test_a_group_moves_only_its_own_sounds_and_the_ones_playing():
    app = _app()
    pb = app.playback
    with _Saved():
        for key in volume.VOLUME_KEYS:
            volume.percents[key] = 100
        _load_sounds(pb)
        try:
            for key, group in ((volume.WEAPON_KEY, volume.WEAPONS),
                               (volume.PLAYER_KEY, volume.PLAYER)):
                volume.percents[key] = 50
                pb.refreshGains()
                for note, (name, g) in SOUNDS.items():
                    want = 0.125 if g == group else 0.5
                    assert abs(_heard(pb, note) - want) < 1e-6, (key, name, _heard(pb, note))
                volume.percents[key] = 100
                pb.refreshGains()
        finally:
            _free(pb)


def test_the_gain_raises_the_sounds_and_holds_the_music_and_ambience():
    app = _app()
    pb = app.playback
    with _Saved():
        for key in volume.VOLUME_KEYS:
            volume.percents[key] = 100
        volume.gameplay_gain_db = 6
        _load_sounds(pb, gain=0.2)
        path = paths.path_for_resource('bgm_cave', 'wav')
        pb.bgPlayer.play(path, 0.02, -1)
        try:
            pb.setGameplayGain_(True)
            g = pb.al.listener_float(al.AL_GAIN)
            assert abs(g - volume.gain(6)) < 1e-5 and g <= 2.0, g
            for note, (name, group) in SOUNDS.items():
                want = 0.2 / g if group == volume.BACKDROP else 0.2
                assert abs(_heard(pb, note) - want) < 1e-6, (name, _heard(pb, note))
            heard = pb.al.source_float(pb.bgPlayer.source, al.AL_GAIN)
            assert abs(heard * g - 0.02) < 1e-6, 'the gain moved the level music'
            assert pb.bgPlayer.volume == 0.02
            pb.setGameplayGain_(False)
            assert abs(pb.al.listener_float(al.AL_GAIN) - 1.0) < 1e-6
            assert abs(_heard(pb, 113) - 0.2) < 1e-6
            assert abs(pb.al.source_float(pb.bgPlayer.source, al.AL_GAIN) - 0.02) < 1e-6
        finally:
            pb.backgroundSoundStop()
            _free(pb)


def test_the_steps_hold_at_the_ends_and_are_saved():
    app = _app()
    d = UserDefaults.standardUserDefaults()
    with _Saved():
        volume.gameplay_gain_db = 0
        assert app.change_gameplay_volume(volume.GAMEPLAY_GAIN_KEY, -1) == 0
        got = [app.change_gameplay_volume(volume.GAMEPLAY_GAIN_KEY, 1) for _ in range(7)]
        assert got == [1, 2, 3, 4, 5, 6, 6], got
        assert d.intForKey_(volume.GAMEPLAY_GAIN_KEY) == 6
        volume.percents[volume.PLAYER_KEY] = 55
        assert app.change_gameplay_volume(volume.PLAYER_KEY, 1) == 60
        assert app.change_gameplay_volume(volume.PLAYER_KEY, -1) == 50
        assert d.intForKey_(volume.PLAYER_KEY) == 50
        volume.percents[volume.WEAPON_KEY] = 100
        assert app.change_gameplay_volume(volume.WEAPON_KEY, 1) == 100


def test_the_keys_in_play_and_what_they_say():
    app = _app()
    with _Saved():
        volume.gameplay_gain_db = 0
        for key in volume.VOLUME_KEYS:
            volume.percents[key] = 100
        st = _Stage(app)
        inp = Input(st)
        for name, mod in (('page up', 0), ('page up', 0), ('page down', 0),
                          ('page down', _Pygame.KMOD_SHIFT),
                          ('page down', _Pygame.KMOD_CTRL),
                          ('page down', _Pygame.KMOD_ALT)):
            inp.handle(_Key(name, mod), _Pygame)
        # Control set the entities until 2026-09-28; now it does nothing at all
        assert st.said == ['Gain 1 decibel', 'Gain 2 decibels', 'Gain 1 decibel',
                           'Weapons volume 90%', 'Player volume 90%'], st.said
        assert volume.gameplay_gain_db == 1
        # ...on the pause panel too
        st.gameState = 1
        inp.handle(_Key('page up', 0), _Pygame)
        assert st.said[-1] == 'Gain 2 decibels', st.said
        assert not gameplay_volume_key('up', 0, st, _Pygame)


def test_the_binding_screen_lists_the_keys_in_play():
    labels = [what for _b, what in FIXED_IN_PLAY]
    assert len(labels) == 6 and all(label.endswith('in play') for label in labels)
    assert not any('Entities' in label for label in labels)


def test_the_entities_are_always_at_full_volume():
    """tunmi13productions, 2026-09-28: the zombies are what you listen for, so they have no
    setting; every other group turned right down leaves them where they were."""
    assert 'ENTITYVOLUME' not in volume.VOLUME_KEYS
    assert volume.ENTITIES not in volume.GROUP_KEY
    app = _app()
    pb = app.playback
    with _Saved():
        for key in volume.VOLUME_KEYS:
            volume.percents[key] = 0 if key in (volume.WEAPON_KEY, volume.PLAYER_KEY) else 100
        assert volume.group_gain(volume.ENTITIES) == 1.0
        _load_sounds(pb)
        try:
            for note, (name, group) in SOUNDS.items():
                if group == volume.ENTITIES:
                    assert abs(_heard(pb, note) - 0.5) < 1e-6, (name, _heard(pb, note))
        finally:
            _free(pb)


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
