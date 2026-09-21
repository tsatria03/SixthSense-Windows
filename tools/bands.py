# -*- coding: utf-8 -*-
"""Recover a blind-mode screen's rows in the order they sit on the screen.

``-[X selectTapPointSoundStart]`` is one long chain of

    if (y > LOW && y < HIGH) { selectMenu = N; if (!flag) { flag = 1; play(sound); } }

with a second copy of every band for the other screen height.  The ``Y`` bounds are
float literals in the pool, so this pairs each ``selectMenu = N`` store with the two
floats loaded just before it and sorts the rows by where they are on the screen.

    python tools/bands.py mainStoreController
"""
import os
import plistlib
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

SOUNDS = plistlib.load(open(os.path.join(ROOT, 'game', 'SoundList.plist'), 'rb'))
FLOAT = re.compile(r'^0x([0-9a-f]+)\s+vldr\s+s\d+, \[pc.*?;\s*s\d+ = ([-\d.]+)')
ADDR = re.compile(r'^\s*([0-9a-f]{4,6})\s')


def _method(cls, name):
    path = os.path.join(ROOT, 'analysis', 'disasm', 'dc_%s.txt' % cls)
    txt = open(path, encoding='utf-8').read()
    key = '//// -[%s %s]' % (cls, name)
    if key not in txt:
        return None, None, None
    body = txt.split(key)[1].split('\n//// ')[0]
    head = body.split('\n')[0]
    m = re.search(r'0x([0-9a-f]+)\.\.0x([0-9a-f]+)', head)
    return body, int(m.group(1), 16), int(m.group(2), 16)


def bands(cls):
    body, lo, hi = _method(cls, 'selectTapPointSoundStart')
    if body is None:
        print('  (no selectTapPointSoundStart)')
        return []
    out = subprocess.run([sys.executable, os.path.join(HERE, 'dz.py'),
                          hex(lo), hex(hi)], capture_output=True, text=True,
                         cwd=HERE).stdout
    floats = {}
    for line in out.split('\n'):
        m = FLOAT.match(line.strip())
        if m:
            floats[int(m.group(1), 16)] = float(m.group(2))

    rows, cur = [], None
    for line in body.split('\n'):
        m = re.search(r'\s*([0-9a-f]{4,6})\s+self->selectMenu = (\d+)', line)
        if m:
            at = int(m.group(1), 16)
            near = sorted(v for a, v in floats.items() if 0 < at - a < 0x90)
            cur = {'at': at, 'row': int(m.group(2)), 'y': near, 'sound': None}
            rows.append(cur)
            continue
        m = re.search(r'playSound:Gain:Pos:z:reprats:\]\((\d+),', line)
        if m and cur is not None and cur['sound'] is None:
            cur['sound'] = int(m.group(1))
            cur = None
    return [r for r in rows if r['row']]


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    for cls in argv:
        print('==== %s ====' % cls)
        rows = bands(cls)
        # The taller layout is whichever set of bands has the larger bottom edge;
        # both list the rows in the same order, so one copy is enough.
        seen = {}
        for r in rows:
            seen.setdefault(r['row'], r)
        for r in sorted(seen.values(), key=lambda r: (r['y'] or [9999])[0]):
            snd = r['sound']
            print('  y %-28s row %-3d sound %-5s %s'
                  % (r['y'][:3] if r['y'] else '?', r['row'],
                     snd if snd is not None else '-',
                     SOUNDS[snd] if snd is not None and snd < len(SOUNDS) else ''))
        print()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
