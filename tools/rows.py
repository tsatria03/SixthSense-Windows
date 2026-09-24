# -*- coding: utf-8 -*-
"""Pull a blind-mode screen's row table and its double-tap dispatch out of a class.

Every screen in this game is built the same way (``aidocks/GAME_STRUCTURE.md`` §8):

    -[X selectTapPointSoundStart]   maps the finger's Y to a band, stores the band in
                                    ``selectMenu`` and plays that row's WAV
    -[X tapCount]                   a ``tbb`` jump table on ``selectMenu - 1``: what a
                                    double tap on that row does

This prints both, so a screen can be ported without reading a thousand lines of
address arithmetic by hand.

    python tools/rows.py mainStoreController
    python tools/rows.py StoreController DetailStoreController
"""
import os
import plistlib
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import mb as B                                                       # noqa: E402

SOUNDS = plistlib.load(open(os.path.join(ROOT, 'game', 'SoundList.plist'), 'rb'))


def _name(num):
    return SOUNDS[num] if 0 <= num < len(SOUNDS) else '?'


def _body(cls, method):
    path = os.path.join(ROOT, 'analysis', 'disasm', 'dc_%s.txt' % cls)
    if not os.path.exists(path):
        return None
    txt = open(path, encoding='utf-8').read()
    key = '//// -[%s %s]' % (cls, method)
    if key not in txt:
        return None
    return txt.split(key)[1].split('\n//// ')[0]


def rows(cls):
    """selectMenu = N ... playSound(S) pairs, in the order they appear."""
    body = _body(cls, 'selectTapPointSoundStart')
    if body is None:
        print('  (no selectTapPointSoundStart)')
        return
    cur = None
    seen = []
    for line in body.split('\n'):
        m = re.search(r'self->selectMenu = (\d+)', line)
        if m:
            cur = int(m.group(1))
            continue
        m = re.search(r'self->(\w*[Ff]lag) = 1\b', line)
        flag = m.group(1) if m else None
        m = re.search(r'playSound:Gain:Pos:z:reprats:\]\((\d+),', line)
        if m and cur is not None:
            sound = int(m.group(1))
            key = (cur, sound)
            if key in seen:                       # the second device layout
                continue
            seen.append(key)
            print('  row %-3d sound %-4d %s' % (cur, sound, _name(sound)))
        elif flag:
            print('           (flag %s)' % flag)
    for line in body.split('\n'):
        m = re.search(r'SEL\((Read\w+|\w+Action:)\)', line)
        if m:
            pass


def readers(cls):
    """Whatever selectTapPointSoundStart schedules behind a label."""
    body = _body(cls, 'selectTapPointSoundStart')
    if body is None:
        return
    out = []
    for line in body.split('\n'):
        m = re.search(r'r2 = SEL\((\w+)\)', line)
        if m and m.group(1) not in out and not m.group(1).endswith(':'):
            out.append(m.group(1))
    if out:
        print('  scheduled: %s' % ', '.join(out))


def dispatch(cls):
    """Decode the tbb table in -[cls tapCount]."""
    body = _body(cls, 'tapCount')
    if body is None:
        print('  (no tapCount)')
        return
    head = body.split('\n')[0]
    m = re.search(r'0x([0-9a-f]+)\.\.0x([0-9a-f]+)', head)
    if not m:
        return
    lo, hi = int(m.group(1), 16), int(m.group(2), 16)
    code = B.rd(lo, hi - lo)

    # find `cmp rN, #k` followed by `bhi` and `tbb [pc, rN]`: 0x2f 0xe8 ... is tbb.w,
    # the short form is 0xdf 0xe8 0x00 0xf0.  Look for the encoding directly.
    idx = code.find(b'\xdf\xe8\x00\xf0')
    if idx < 0:
        print('  (no tbb - dispatch is an if/else chain)')
        _selectors(body)
        return
    base = lo + idx + 4
    # the `cmp rN, #k` two halfwords before the tbb gives the case count
    cmp_hw = code[idx - 2] | (code[idx - 1] << 8)
    count = (cmp_hw & 0xFF) + 1 if (cmp_hw & 0xF800) == 0x2800 else 8
    table = code[idx + 4: idx + 4 + count]
    print('  tbb at 0x%05x, %d cases, bytes %s'
          % (base, count, ' '.join('%02x' % b for b in table)))
    targets = [base + 2 * b for b in table]
    for i, t in enumerate(targets):
        print('    selectMenu %-3d -> 0x%05x%s'
              % (i + 1, t, '   (falls through to the end)'
                 if t >= hi - 0x30 else ''))
    _selectors(body, targets)


def _selectors(body, targets=None):
    """The selectors the dispatch blocks reach, with their addresses."""
    for line in body.split('\n'):
        m = re.match(r'\s*([0-9a-f]{4,6})\s+r\d+ = SEL\((\w+:?)\)', line)
        if not m:
            continue
        sel = m.group(2)
        if sel in ('performSelector:', 'playSound:Gain:Pos:z:reprats:', 'bDevice',
                   'StopElseSpeak', 'selectTapPointSoundStart'):
            continue
        print('    0x%s  %s' % (m.group(1), sel))


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    for cls in argv:
        print('==== %s ====' % cls)
        print('  -- rows --')
        rows(cls)
        readers(cls)
        print('  -- double tap --')
        dispatch(cls)
        print()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
