"""The save files: ``UserDefaults`` never writes over a save it could not read, keeps
progress in save.json and settings in settings.json, and moves an old defaults.json over.

Every test points ``SIXTHSENSE_USER_DIR`` at a throwaway folder of its own, so the real
save is never read or written.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import _scratch_save                                             # noqa: E402,F401  never the real save

from sixthsense import paths                                     # noqa: E402
from sixthsense.platform.defaults import UserDefaults            # noqa: E402


class _Folder:
    """A fresh save folder for one test, put back afterwards."""

    def __enter__(self):
        self.old = os.environ.get(paths.USER_DIR_ENV)
        self.top = tempfile.mkdtemp()
        self.dir = os.path.join(self.top, 'SixthSense')
        os.environ[paths.USER_DIR_ENV] = self.dir
        return self

    def __exit__(self, *exc):
        if self.old is None:
            os.environ.pop(paths.USER_DIR_ENV, None)
        else:
            os.environ[paths.USER_DIR_ENV] = self.old
        shutil.rmtree(self.top, ignore_errors=True)

    def file(self, name='save.json'):
        return os.path.join(self.dir, name)

    def read(self, name='save.json'):
        with open(self.file(name), encoding='utf-8') as fh:
            return json.load(fh)

    def write(self, name, text):
        os.makedirs(self.dir, exist_ok=True)
        with open(self.file(name), 'w', encoding='utf-8') as fh:
            fh.write(text)


def _save(**keys):
    d = UserDefaults()
    for k, v in keys.items():
        d.setObject_forKey_(v, k)
    d.synchronize()
    return d


def test_each_save_keeps_the_one_before_as_a_backup():
    with _Folder() as f:
        _save(GOLD='5000')
        _save(GOLD='6000')
        with open(f.file('save.json.bak'), encoding='utf-8') as fh:
            assert json.load(fh)['GOLD'] == '5000'
        assert UserDefaults().intForKey_('GOLD') == 6000


def test_a_damaged_save_is_kept_and_the_backup_carries_on():
    with _Folder() as f:
        _save(GOLD='5000', SHOTGUN='1')
        _save(GOLD='6000', SHOTGUN='1')
        with open(f.file(), 'w', encoding='utf-8') as fh:
            fh.write('{"GOLD": "60')                  # cut off mid-write
        d = UserDefaults()
        assert d.intForKey_('GOLD') == 5000, 'the backup was not loaded'
        assert d.intForKey_('SHOTGUN') == 1, 'the weapons were lost'
        with open(f.file('save.json.damaged'), encoding='utf-8') as fh:
            assert fh.read() == '{"GOLD": "60', 'the damaged save was not kept as it was'
        with open(f.file(), encoding='utf-8') as fh:
            assert json.load(fh)['GOLD'] == '5000', 'the recovered save was not written back'


def test_a_save_that_is_not_an_object_does_not_crash():
    with _Folder() as f:
        os.makedirs(f.dir, exist_ok=True)
        with open(f.file(), 'w', encoding='utf-8') as fh:
            fh.write('[1, 2, 3]')
        d = UserDefaults()
        assert d.intForKey_('GOLD') == 0
        d.setObject_forKey_('12', 'GOLD')
        d.synchronize()
        with open(f.file('save.json.damaged'), encoding='utf-8') as fh:
            assert fh.read() == '[1, 2, 3]', 'the damaged save was written over'


def test_a_deleted_save_starts_over():
    """Deleting the save is how a player starts again, so the backup must not
    bring it back."""
    with _Folder() as f:
        _save(GOLD='5000')
        _save(GOLD='6000')
        os.remove(f.file())
        assert UserDefaults().intForKey_('GOLD') == 0


# ---- the split: save.json, settings.json and keys.json (tsatria03, 2026-09-25) ---------------

def test_progress_goes_to_save_json_and_settings_to_settings_json():
    with _Folder() as f:
        _save(GOLD='5000', SHOTGUN='1', EYEMODE='0', MENUMUSICVOLUME=70)
        save, settings = f.read(), f.read('settings.json')
        assert save == {'GOLD': '5000', 'SHOTGUN': '1'}, save
        assert settings == {'MENUMUSICVOLUME': 70, 'EYEMODE': '0'}, settings
        assert not os.path.exists(f.file('defaults.json')), 'the old file was written'
        d = UserDefaults()
        assert d.intForKey_('GOLD') == 5000 and d.intForKey_('EYEMODE') == 0
        assert d.objectForKey_('MENUMUSICVOLUME') == 70


def test_a_new_key_is_progress():
    """Anything not named as a setting is kept in the save, the safe place for it."""
    with _Folder() as f:
        _save(SOMETHINGNEW='1')
        assert f.read()['SOMETHINGNEW'] == '1'
        assert 'SOMETHINGNEW' not in f.read('settings.json')


def test_settings_json_is_written_in_its_own_order():
    """Not sorted by name: the order SETTINGS_KEYS gives."""
    from sixthsense.platform.defaults import SETTINGS_KEYS
    with _Folder() as f:
        _save(EYEMODE='1', MENUMUSICVOLUME=100)
        with open(f.file('settings.json'), encoding='utf-8') as fh:
            text = fh.read()
        order = [k for k in SETTINGS_KEYS if k in text]
        assert sorted(order, key=text.index) == order, text


def test_an_old_defaults_json_is_moved_over_and_kept():
    with _Folder() as f:
        f.write('defaults.json', json.dumps({'GOLD': '7000', 'COIN': '3', 'M4': '1',
                                              'EYEMODE': '0', 'MENUMUSICVOLUME': 40}))
        d = UserDefaults()
        assert d.intForKey_('GOLD') == 7000 and d.intForKey_('M4') == 1
        assert d.intForKey_('EYEMODE') == 0 and d.objectForKey_('MENUMUSICVOLUME') == 40
        assert f.read() == {'COIN': '3', 'GOLD': '7000', 'M4': '1'}
        assert f.read('settings.json') == {'MENUMUSICVOLUME': 40, 'EYEMODE': '0'}
        assert not os.path.exists(f.file('defaults.json')), 'the old file was left in place'
        assert json.loads(open(f.file('defaults.json.old'), encoding='utf-8').read())['GOLD'] \
            == '7000', 'the old file was not kept'
        # and the next start reads save.json, not the old one again
        assert UserDefaults().intForKey_('GOLD') == 7000


def test_a_damaged_old_defaults_json_moves_its_backup_over():
    with _Folder() as f:
        f.write('defaults.json', '{"GOLD": "70')
        f.write('defaults.json.bak', json.dumps({'GOLD': '6500', 'EYEMODE': '0'}))
        d = UserDefaults()
        assert d.intForKey_('GOLD') == 6500, 'the old backup was not used'
        assert d.intForKey_('EYEMODE') == 0
        with open(f.file('defaults.json.damaged'), encoding='utf-8') as fh:
            assert fh.read() == '{"GOLD": "70', 'the damaged old save was not kept'
        assert f.read()['GOLD'] == '6500'


def test_an_old_defaults_json_beside_a_save_is_left_alone():
    with _Folder() as f:
        _save(GOLD='100')
        f.write('defaults.json', json.dumps({'GOLD': '9999'}))
        assert UserDefaults().intForKey_('GOLD') == 100
        assert os.path.exists(f.file('defaults.json')), 'it was moved over a save'


def test_a_damaged_settings_json_carries_on_from_its_backup():
    with _Folder() as f:
        _save(EYEMODE='0')
        _save(EYEMODE='1')
        f.write('settings.json', '{"EYEMO')
        d = UserDefaults()
        assert d.intForKey_('EYEMODE') == 0, 'the settings backup was not loaded'
        with open(f.file('settings.json.damaged'), encoding='utf-8') as fh:
            assert fh.read() == '{"EYEMO'


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
