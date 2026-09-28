"""Measure every sound the game plays and write the trims that level them all.

Reads each WAV in ``game/sounds/used/``, measures its integrated loudness (ITU-R BS.1770:
K-weighted, 400 ms blocks, gated at -70 LUFS and 10 LU under the mean) and its sample
peak, and gives it the trim that brings it to ``TARGET_LUFS``, a boost no more than
``MAX_BOOST_DB``, and never a cut in ``NEVER_CUT``.  Then it rewrites the ``MEASURED`` block of
``sixthsense/platform/sound_trims.py``; ``BY_EAR`` is never touched.
aidocks/project_sound_trims_plan.md has why.

It prints one line per file, folder by folder, and makes no sound.  Standard library
only.

    python tools/sound_trims.py             measure, print and write
    python tools/sound_trims.py --dry-run   measure and print only
"""
from __future__ import annotations

import array
import math
import os
import sys
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sixthsense.game.oal_playback import MONO_AT_LOAD, _fold_to_mono    # noqa: E402

USED = os.path.join(ROOT, 'game', 'sounds', 'used')
TABLE = os.path.join(ROOT, 'sixthsense', 'platform', 'sound_trims.py')
BEGIN, END = '# ---- MEASURED begin ----', '# ---- MEASURED end ----'

#: The one loudness every sound is brought to (tunmi13productions, 2026-09-27: "let's try option
#: 2"; the game's median is -16.9 and nine files in ten are under -11.9).
TARGET_LUFS = -12.0
#: No boost is more than this: a gain of 3.98, under the sources' AL_MAX_GAIN of 4.0.
MAX_BOOST_DB = 12.0
#: Trims are rounded to this, and a smaller one is left out.
STEP_DB = 0.5
#: The folders under used/ whose sounds are only ever boosted: the zombies, the bosses,
#: the monster and the woman, which the player listens for (tunmi13productions, 2026-09-28;
#: aidocks/project_entity_full_volume_plan.md).
NEVER_CUT = ('sfx/zombies', 'sfx/monsters', 'sfx/characters')


def read(path, name):
    """The file's channels as lists of samples, folded to mono as the game folds it."""
    with wave.open(path, 'rb') as w:
        ch, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
        pcm = w.readframes(w.getnframes())
    if width != 2:
        raise ValueError('%s is not 16-bit' % name)
    if name in MONO_AT_LOAD and ch == 2:
        pcm, ch = _fold_to_mono(pcm), 1
    a = array.array('h')
    a.frombytes(pcm)
    if sys.byteorder != 'little':
        a.byteswap()
    return [a[c::ch] for c in range(ch)], rate


def k_weighting(rate):
    """BS.1770's two biquads, the high shelf then the high pass, for any sample rate."""
    k = math.tan(math.pi * 1681.974450955533 / rate)
    q = 0.7071752369554196
    vh = 10.0 ** (3.999843853973347 / 20.0)
    vb = vh ** 0.4996667741545416
    a0 = 1.0 + k / q + k * k
    shelf = ((vh + vb * k / q + k * k) / a0, 2.0 * (k * k - vh) / a0,
             (vh - vb * k / q + k * k) / a0, 2.0 * (k * k - 1.0) / a0,
             (1.0 - k / q + k * k) / a0)
    k = math.tan(math.pi * 38.13547087602444 / rate)
    q = 0.5003270373238773
    a0 = 1.0 + k / q + k * k
    high_pass = (1.0, -2.0, 1.0, 2.0 * (k * k - 1.0) / a0, (1.0 - k / q + k * k) / a0)
    return shelf, high_pass


