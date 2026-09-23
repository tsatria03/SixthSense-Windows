"""PORT ADDITION: the debug commands, live only with ``--debug``.

The original has nothing like them.  In debug mode nothing takes a heart and nothing you
kill counts (``Stage_1_E``, ``AppDelegate.debug``); these keys are for trying the game
out by ear.  They are keymap actions, so the F1 screen lists and rebinds them:

    F2          the start of the next section of the corridor, in the same level
    Shift+F2    next level, the way the end of a level goes; after level 8, level 1
    F5          spawn the chosen zombie, in the lane you last attacked
    Shift+F5    choose what F5 spawns
    F6          hold every zombie where it is, or let them walk again
    F7          let zombies that reach you hit you, still for no heart, or die again
    F11         say where each zombie is

Debug mode also hands you every weapon on Tab and Shift+Tab, bought or not, and no
shot, no grenade and no magazine ever runs out (``Stage_1_E``).

Everything here speaks through the screen reader, whatever the voice over row says:
the game has no recordings for any of it.  They do nothing in the tutorial, which
runs on its own script, and F2 and Shift+F2 do nothing in the weapon test range,
where you never walk.
"""
from __future__ import annotations

import time

from .stage_1_e import (BOSS_CAVE, BOSS_FOREST, BOSS_NUMBER, MONSTER_GIRL,
                        MONSTER_WOMAN, SOUND_WARNING)

START_ROW = 680                     # 0x2cf1a, where every level starts
#: Shift+F2 goes round the levels: after this one comes level 1 again.
MAX_LEVEL = 8
#: How long F2 waits before it will jump again: as long as Shift+F2's level change
#: takes, ``ChangeLevel:`` 2 s after the end (0x31d92).
SECTION_SECONDS = 2.0

#: What F5 can spawn, in the order Shift+F5 goes through them: the name spoken, and
#: the type id for a lane (``MONSTER_ARRAY``'s ``kind*10 + lane``, the first kind
#: bare; 10001.. the girl, 10006.. the woman).  The boss has one id per area.
SPAWNS = (
    [('Zombie 1', lambda lane: lane)]
    + [('Zombie 8, the one that grabs you' if k == 8 else 'Zombie %d' % k,
        lambda lane, k=k: (k - 1) * 10 + lane) for k in range(2, 11)]
    + [('The woman zombie', lambda lane: 10005 + lane),
       ('The girl who heals you', lambda lane: 10000 + lane),
       ('The boss', None)]
)

CLOCK = {1: "9 o'clock", 2: '10:30', 3: "12 o'clock", 4: '1:30', 5: "3 o'clock"}


def _in_tutorial(st):
    if getattr(st, 'ESCAPE_LEAVES', False):
        st._say('Debug commands work in a stage, not the tutorial.')
        return True
    return False


def perform(st, action, lane):
    """Run one ``debug_`` action; ``lane`` is the lane last attacked, 1..5."""
    if _in_tutorial(st):
        return
    if (action in ('debug_next_level', 'debug_next_section')
            and getattr(st, 'IS_TEST_RANGE', False)):
        st._say('The weapon test range has no levels or sections.')
        return
    {'debug_next_level': next_level,
     'debug_next_section': next_section,
     'debug_spawn': lambda s: spawn(s, lane),
     'debug_spawn_kind': next_spawn_kind,
     'debug_freeze': toggle_freeze,
     'debug_hits': toggle_hits,
     'debug_monsters': say_monsters}[action](st)


def area_name(st):
    return {1: 'cave', 2: 'forest', 3: 'forest in the rain'}.get(st.gameMode, '')


