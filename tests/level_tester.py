#!/usr/bin/env python
"""PORT ADDITION, for testing by ear: start the stage at any level, in any area, from
any row of the corridor.  Not a test, and not part of the game - the test runs skip it,
since its name does not start with ``test_``.

    python tests\\level_tester.py 2                 level 2
    python tests\\level_tester.py 3 --mode forest   level 3, in the forest
    python tests\\level_tester.py 2 --boss          level 2, a few steps before the siren
    python tests\\level_tester.py 1 --row 300       level 1, from row 300
    python tests\\level_tester.py                   asks for the level, the area and
                                                    whether to start near the boss

What a level is, from the binary: ``ChangeLevel:`` multiplies ``monsterHPGain`` by 1.5
(0x32314), which scales every new monster's health and step (0x10724, 0x10848), and
``MainControl`` adds one to ``LVUP`` (0x31c80), which lets one more monster out at a
time (0x3612e).  The area goes from the cave to the forest and back (0x31c8c); the rain
only ever comes on level 1.  Level N here is exactly what walking there would give you.

Starting part-way down the corridor replays the action cells above the start row, so the
spawn tier, the quiet stretch and the level music are what they would have been.

**Your save is never touched.**  It plays on its own save in
``%APPDATA%\\SixthSense\\level_tester``, marked as past the tutorial, and takes a fresh copy
of your key bindings each time it starts.  Gold and scores earned here stay there.

Everything else is the real game: Escape pauses and resumes, the pause panel's Main menu
row goes back to the menu, and Start Game from that menu starts the tester's level again.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

MODES = {'cave': 1, 'forest': 2, 'rain': 3}
START_ROW = 680           # 0x2cf1a
SIREN_ROW = 29            # 0x31ab2
BOSS_ROW = 23             # 0x31cfc
#: --boss starts here: two steps before the siren, and the girl or the woman zombie
#: that action cell 8 sends at the siren.
NEAR_BOSS_ROW = SIREN_ROW + 2


def _own_save():
    """Point APPDATA at the tester's own folder, before anything reads it."""
    real = os.path.join(os.environ.get('APPDATA') or os.path.expanduser('~'),
                        'SixthSense')
    mine = os.path.join(real, 'level_tester')
    os.makedirs(os.path.join(mine, 'SixthSense'), exist_ok=True)
    keys = os.path.join(real, 'keys.json')
    if os.path.exists(keys):
        shutil.copyfile(keys, os.path.join(mine, 'SixthSense', 'keys.json'))
    os.environ['APPDATA'] = mine


def _mode_for(level, first):
    """The area level ``level`` is in, when level 1 was ``first``: 0x31c8c turns the
    cave into the forest and anything else into the cave."""
    mode = first
    for _ in range(level - 1):
        mode = 2 if mode == 1 else 1
    return mode


def _ask(question, check):
    """Ask until ``check`` accepts the answer; Enter alone gives ''.  With no console to
    ask on, the answer is ''."""
    while True:
        try:
            answer = input(question + ' ').strip().lstrip('﻿').lower()
        except EOFError:
            return ''
        ok = check(answer)
        if ok is not None:
            return ok
        print('Sorry, that is not one of the choices.')


def _questions():
    """Opened with nothing after its name, the tester asks instead."""
    argv = []
    level = _ask('Level to start on (1 and up, Enter for 1):',
                 lambda a: '' if a == '' else (a if a.isdigit() and int(a) >= 1 else None))
    if level:
        argv.append(level)
    mode = _ask("Area: cave, forest or rain (Enter for the game's choice):",
                lambda a: a if a in ('',) + tuple(MODES) else None)
    if mode:
        argv += ['--mode', mode]
    boss = _ask('Start near the boss? (y or n, Enter for no):',
                lambda a: a[:1] if a[:1] in ('', 'y', 'n') else None)
    if boss == 'y':
        argv.append('--boss')
    return argv


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:] or _questions()
    ap = argparse.ArgumentParser(description='Start SixthSense at any level.')
    ap.add_argument('level', nargs='?', type=int, default=1,
                    help='the level to start on, 1 and up (default 1)')
    ap.add_argument('--mode', choices=sorted(MODES),
                    help='the area; left out, level 1 is random as in the game and '
                         'later levels follow from it')
    start = ap.add_mutually_exclusive_group()
    start.add_argument('--row', type=int,
                       help='the corridor row to start on, %d (the start) down to %d'
                            % (START_ROW, BOSS_ROW + 1))
    start.add_argument('--boss', action='store_true',
                       help='start just before the siren, the girl or woman zombie, '
                            'and the boss')
    ap.add_argument('-v', '--verbose', action='store_true')
    args = ap.parse_args(argv)

    if args.level < 1:
        ap.error('the level starts at 1')
    row = NEAR_BOSS_ROW if args.boss else (args.row or START_ROW)
    if not BOSS_ROW < row <= START_ROW:
        ap.error('the row must be from %d down to %d' % (START_ROW, BOSS_ROW + 1))

    _own_save()

    import SixthSense
    from sixthsense.game.stage_1_e import Stage_1_E
    from sixthsense.platform import volume
    from sixthsense.platform.defaults import UserDefaults

    d = UserDefaults.standardUserDefaults()
    d.setObject_forKey_('1', 'TUTORIAL')      # the stage only walks once it is set
    d.synchronize()

    class LevelStage(Stage_1_E):
        """The stage, put where the tester asked before it starts walking."""

        def viewDidLoad(self):
            super().viewDidLoad()             # rolls level 1's area, as the game does
            first = MODES[args.mode] if args.mode else self.gameMode
            self.gameMode = first if args.mode else _mode_for(args.level, first)
            self._set_level()

        def _set_level(self):
            self.LVUP = args.level
            self.monsterHPGain = 1.5 ** (args.level - 1)

        def MapInitInBundle(self):
            super().MapInitInBundle()
            if row != START_ROW:
                self._walk_to(row)

        def _walk_to(self, y):
            """Stand on row ``y`` as though the corridor above it had been walked:
            every action cell passed is replayed, except the monsters it sent."""
            music = False
            for passed in range(START_ROW, y, -1):
                cell = self.stage.movePlayActionState_PlotY_(
                    self.gamePlayer.playerXplot, passed)
                if cell == 9:
                    self.monster_num = 9
                    music = False
                elif cell == 10:
                    music = True
                elif 1 <= cell <= 7:
                    self.monster_num = cell
            self.gamePlayer.playerYplot = y
            if music:
                # the same as MainControl's action cell 10 (0x321d4)
                name = 'bgm_forest' if self.gameMode >= 2 else 'bgm_cave'
                self.app.playback.startBGPlayer_type_soundGain_Loop_(
                    name, 'wav', volume.music(0.02), True)

        def gameReplayAction_(self, *a):
            # a restart puts LVUP and monsterHPGain back to level 1 (0x334fc, 0x3350c)
            done = super().gameReplayAction_(*a)
            if done:
                self._set_level()
            return done

    def new_stage():
        st = LevelStage()
        st.viewDidLoad()
        return st

    SixthSense._new_stage = new_stage
    print('Level %d, %s, from row %d.  Your own save is not used.'
          % (args.level, args.mode or 'area as the game picks it', row))
    return SixthSense.main(['--stage'] + (['-v'] if args.verbose else []))


if __name__ == '__main__':
    sys.exit(main())
