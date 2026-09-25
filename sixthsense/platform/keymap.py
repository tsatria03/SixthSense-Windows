"""PORT ADDITION: the keyboard the touch input is mapped to, and the player's changes.

The original has no key bindings at all - every action is a swipe, a tap or a shake
(``aidocks/GAME_STRUCTURE.md`` §7). The port binds those actions to keys, keeps the
bindings in ``%APPDATA%\\SixthSense\\keys.json`` and lets the player rebind them from
the screen F1 opens.

**Bindings can be chords.** An action holds a list of bindings, and each binding is a
*set* of keys that must be held together. That is what makes the default arrow layout
work, which puts the five lanes exactly where the tutorial says they are - the clock
face the recorded instructions describe:

        9 o'clock   Left            lane 1      "if you make your finger 9"
        10:30       Left + Up       lane 2      "...10_30"
        12          Up              lane 3      "...12"
        1:30        Right + Up      lane 4      "...1_30"
        3           Right           lane 5      "...3"
        6           Down            reload      "...6"

The letters A Q W E D S stay bound alongside, so either hand position works. There are
no turn keys: the original never turns you.

``Shift+Tab`` for the previous weapon was already a chord before any of this, and goes
through the same machinery.

Keys are stored by pygame's name for them ("left", "left shift"), not by keycode, so a
saved keymap survives a pygame update.

Resolving a chord
-----------------
``Left`` alone is lane 1 and ``Left+Up`` is lane 2, so a keydown cannot always be
decided on the spot. ``KeyMap.press`` returns an action immediately when the held set
matches a binding that nothing longer extends; otherwise it asks the caller to wait
``CHORD_WINDOW`` seconds and call ``settle``, and a key that completes the longer chord
in the meantime fires at once and cancels the wait. 60 ms is well under anything this
game reacts to - one tick is a second and the shortest weapon cooldown is 0.3 s.

What is held is often more than one binding's worth, because a player rolling from one
attack key to the next has not let go of the first yet. So the match that wins is one
that uses the key just pressed, and the longest of those: pressing D while A is down
attacks lane 5, and pressing Up while Left is down is still the Left+Up chord.
"""
from __future__ import annotations

import json
import logging
import os

from .. import paths

log = logging.getLogger('keymap')

CHORD_WINDOW = 0.06        # seconds to wait before deciding a possibly-chorded key

# action, what the binding screen calls it, default bindings.
# A binding is a tuple of pygame key names; more than one name means a chord.
ACTIONS = (
    ('lane1', "Attack 9 o'clock, hard left", (('a',), ('left',))),
    ('lane2', 'Attack 10:30, half left', (('q',), ('left', 'up'))),
    ('lane3', 'Attack 12, straight ahead', (('w',), ('up',))),
    ('lane4', 'Attack 1:30, half right', (('e',), ('right', 'up'))),
    ('lane5', "Attack 3 o'clock, hard right", (('d',), ('right',))),
    ('reload', "Reload, 6 o'clock", (('s',), ('r',), ('down',))),
    ('next_weapon', 'Next weapon', (('tab',),)),
    ('prev_weapon', 'Previous weapon', (('left shift', 'tab'), ('right shift', 'tab'))),
    ('shake', 'Shake free', (('space',),)),
    ('pause', 'Pause / stop', (('p',),)),
    # Only with --debug (``KeyMap.debug``); otherwise they neither match nor show.
    ('debug_next_section', 'Debug: next section of the corridor', (('f2',),)),
    ('debug_next_level', 'Debug: next level',
     (('left shift', 'f2'), ('right shift', 'f2'))),
    ('debug_spawn', 'Debug: spawn a zombie', (('f5',),)),
    ('debug_spawn_kind', 'Debug: choose what to spawn',
     (('left shift', 'f5'), ('right shift', 'f5'))),
    ('debug_freeze', 'Debug: hold zombies in place', (('f6',),)),
    ('debug_hits', 'Debug: let zombies hit you, without taking a heart', (('f7',),)),
    ('debug_monsters', 'Debug: say where the zombies are', (('f11',),)),
)

ACTION_IDS = [a[0] for a in ACTIONS]
DEBUG_IDS = [a for a in ACTION_IDS if a.startswith('debug_')]
LABELS = {a[0]: a[1] for a in ACTIONS}
DEFAULTS = {a[0]: [tuple(b) for b in a[2]] for a in ACTIONS}

# Not rebindable, on purpose: bind over these and there is no way back into the game
# or into the binding screen without deleting the save.
# Escape goes back from the shop's screens, pauses a stage, leaves the tutorial and
# quits only from the main menu.
#: Page Up and Page Down set the menu music's volume on the menu screens (ui/menu_input.py,
#: a PORT ADDITION of 2026-09-25), which read them outside the keymap.
FIXED = {'f1': 'Key bindings', 'escape': 'Back, pause or quit',
         'page up': 'Menu music louder', 'page down': 'Menu music quieter'}

# pygame's names are terse and some of them read badly; these are for speech.
SPOKEN = {
    'left': 'Left Arrow', 'right': 'Right Arrow', 'up': 'Up Arrow', 'down': 'Down Arrow',
    'space': 'Space', 'tab': 'Tab', 'escape': 'Escape', 'return': 'Enter',
    'left shift': 'Left Shift', 'right shift': 'Right Shift',
    'left ctrl': 'Left Control', 'right ctrl': 'Right Control',
    'left alt': 'Left Alt', 'right alt': 'Right Alt',
    ',': 'Comma', '.': 'Full stop', '/': 'Slash', ';': 'Semicolon', "'": 'Apostrophe',
    '[': 'Left bracket', ']': 'Right bracket', '\\': 'Backslash', '-': 'Minus',
    '=': 'Equals', '`': 'Backtick', 'backspace': 'Backspace', 'delete': 'Delete',
    'home': 'Home', 'end': 'End', 'page up': 'Page Up', 'page down': 'Page Down',
    'insert': 'Insert', 'caps lock': 'Caps Lock', 'enter': 'Enter',
}


