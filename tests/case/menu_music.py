"""The menu music's volume: Page Up and Page Down on the menu screens.

A PORT ADDITION (tsatria03, 2026-09-25; aidocks/project_menu_music_volume_plan.md).  The
menu music goes from 0 to 100% in steps of ten, 100% being MENU_MUSIC_DB as it always
was; it is saved in settings.json as MENUMUSICVOLUME; the screen reader says the new
volume only with voice over off; and nothing else the music player plays - a level's
music, the story's - is ever changed.

It opens the audio device on OpenAL's null driver and reads the music source's gain back
from it, so what is checked is what would be heard.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import _scratch_save                                             # noqa: E402,F401  never the real save

from sixthsense.game.app_delegate import (MENU_MUSIC_KEY,        # noqa: E402
                                          AppDelegate)
from sixthsense.game.main_controller import MainController       # noqa: E402
from sixthsense.platform import openal as al                     # noqa: E402
from sixthsense.platform import volume                           # noqa: E402
from sixthsense.platform.defaults import UserDefaults            # noqa: E402
from sixthsense.platform.keymap import FIXED                     # noqa: E402
from sixthsense.platform.runloop import RunLoop                  # noqa: E402
from sixthsense.ui.menu_input import MenuInput                   # noqa: E402
from sixthsense.ui.screen_input import ScreenInput               # noqa: E402

FULL = volume.gain(volume.MENU_MUSIC_DB)


class _Recorder:
    def __init__(self):
        self.said = []

    def speak(self, text, interrupt=True):
        self.said.append(text)
        return True

    def stop(self):
        pass


class _Pygame:
    """Just enough of pygame for a keyboard handler: key-downs named by their key."""
    KEYDOWN, KEYUP, QUIT = 1, 2, 3

    class key:
        @staticmethod
        def name(k):
            return k


class _Key:
    def __init__(self, name):
        self.type = _Pygame.KEYDOWN
        self.key = name


def _set_saved(value):
    d = UserDefaults.standardUserDefaults()
    if value is None:
        d.removeObjectForKey_(MENU_MUSIC_KEY)
    else:
        d.setObject_forKey_(value, MENU_MUSIC_KEY)
    d.synchronize()


def _menu(saved=None, voice_over=True):
    """The main menu, with its music playing, at the saved volume ``saved``."""
    _set_saved(saved)
    d = UserDefaults.standardUserDefaults()
    # the menu reads voice over back from EYEMODE as it opens, so it goes in the save
    for key, value in (('FIREST', '1'), ('COIN', '3'), ('TUTORIAL', '1'),
                       ('EYEMODE', '1' if voice_over else '0')):
        d.setObject_forKey_(value, key)
    d.synchronize()
    app = AppDelegate.shared()
    if app.playback is None:
        app.didFinishLaunching()
    app.mode = 1 if voice_over else 0
    RunLoop.main().reset()
    m = MainController(speech=_Recorder())
    m.viewDidLoad()
    app.mode = 1 if voice_over else 0
    app.BGMusicStart()
    return m


def _heard(app):
    """The gain the music source is really playing at, read back from OpenAL."""
    bg = app.playback.bgPlayer
    return app.playback.al.source_float(bg.source, al.AL_GAIN)


def _press(handler, *names):
    for name in names:
        handler.handle(_Key(name), _Pygame)


def _done(m):
    m.app.mode = 1
    m.app.playback.backgroundSoundStop()
    m.teardown()
    _set_saved(None)
    d = UserDefaults.standardUserDefaults()
    d.setObject_forKey_('1', 'EYEMODE')
    d.synchronize()


def test_the_steps_and_the_curve():
    """0 to 100 by ten; 100% is the menu music as it always was, never louder; 0% is
    silent; and each step is the percentage squared, so the steps sound even."""
    assert volume.MENU_MUSIC_VOLUMES == (0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100)
    assert volume.DEFAULT_MENU_MUSIC_VOLUME == 100
    assert volume.menu_music() == volume.menu_music(100) == FULL
    assert volume.menu_music(0) == 0.0
    assert abs(volume.menu_music(50) - FULL * 0.25) < 1e-12
    gains = [volume.menu_music(p) for p in volume.MENU_MUSIC_VOLUMES]
    assert gains == sorted(gains) and len(set(gains)) == len(gains), 'the steps are not in order'
    assert max(gains) <= FULL


def test_a_new_save_plays_the_menu_music_at_full():
    m = _menu(saved=None)
    try:
        assert m.app.menu_music_volume == 100
        assert m.app.menu_music_playing()
        assert abs(_heard(m.app) - volume.master(FULL)) < 1e-6, _heard(m.app)
    finally:
        _done(m)


def test_page_down_and_page_up_step_the_menu_music_and_save_it():
    m = _menu(saved=None)
    try:
        keys = MenuInput(m)
        _press(keys, 'page down')
        assert m.app.menu_music_volume == 90
        assert abs(_heard(m.app) - volume.master(volume.menu_music(90))) < 1e-6
        _press(keys, 'page down', 'page down')
        assert m.app.menu_music_volume == 70
        assert UserDefaults.standardUserDefaults().objectForKey_(MENU_MUSIC_KEY) == 70
        _press(keys, 'page up')
        assert m.app.menu_music_volume == 80
        assert abs(_heard(m.app) - volume.master(volume.menu_music(80))) < 1e-6
        # the menu's own rows do not move
        assert keys.quit is False
    finally:
        _done(m)


def test_it_holds_at_both_ends():
    m = _menu(saved=10)
    try:
        keys = MenuInput(m)
        _press(keys, 'page down')
        assert m.app.menu_music_volume == 0
        assert _heard(m.app) == 0.0, 'nought per cent is not silent'
        _press(keys, 'page down')
        assert m.app.menu_music_volume == 0
        for _ in range(12):
            _press(keys, 'page up')
        assert m.app.menu_music_volume == 100
        assert abs(_heard(m.app) - volume.master(FULL)) < 1e-6, 'louder than it ever was'
    finally:
        _done(m)


def test_the_saved_volume_is_used_the_next_time_the_music_starts():
    """Coming back to the menu, or starting the game again, plays it at the saved level."""
    m = _menu(saved=40)
    try:
        m.app.playback.backgroundSoundStop()
        m.app.BGMusicStart()
        assert abs(_heard(m.app) - volume.master(volume.menu_music(40))) < 1e-6
    finally:
        _done(m)


def test_a_saved_value_that_is_not_a_step_means_full():
    for bad in ('loud', 55, -10, 250):
        m = _menu(saved=bad)
        try:
            assert m.app.menu_music_volume == 100, bad
        finally:
            _done(m)
    m = _menu(saved='30')                      # a hand-edited save may hold a string
    try:
        assert m.app.menu_music_volume == 30
    finally:
        _done(m)


def test_spoken_only_with_voice_over_off():
    m = _menu(saved=None, voice_over=False)
    try:
        _press(MenuInput(m), 'page down')
        assert m.speech.said[-1] == 'Music volume 90%', m.speech.said
    finally:
        _done(m)
    m = _menu(saved=None, voice_over=True)
    try:
        before = list(m.speech.said)
        _press(MenuInput(m), 'page down')
        assert m.app.menu_music_volume == 90, 'the volume did not change with voice over on'
        assert m.speech.said == before, 'something was spoken with voice over on'
    finally:
        _done(m)


def test_the_shop_and_the_inventory_take_the_keys_too():
    from sixthsense.game.inventory import InventoryController
    from sixthsense.game.store import MainStoreController
    m = _menu(saved=None, voice_over=False)
    shop = MainStoreController(speech=_Recorder())
    inv = InventoryController(speech=_Recorder())
    try:
        _press(ScreenInput(shop), 'page down')
        assert m.app.menu_music_volume == 90
        assert shop.speech.said[-1] == 'Music volume 90%'
        _press(ScreenInput(inv), 'page down')
        assert m.app.menu_music_volume == 80
        assert inv.speech.said[-1] == 'Music volume 80%'
    finally:
        shop.teardown()
        inv.teardown()
        _done(m)


def test_a_levels_music_and_the_storys_are_never_touched():
    """The music player also plays the level music and the opening screen's story music;
    the keys leave both alone, and save nothing."""
    m = _menu(saved=None, voice_over=False)
    pb = m.app.playback
    try:
        for track, gain in (('bgm_cave', 0.02), ('bgm_start_end', 0.05)):
            pb.startBGPlayer_type_soundGain_Loop_(track, 'wav', gain, True)
            said = list(m.speech.said)
            _press(MenuInput(m), 'page down')
            assert abs(_heard(m.app) - volume.master(gain)) < 1e-6, track
            assert m.app.menu_music_volume == 100, track
            assert m.speech.said == said, track
        pb.backgroundSoundStop()
        assert m.app.change_menu_music_volume(-1) is None, 'it changed with nothing playing'
    finally:
        _done(m)


def test_the_opening_screen_leaves_the_keys_alone():
    from sixthsense.game.intro import StartIntroPage
    m = _menu(saved=None, voice_over=False)
    m.app.playback.backgroundSoundStop()
    page = StartIntroPage(speech=_Recorder())
    try:
        _press(ScreenInput(page), 'page down', 'page up')
        assert m.app.menu_music_volume == 100
        assert not any('Menu music' in line for line in page.speech.said), page.speech.said
    finally:
        page.teardown()
        _done(m)


def test_the_key_bindings_screen_lists_the_two_keys_as_fixed():
    assert FIXED['page up'] == 'Menu music louder'
    assert FIXED['page down'] == 'Menu music quieter'


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
