"""PORT ADDITION: the key-binding screen, opened with F1 and read aloud.

The game is self-voicing from recorded WAVs, and none of them can say "Left Arrow" or
"Attack 10:30" - so this one screen speaks through ``platform/speech.py`` (NVDA when it
is running, SAPI 5 otherwise). Everything it says, it says on entry and on every move,
because there is nothing on screen a player of this game is expected to read.

    Up / Down       move through the actions
    Enter           bind: hold the key or chord you want, then let go
    A               add a second binding instead of replacing
    Delete          unbind
    R               reset everything to the defaults
    F1 / Escape     back to the game

Binding captures a *chord*: hold Left and Up together and release, and the action gets
``Left + Up``. The keys are recorded when the first one comes back up, so the order you
press them in does not matter.

F1 and Escape are never rebindable (``keymap.FIXED``) - bind over the way out and there
would be no way back in.
"""
from __future__ import annotations

import logging

from ..platform.keymap import (ACTION_IDS, FIXED, KeyMap, binding_text,
                               key_text)
from ..platform.speech import Speech

log = logging.getLogger('keybind')

HELP = ('Key bindings. Up and Down to move, Enter to rebind, A to add a second key, '
        'Delete to unbind, R to reset everything, Escape to go back.')


class KeyBindScreen:
    """Runs modally over the game: while it is open the stage sees no input."""

    def __init__(self, keymap=None, speech=None):
        self.keymap = keymap or KeyMap.shared()
        self.speech = speech or Speech.shared()
        self.index = 0
        self.done = False
        self.capturing = False
        self.capture_add = False
        self.captured = []          # in press order, so speech reads them that way
        self.lines = []             # what a sighted player sees

    # ---- speech ----------------------------------------------------------
    def say(self, text, interrupt=True):
        self.lines.append(text)
        del self.lines[:-8]
        self.speech.speak(text, interrupt)
        log.info('%s', text)

    def open(self):
        self.done = False
        self.index = 0
        self.keymap.clear_held()
        self.say(HELP)
        self.say(self.current_text(), interrupt=False)

    def close(self):
        self.done = True
        self.capturing = False
        self.keymap.clear_held()
        self.say('Back to the game.')

    # ---- the list --------------------------------------------------------
    @property
    def action(self):
        return ACTION_IDS[self.index]

    def current_text(self):
        a = self.action
        return '%s: %s' % (self.keymap.label(a), self.keymap.keys_text(a))

    def move(self, delta):
        self.index = (self.index + delta) % len(ACTION_IDS)
        self.say(self.current_text())

    # ---- binding ---------------------------------------------------------
    def begin_capture(self, add=False):
        self.capturing = True
        self.capture_add = add
        self.captured = []
        self.say('Hold the key or keys for %s, then let go.'
                 % self.keymap.label(self.action))

    def finish_capture(self):
        self.capturing = False
        if not self.captured:
            self.say('Nothing pressed. %s' % self.current_text())
            return
        binding = tuple(self.captured)
        if any(k in FIXED for k in binding):
            taken = ', '.join(key_text(k) for k in binding if k in FIXED)
            self.say('%s cannot be rebound. %s' % (taken, self.current_text()))
            return
        stolen = self.keymap.conflicts(binding, ignore=self.action)
        self.keymap.set_binding(self.action, binding, replace=not self.capture_add)
        said = '%s is now %s.' % (self.keymap.label(self.action), binding_text(binding))
        if stolen:
            said += ' Taken from %s.' % ', '.join(self.keymap.label(a) for a in stolen)
        self.say(said)

    def unbind(self):
        self.keymap.clear(self.action)
        self.say('%s is unbound.' % self.keymap.label(self.action))

    def reset(self):
        self.keymap.reset()
        self.say('Every binding is back to the default. %s' % self.current_text())

    # ---- events ----------------------------------------------------------
    def handle(self, event, pygame):
        """Consume one pygame event. The caller must not pass these to the game."""
        if event.type == pygame.QUIT:
            self.close()
            return
        if event.type == pygame.KEYDOWN:
            name = pygame.key.name(event.key)
            if self.capturing:
                if name not in self.captured:
                    self.captured.append(name)
                return
            if name in ('escape', 'f1'):
                self.close()
            elif name == 'up':
                self.move(-1)
            elif name == 'down':
                self.move(1)
            elif name in ('return', 'enter'):
                self.begin_capture(add=False)
            elif name == 'a':
                self.begin_capture(add=True)
            elif name in ('delete', 'backspace'):
                self.unbind()
            elif name == 'r':
                self.reset()
            elif name == 'home':
                self.index = 0
                self.say(self.current_text())
            elif name == 'end':
                self.index = len(ACTION_IDS) - 1
                self.say(self.current_text())
            else:
                self.say(self.current_text())
        elif event.type == pygame.KEYUP and self.capturing:
            # the chord is whatever was held when the first key came back up
            self.finish_capture()

    # ---- what a sighted player sees -------------------------------------
    def render_lines(self):
        out = ['Key bindings', '']
        for i, a in enumerate(ACTION_IDS):
            out.append('%s %-28s %s' % ('>' if i == self.index else ' ',
                                        self.keymap.label(a), self.keymap.keys_text(a)))
        out += ['']
        for name, what in FIXED.items():
            out.append('  %-28s %s (fixed)' % (what, key_text(name)))
        out += ['', 'Up/Down move   Enter rebind   A add   Delete unbind   R reset',
                'Escape or F1 to go back', '']
        if self.capturing:
            out.append('listening... hold the keys, then let go')
        out += self.lines[-3:]
        return out