def loudness(channels, rate):
    """Integrated loudness in LUFS, or -inf for silence."""
    seg = max(1, rate // 10)                            # 100 ms; a block is four of them
    energies = []
    for samples in channels:
        (b0, b1, b2, a1, a2), (c0, c1, c2, d1, d2) = k_weighting(rate)
        x1 = x2 = y1 = y2 = z1 = z2 = 0.0
        segs, acc, n = [], 0.0, 0
        for s in samples:
            x = s / 32768.0
            y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
            z = c0 * y + c1 * y1 + c2 * y2 - d1 * z1 - d2 * z2
            x2, x1, y2, y1, z2, z1 = x1, x, y1, y, z1, z
            acc += z * z
            n += 1
            if n == seg:
                segs.append(acc)
                acc, n = 0.0, 0
        if n:
            segs.append(acc)
        energies.append(segs)
    count = len(energies[0])
    total = len(channels[0])
    if count < 4:                                       # shorter than a block: all of it
        blocks = [sum(sum(segs) for segs in energies) / max(1, total)]
    else:
        blocks = [sum(sum(segs[i:i + 4]) for segs in energies) / (4 * seg)
                  for i in range(count - 3)]
    blocks = [b for b in blocks if b > 0.0]

    def lufs(ms):
        return -0.691 + 10.0 * math.log10(ms)

    gated = [b for b in blocks if lufs(b) > -70.0]
    if not gated:
        return float('-inf')
    threshold = lufs(sum(gated) / len(gated)) - 10.0
    gated = [b for b in gated if lufs(b) > threshold]
    return lufs(sum(gated) / len(gated))


def peak_dbfs(channels):
    p = max(max(max(c), -min(c)) for c in channels if len(c))
    return 20.0 * math.log10(p / 32768.0) if p else float('-inf')


def measure():
    """(name, folder under used/, loudness, peak) for every WAV under used/."""
    out = []
    for folder, _dirs, files in os.walk(USED):
        for f in sorted(files):
            if not f.lower().endswith('.wav'):
                continue
            path = os.path.join(folder, f)
            name = f[:-4]
            channels, rate = read(path, name)
            out.append((name, os.path.relpath(folder, USED).replace(os.sep, '/'),
                        loudness(channels, rate), peak_dbfs(channels)))
    return out


def trim_for(level, folder=''):
    """The trim that brings ``level`` to ``TARGET_LUFS``, or 0.0 for silence, one under
    ``STEP_DB``, or a cut in a ``NEVER_CUT`` folder."""
    if level == float('-inf'):
        return 0.0
    t = min(MAX_BOOST_DB, round((TARGET_LUFS - level) / STEP_DB) * STEP_DB)
    if t < 0 and (folder + '/').startswith(tuple(f + '/' for f in NEVER_CUT)):
        return 0.0
    return t if abs(t) >= STEP_DB else 0.0


def trims(rows):
    """{name: trim} for every file whose trim is not 0."""
    return {r[0]: trim_for(r[2], r[1]) for r in rows if trim_for(r[2], r[1])}


def write(result, rows):
    with open(TABLE, encoding='utf-8') as f:
        text = f.read()
    start, end = text.index(BEGIN), text.index(END)
    folder = {r[0]: r[1] for r in rows}
    lines = [BEGIN, 'MEASURED: dict[str, float] = {']
    for fol in sorted({folder[n] for n in result}):
        lines.append('    # %s' % fol)
        for name in sorted(n for n in result if folder[n] == fol):
            lines.append('    %r: %.1f,' % (name, result[name]))
    lines.append('}')
    with open(TABLE, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text[:start] + '\n'.join(lines) + '\n' + text[end:])


def main(argv):
    rows = measure()
    result = trims(rows)
    print('target %.1f LUFS, boosts at most %+.1f dB' % (TARGET_LUFS, MAX_BOOST_DB))
    for fol in sorted({r[1] for r in rows}):
        print('%s:' % fol)
        for name, _f, level, peak in sorted(r for r in rows if r[1] == fol):
            short = ', short of the target' if TARGET_LUFS - level > MAX_BOOST_DB else ''
            print('  %s: %.1f LUFS, peak %.1f dBFS, trim %+.1f dB%s'
                  % (name, level, peak, result.get(name, 0.0), short))
    print('%d files trimmed, %d cut, %d boosted, %d short of the target'
          % (len(result), sum(t < 0 for t in result.values()),
             sum(t > 0 for t in result.values()),
             sum(TARGET_LUFS - r[2] > MAX_BOOST_DB for r in rows)))
    if '--dry-run' not in argv:
        write(result, rows)
        print('wrote %s' % os.path.relpath(TABLE, ROOT))


if __name__ == '__main__':
    main(sys.argv[1:])
