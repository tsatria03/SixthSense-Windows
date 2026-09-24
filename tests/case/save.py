"""The save file: ``UserDefaults`` never writes over a save it could not read.

Every test points ``APPDATA`` at a throwaway folder of its own, so the real save is never
read or written.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sixthsense.platform.defaults import UserDefaults            # noqa: E402


class _Folder:
    """A fresh APPDATA for one test, put back afterwards."""

    def __enter__(self):
        self.old = os.environ.get('APPDATA')
        self.top = tempfile.mkdtemp()
        os.environ['APPDATA'] = self.top
        self.dir = os.path.join(self.top, 'SixthSense')
        return self

    def __exit__(self, *exc):
        if self.old is None:
            os.environ.pop('APPDATA', None)
        else:
            os.environ['APPDATA'] = self.old
        shutil.rmtree(self.top, ignore_errors=True)

    def file(self, name='defaults.json'):
        return os.path.join(self.dir, name)


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
        with open(f.file('defaults.json.bak'), encoding='utf-8') as fh:
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
        with open(f.file('defaults.json.damaged'), encoding='utf-8') as fh:
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
        with open(f.file('defaults.json.damaged'), encoding='utf-8') as fh:
            assert fh.read() == '[1, 2, 3]', 'the damaged save was written over'


def test_a_deleted_save_starts_over():
    """Deleting the save is how a player starts again, so the backup must not
    bring it back."""
    with _Folder() as f:
        _save(GOLD='5000')
        _save(GOLD='6000')
        os.remove(f.file())
        assert UserDefaults().intForKey_('GOLD') == 0


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
