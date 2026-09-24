"""Where the game finds its files: ``paths.path_for_resource``.

The original bundle is flat; the port keeps its sounds in folders under
``game/sounds/used``, and those the game never plays under ``game/sounds/unused``, which
is searched last (aidocks/DIVERGENCES.md).  Each test builds a small bundle of its own in
a temporary folder, so these check the lookup itself rather than the shipped data - that
is ``data.py``'s job - and they never touch the save or play a sound.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import _scratch_save                                             # noqa: E402,F401  never the real save

from sixthsense import paths                                     # noqa: E402

# what paths._is_bundle looks for before it takes a folder for the bundle
MARKERS = ('SoundList.plist', 'g_CH1_E')


def _bundle(files):
    """A throwaway bundle holding the two marker files and ``files`` (paths inside the
    bundle, with '/' between folders), and the lookup pointed at it."""
    top = tempfile.mkdtemp()
    for rel in MARKERS + tuple(files):
        p = os.path.join(top, *rel.split('/'))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            f.write(rel)
    paths.set_game(top)
    return top


def _done(top):
    paths.set_game(None)
    shutil.rmtree(top, ignore_errors=True)


def _found(top, name, ext=None):
    """Where the lookup found it, inside the bundle, with '/' between folders."""
    p = paths.path_for_resource(name, ext)
    return None if p is None else os.path.relpath(p, top).replace(os.sep, '/')


def test_a_sound_in_a_folder_is_found():
    rel = 'sounds/used/sfx/zombies/normal/normalcave1/zombie_1_coming_cave.wav'
    top = _bundle([rel])
    try:
        assert _found(top, 'zombie_1_coming_cave', 'wav') == rel
    finally:
        _done(top)


def test_the_unused_folder_is_searched_last():
    """What the game never plays is in sounds/unused; a name only there is still found."""
    rel = 'sounds/unused/speech/game/the rank.wav'
    top = _bundle([rel])
    try:
        assert _found(top, 'the rank', 'wav') == rel
    finally:
        _done(top)


def test_a_sound_in_the_used_folder_wins_over_the_unused_one():
    top = _bundle(['sounds/unused/sfx/misc/ui_select.wav', 'sounds/used/sfx/misc/ui_select.wav'])
    try:
        assert _found(top, 'ui_select', 'wav') == 'sounds/used/sfx/misc/ui_select.wav'
    finally:
        _done(top)


def test_case_does_not_matter():
    rel = 'sounds/used/speech/menus/main/Game Start Button.wav'
    top = _bundle([rel])
    try:
        assert _found(top, 'game start button', 'wav') == rel
        assert _found(top, 'GAME START BUTTON', 'WAV') == rel
    finally:
        _done(top)


def test_a_shared_sound_is_always_the_same_copy():
    """Where the original reuses one recording, each folder that uses it has a copy.
    The first in sorted order is taken, whichever order the folders were made in."""
    top = _bundle(['sounds/used/sfx/zombies/normal/normalcave7/zombie_3_7_hit_player.wav',
                   'sounds/used/sfx/zombies/normal/normalcave3/zombie_3_7_hit_player.wav'])
    try:
        want = 'sounds/used/sfx/zombies/normal/normalcave3/zombie_3_7_hit_player.wav'
        assert _found(top, 'zombie_3_7_hit_player', 'wav') == want
        assert _found(top, 'zombie_3_7_hit_player', 'wav') == want
    finally:
        _done(top)


def test_the_top_folder_comes_first():
    """pathForResource:ofType: only ever looked in the top folder, so a file there wins
    over one of the same name in the sounds folder."""
    top = _bundle(['ui_select.wav', 'sounds/used/sfx/misc/ui_select.wav'])
    try:
        assert _found(top, 'ui_select', 'wav') == 'ui_select.wav'
    finally:
        _done(top)


def test_the_plists_and_maps_are_in_the_top_folder():
    top = _bundle(['type1.plist', 'a_CH1_E.txt', 'sounds/used/sfx/misc/ui_select.wav'])
    try:
        assert _found(top, 'type1', 'plist') == 'type1.plist'
        assert _found(top, 'a_CH1_E', 'txt') == 'a_CH1_E.txt'
        assert _found(top, 'g_CH1_E') == 'g_CH1_E'
        assert _found(top, 'SoundList', 'plist') == 'SoundList.plist'
    finally:
        _done(top)


def test_an_original_flat_bundle_still_works():
    """--game pointed at an untouched sixsense.app, with every WAV beside the plists."""
    top = _bundle(['zombie_1_coming_cave.wav', 'type1.plist'])
    try:
        assert _found(top, 'zombie_1_coming_cave', 'wav') == 'zombie_1_coming_cave.wav'
        assert _found(top, 'type1', 'plist') == 'type1.plist'
        assert paths.sounds() == top
    finally:
        _done(top)


def test_sounds_is_the_used_folder():
    top = _bundle(['sounds/used/sfx/misc/ui_select.wav'])
    try:
        assert paths.sounds() == os.path.join(top, 'sounds', 'used')
    finally:
        _done(top)


def test_a_missing_sound_is_none():
    top = _bundle(['sounds/used/sfx/misc/ui_select.wav'])
    try:
        assert _found(top, 'zombie_5_hit_player', 'wav') is None
        assert _found(top, 'ui_select', 'plist') is None, 'the extension was ignored'
    finally:
        _done(top)


def test_pointing_somewhere_else_forgets_the_old_sounds():
    first = _bundle(['sounds/used/sfx/misc/ui_select.wav'])
    try:
        assert _found(first, 'ui_select', 'wav') is not None
        second = _bundle([])
        try:
            assert _found(second, 'ui_select', 'wav') is None, \
                'a sound from the previous bundle was still found'
        finally:
            _done(second)
    finally:
        _done(first)


def test_the_save_goes_where_sixthsense_user_dir_points():
    """The tests' way off the real save; without it, the save is in %APPDATA%\\SixthSense."""
    old_dir, old_appdata = os.environ.get(paths.USER_DIR_ENV), os.environ.get('APPDATA')
    top = tempfile.mkdtemp()
    try:
        mine = os.path.join(top, 'mine')
        os.environ[paths.USER_DIR_ENV] = mine
        assert paths.user_dir() == mine and os.path.isdir(mine)
        os.environ.pop(paths.USER_DIR_ENV)
        os.environ['APPDATA'] = top
        assert paths.user_dir() == os.path.join(top, 'SixthSense')
    finally:
        for key, old in ((paths.USER_DIR_ENV, old_dir), ('APPDATA', old_appdata)):
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
        shutil.rmtree(top, ignore_errors=True)


def test_every_test_file_keeps_off_the_real_save():
    """Each test file imports _scratch_save before the game, so none can write the real save,
    whichever shell runs it."""
    here = os.path.dirname(os.path.abspath(__file__))
    forgot = []
    for name in sorted(os.listdir(here)):
        if name.endswith('.py') and not name.startswith('_'):
            with open(os.path.join(here, name), encoding='utf-8') as fh:
                if '\nimport _scratch_save' not in fh.read():
                    forgot.append(name)
    assert not forgot, 'these do not import _scratch_save: %s' % ', '.join(forgot)
    assert os.environ.get(paths.USER_DIR_ENV) == _scratch_save.FOLDER


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