def next_level(st):
    """What ``MainControl`` does when the boss is dead and you are at the end: every
    zombie left dies, and ``ChangeLevel:`` follows 2 s later.  After ``MAX_LEVEL``
    it goes round to level 1, with level 1's zombies."""
    if st.MotionSamplingTimer is None or not st.MotionSamplingTimer.isValid():
        st._say('Not while the level is changing.')
        return
    st.app.stopSoundBufNumber_(SOUND_WARNING)       # the alarm, if it had started
    wrap = st.LVUP >= MAX_LEVEL
    st._level_transition()
    if wrap:
        st.LVUP = 1
        # ChangeLevel: multiplies this by 1.5 as it lands (0x32314), giving level 1's 1.0.
        st.monsterHPGain = 1.0 / 1.5
    st._say('Level %d, %s.' % (st.LVUP, area_name(st)))


def sections(st):
    """The rows each section of the corridor starts on, top of the corridor first:
    the rows on your path whose action cell is 9, the quiet stretch that opens each
    one.  The last is the boss's."""
    x = st.gamePlayer.playerXplot
    return [y for y in range(START_ROW, 0, -1)
            if st.stage.movePlayActionState_PlotY_(x, y) == 9]


def next_section(st):
    """Walk straight to the start of the next section.  The zombies around you die
    where they are, but not the girl, who walks on and still thanks you, and the next
    tick reads the section's own cell 9 as walking there would, so its quiet stretch,
    its tier and its music follow on their own."""
    if st.MotionSamplingTimer is None or not st.MotionSamplingTimer.isValid():
        st._say('Not while the section is changing.')
        return
    if time.monotonic() < getattr(st, 'debugSectionReady', 0.0):
        st._say('Not while the section is changing.')
        return
    if st.isShake:
        st._say('Not while a zombie holds you.')
        return
    rows = sections(st)
    ahead = [y for y in rows if y < st.gamePlayer.playerYplot]
    if not ahead:
        st._say('This is the last section. Shift+F2 goes to the next level.')
        return
    for m in list(st.MonsterBuffer):
        if m.monsterNumber != MONSTER_GIRL:
            m.DieMonster()
            st._remove(m)
    st.gamePlayer.playerYplot = ahead[0]
    st.debugSectionReady = time.monotonic() + SECTION_SECONDS
    st._say('Section %d of %d.' % (rows.index(ahead[0]) + 1, len(rows)))


def next_spawn_kind(st):
    st.debugSpawn = (st.debugSpawn + 1) % len(SPAWNS)
    st._say(SPAWNS[st.debugSpawn][0])


def spawn(st, lane):
    name, type_for = SPAWNS[st.debugSpawn]
    if type_for is None:
        type_id = BOSS_CAVE if st.gameMode == 1 else BOSS_FOREST
        lane = 3                                    # the boss comes down the middle
    else:
        type_id = type_for(lane)
    before = len(st.MonsterBuffer)
    st.MonsterInit_(type_id)
    if len(st.MonsterBuffer) == before:
        st._say('%s cannot come now; every voice it has is in use.' % name)
        return
    st._say('%s, %s.' % (name, CLOCK.get(lane, '')))


def toggle_freeze(st):
    st.monstersFrozen = not st.monstersFrozen
    for m in st.MonsterBuffer:
        m.frozen = st.monstersFrozen
    st._say('Zombies hold still.' if st.monstersFrozen else 'Zombies walk again.')


def toggle_hits(st):
    st.debugHits = not st.debugHits
    st._say('Zombies hit you, but take no heart.' if st.debugHits
            else 'Zombies die when they reach you.')


def monster_name(m):
    n = m.monsterNumber
    if n == MONSTER_GIRL:
        return 'The girl'
    if n == MONSTER_WOMAN:
        return 'The woman zombie'
    if n in BOSS_NUMBER.values():
        return 'The boss'
    return 'Zombie %d' % n


def monsters_text(st):
    if not st.MonsterBuffer:
        return 'No zombies.'
    out = []
    for m in sorted(st.MonsterBuffer, key=lambda m: m.monsterRange):
        where = CLOCK.get(m.MovingType, 'zig-zag')
        line = '%s, %s, %.1f metres' % (monster_name(m), where, m.monsterRange / 100.0)
        if m.headShotFlag:
            line += ', head open'
        out.append(line + '.')
    return ' '.join(out)


def say_monsters(st):
    st._say(monsters_text(st))
