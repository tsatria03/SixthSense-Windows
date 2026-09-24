"""Where the game finds its files: ``paths.path_for_resource``.

The original bundle is flat; the port keeps its sounds in folders under
``game/sounds/used`` (docs/DIVERGENCES.md).  Each test builds a small bundle of its own in
a temporary folder, so these check the lookup itself rather than the shipped data - that
is ``test_data.py``'s job - and they never touch the save or play a sound.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

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


def test_the_unused_folder_is_never_searched():
    top = _bundle(['sounds/unused/sfx/misc/menuclick.wav'])
    try:
        assert _found(top, 'menuclick', 'wav') is None
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