def key_text(name):
    """A key name as it should be spoken."""
    if name in SPOKEN:
        return SPOKEN[name]
    if len(name) == 1:
        return name.upper()
    return name.title()


def binding_text(binding):
    """A chord as it should be spoken: 'Left Arrow plus Up Arrow'."""
    return ' plus '.join(key_text(k) for k in binding)


def bindings_text(bindings):
    if not bindings:
        return 'nothing'
    return ', or '.join(binding_text(b) for b in bindings)


class KeyMap:
    _shared = None

    @classmethod
    def shared(cls):
        if cls._shared is None:
            cls._shared = KeyMap()
        return cls._shared

    def __init__(self, path=None):
        self.path = path or os.path.join(paths.user_dir(), 'keys.json')
        self.bindings = {a: [tuple(b) for b in DEFAULTS[a]] for a in ACTION_IDS}
        self.load()
        self._held = set()
        self._newest = None        # the key pressed last, which decides a rollover
        self.debug = False         # --debug: the debug_ actions are live

    @property
    def actions(self):
        """The actions in play: every one with --debug, the debug_ ones left out
        otherwise."""
        if self.debug:
            return ACTION_IDS
        return [a for a in ACTION_IDS if a not in DEBUG_IDS]

    # ---- storage ---------------------------------------------------------
    def load(self):
        """Read the bindings, and write the file when it is missing or lacks an action.

        PORT ADDITION (tsatria03, 2026-09-25): ``keys.json`` is there from the first
        start, holding the default bindings, instead of appearing only once a key is
        rebound.  An action the file does not name yet, one added since it was written,
        gets its default and is written in too.  A file that cannot be read is left
        alone, so a player's bindings are never overwritten by the defaults."""
        saved = {}
        try:
            if os.path.exists(self.path):
                with open(self.path, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                for action in ACTION_IDS:
                    if action in saved:
                        self.bindings[action] = [tuple(b) for b in saved[action] if b]
        except Exception:
            log.exception('could not read %s; using the defaults', self.path)
            return
        if not all(action in saved for action in ACTION_IDS):
            self.save()

    def save(self):
        try:
            tmp = self.path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump({a: [list(b) for b in self.bindings[a]] for a in ACTION_IDS},
                          f, indent=1, sort_keys=True)
            os.replace(tmp, self.path)
        except Exception:
            log.exception('could not write %s', self.path)

    def reset(self):
        self.bindings = {a: [tuple(b) for b in DEFAULTS[a]] for a in ACTION_IDS}
        self.save()

    # ---- editing ---------------------------------------------------------
    def label(self, action):
        return LABELS[action]

    def keys_text(self, action):
        return bindings_text(self.bindings.get(action, []))

    def conflicts(self, binding, ignore=None):
        """Actions already using exactly this chord."""
        b = tuple(sorted(binding))
        return [a for a in self.actions if a != ignore
                and any(tuple(sorted(x)) == b for x in self.bindings[a])]

    def set_binding(self, action, binding, replace=True):
        """Give ``action`` this chord, taking it off whatever else had it."""
        b = tuple(binding)
        key = tuple(sorted(b))
        for other in ACTION_IDS:
            self.bindings[other] = [x for x in self.bindings[other]
                                    if tuple(sorted(x)) != key]
        self.bindings[action] = [b] if replace else self.bindings[action] + [b]
        self.save()

    def clear(self, action):
        self.bindings[action] = []
        self.save()

    # ---- resolving -------------------------------------------------------
    def _matches(self, held):
        """(action, binding) for every binding satisfied by ``held``."""
        out = []
        for action in self.actions:
            for b in self.bindings[action]:
                if set(b) <= held:
                    out.append((action, b))
        return out

    def _extendable(self, held):
        """True when some binding is a strict superset of ``held`` - so holding one
        more key could still mean something else."""
        for action in self.actions:
            for b in self.bindings[action]:
                if held < set(b):
                    return True
        return False

    def _best(self, matches, newest):
        """Which match to take: one that uses the key just pressed, and the longest of
        those, so a chord still beats one of its own keys.

        Without the first half, holding A and pressing D attacked lane 1 again: both
        bindings were satisfied, both were one key long, and the order of ``ACTIONS``
        decided. A player rolling from one attack key to the next hit the same lane twice.
        """
        fresh = [m for m in matches if newest in m[1]] or matches
        return max(fresh, key=lambda m: len(m[1]))

    def press(self, name):
        """A key went down.

        Returns ``(action, pending)``. ``action`` is what to do now, or None.
        ``pending`` is True when the caller should wait ``CHORD_WINDOW`` and then call
        ``settle`` - the key might be the start of a chord.
        """
        self._held.add(name)
        self._newest = name
        held = set(self._held)
        matches = self._matches(held)
        if not matches:
            return None, self._extendable(held)
        action, _binding = self._best(matches, name)
        if self._extendable(held):
            return None, True
        return action, False

    def settle(self):
        """The chord window closed; decide on whatever is still held."""
        held = set(self._held)
        matches = self._matches(held)
        if not matches:
            return None
        action, _b = self._best(matches, self._newest)
        return action

    def release(self, name):
        self._held.discard(name)

    def clear_held(self):
        self._held.clear()
        self._newest = None

    @property
    def held(self):
        return set(self._held)
