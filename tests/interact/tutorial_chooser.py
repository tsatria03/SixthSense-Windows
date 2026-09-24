#!/usr/bin/env python
"""PORT ADDITION, for testing by ear: start the tutorial at any lesson, with either of its
endings, and voice over on or off.  Not a test, and not part of the game: the tests are in
``tests\\case``, and this is one of the tools in ``tests\\interact`` that you play.

    python tests\\interact\\tutorial_chooser.py --lesson 9                  the animal zombie
    python tests\\interact\\tutorial_chooser.py --ending start --lesson 10  P, then 3, 2, 1 into the game
    python tests\\interact\\tutorial_chooser.py --voice off                 with the key hints
    python tests\\interact\\tutorial_chooser.py                             asks for all three

The two endings, from the binary (see ``stage_tutorial.py``):

    start   the tutorial a first Start runs: once it is over, P counts 3, 2, 1 and
            starts the real game with "zombies are coming"
    menu    the tutorial the Tutorial button runs: P goes back to the main menu

The ten lessons, in the order the tutorial teaches them:

     1  shooting at 9 o'clock         6  the stronger zombie
     2  shooting at 10:30             7  reloading
     3  shooting at 12 o'clock        8  changing weapon
     4  shooting at 1:30              9  shaking off the animal zombie
     5  shooting at 3 o'clock        10  ending the tutorial with P

Starting at a lesson counts every lesson before it as done, so the tutorial goes on from
there exactly as it would have, and lesson One is never heard.

Voice over is the main menu's voice over row.  The recorded instructions play either way;
with it off, the screen reader also names the keys to press for each one.

**Your save is never touched.**  It plays on its own save in
``%APPDATA%\\SixthSense\\tutorial_chooser``, and takes a fresh copy of your key bindings
each time it starts.  Choosing Tutorial from its main menu starts the chosen lesson again.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

ENDINGS = ('start', 'menu')
VOICES = ('on', 'off')

#: The lessons as the chooser numbers them, and the beat each one is in the tutorial's
#: own table (stage_tutorial.BEATS).
LESSONS = (
    ('One', "shooting at 9 o'clock"),
    ('Two', 'shooting at 10:30'),
    ('Three', "shooting at 12 o'clock"),
    ('Four', 'shooting at 1:30'),
    ('Five', "shooting at 3 o'clock"),
    ('FiveHalf', 'the stronger zombie'),
    ('Six', 'reloading'),
    ('Seven', 'changing weapon'),
    ('Eight', 'shaking off the animal zombie'),
    ('Nine', 'ending the tutorial with P'),
)


def _own_save():
    """Point APPDATA at the chooser's own folder, before anything reads it."""
    real = os.path.join(os.environ.get('APPDATA') or os.path.expanduser('~'),
                        'SixthSense')
    mine = os.path.join(real, 'tutorial_chooser')
    os.makedirs(os.path.join(mine, 'SixthSense'), exist_ok=True)
    keys = os.path.join(real, 'keys.json')
    if os.path.exists(keys):
        shutil.copyfile(keys, os.path.join(mine, 'SixthSense', 'keys.json'))
    os.environ['APPDATA'] = mine


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
    """Opened with nothing after its name, the chooser asks instead."""
    argv = []
    ending = _ask('Ending: start, which counts down into the game, or menu, which goes '
                  'back to the main menu (Enter for menu):',
                  lambda a: a if a in ('',) + ENDINGS else None)
    if ending:
        argv += ['--ending', ending]
    print('The lessons:')
    for number, (_beat, name) in enumerate(LESSONS, 1):
        print('  %d. %s' % (number, name))
    lesson = _ask('Lesson to start at, 1 to %d (Enter for 1):' % len(LESSONS),
                  lambda a: '' if a == '' else
                  (a if a.isdigit() and 1 <= int(a) <= len(LESSONS) else None))
    if lesson:
        argv += ['--lesson', lesson]
    voice = _ask('Voice over: on, or off for the key hints too (Enter for on):',
                 lambda a: a if a in ('',) + VOICES else None)
    if voice:
        argv += ['--voice', voice]
    return argv


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:] or _questions()
    ap = argparse.ArgumentParser(description='Start the SixthSense tutorial at any lesson.')
    ap.add_argument('--ending', choices=ENDINGS, default='menu',
                    help='start: P counts down into the real game, as after a first '
                         'Start; menu: P goes back to the main menu, as from the '
                         'Tutorial button (default menu)')
    ap.add_argument('--lesson', type=int, default=1,
                    help='the lesson to start at, 1 to %d (default 1): %s'
                         % (len(LESSONS), ', '.join('%d %s' % (n, name) for n, (_b, name)
                                                     in enumerate(LESSONS, 1))))
    ap.add_argument('--voice', choices=VOICES, default='on',
                    help='voice over on, or off, where the screen reader also names the '
                         'keys for each lesson (default on)')
    ap.add_argument('-v', '--verbose', action='store_true')
    args = ap.parse_args(argv)
    if not 1 <= args.lesson <= len(LESSONS):
        ap.error('the lesson must be from 1 to %d' % len(LESSONS))
    first_beat, lesson_name = LESSONS[args.lesson - 1]

    _own_save()

    import SixthSense
    from sixthsense.game.stage_tutorial import BEAT_NAMES, Stage_Tutorial
    from sixthsense.platform.defaults import UserDefaults

    d = UserDefaults.standardUserDefaults()
    d.setObject_forKey_('1' if args.voice == 'on' else '0', 'EYEMODE')
    d.synchronize()

    class LessonTutorial(Stage_Tutorial):
        """The tutorial, starting at the lesson the chooser was asked for."""

        def __init__(self, first_run=False):
            super().__init__(first_run=first_run)
            self._opened = False

        def MapInitInBundle(self):
            # Every lesson before the chosen one counts as done, so what the chosen one
            # needs (stage_tutorial.REQUIRES) is already met.
            for name in BEAT_NAMES[:BEAT_NAMES.index(first_beat)]:
                self.beat_done[name] = True
            super().MapInitInBundle()

        def tutorial_beat(self, name):
            # MapInitInBundle opens with lesson One (0x7e2fa); the chosen lesson plays in
            # its place, so nothing of lesson One is heard.
            if not self._opened:
                self._opened = True
                name = first_beat
            super().tutorial_beat(name)

    launched = []

    def new_tutorial(first_run=False):
        # The first tutorial takes the asked-for ending; one started later from the
        # chooser's menu takes the ending its own route gives it.
        if not launched:
            launched.append(True)
            first_run = args.ending == 'start'
        st = LessonTutorial(first_run=bool(first_run))
        st.viewDidLoad()
        return st

    SixthSense._new_tutorial = new_tutorial
    print('The tutorial from lesson %d, %s, with the %s ending, voice over %s.  '
          'Your own save is not used.'
          % (args.lesson, lesson_name,
             'Start' if args.ending == 'start' else 'Tutorial button', args.voice))
    return SixthSense.main(['--tutorial'] + (['-v'] if args.verbose else []))


if __name__ == '__main__':
    sys.exit(main())
