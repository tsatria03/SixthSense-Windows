"""Keyboard in place of the iPhone's touchscreen and accelerometer.

The original has four inputs, all of them on the device:

    UIPanGestureRecognizer          -> -[Stage_1_E MovingShot:]          attack, by angle
    UITapGestureRecognizer, 2 touch -> -[Stage_1_E doubleTapChangeWeapon:]
    UITapGestureRecognizer, 3 touch -> -[Stage_1_E threeTapChangeWeapon:]
    UIAccelerometer                 -> -[MovingAccelerometer accelerometer:didAccelerate:]
                                       (tilt past +-20 degrees turns you 10 degrees)
                                    -> -[Stage_1_E accelerometer:didAccelerate:]
                                       (shaking free of a zombie that has grabbed you)

Windows gets the same four on the keyboard, through ``platform/keymap.py``, which holds
the bindings and resolves chords. The defaults put the five lanes on the arrow keys in
the shape the tutorial describes - it teaches them as clock positions, and the arrows
are a clock face:

        9 o'clock   Left        10:30  Left+Up      12  Up
        1:30  Right+Up          3      Right        6   Down = reload

with A Q W E D S bound alongside for a one-handed grip. Turning is comma and full stop,
because Left and Right are lanes. F1 opens the binding screen; F1 and Escape are the two
keys that cannot be rebound.

The lane keys replace the swipe rather than simulating it, which loses nothing:
``-[Stage_1_E MovingShot:]`` quantises its angle into five bands and a reload sector
before anything else looks at it, so a key hands the stage the band directly.

There is no mouse. Everything is reachable without leaving the home row or the arrow
cluster, which is the point for a game meant to be played with the screen off.
"""
from __future__ import annotations

import logging
import time

from ..platform.keymap import CHORD_WINDOW, KeyMap

log = logging.getLogger('input')

# The bearing at the centre of each lane, from MOVING_TYPE_ANGLE in monster_control.
# These are the clock positions the tutorial names.
LANE_ANGLE = {1: 180.0, 2: 123.0, 3: 90.0, 4: 57.0, 5: 0.0}
LANE_ACTIONS = {'lane1': 1, 'lane2': 2, 'lane3': 3, 'lane4': 4, 'lane5': 5}


class Input:
    """Turns pygame key events into the calls the stage expects."""

    def __init__(self, stage, keymap=None):
        self.stage = stage
        self.keymap = keymap or KeyMap.shared()
        self.quit = False
        self.open_bindings = False        # the frame loop watches this for F1
        self._pending_at = None           # when the chord window closes
        # The keymap is shared, and a key that was down when the last screen went away
        # never had its key-up delivered here.  Left held, it makes the next stage read
        # chords nobody is pressing.
        self.keymap.clear_held()

    # ---- the actions -----------------------------------------------------
    def attack_lane(self, lane):
        """What the pan gesture ends in: ``-[Stage_1_E MovingShot:]`` with the bearing
        of the lane, which is the band the original would have quantised to."""
        if lane in LANE_ANGLE:
            self.stage.MovingShot_(LANE_ANGLE[lane])

    def perform(self, action):
        if action is None:
            return
        st = self.stage
        lane = LANE_ACTIONS.get(action)
        if lane is not None:
            self.attack_lane(lane)
        elif action == 'reload':
            st.GunReloadAction_()
        elif action == 'next_weapon':
            st.doubleTapChangeWeapon_()
        elif action == 'prev_weapon':
            st.threeTapChangeWeapon_()
        elif action == 'turn_left':
            st.turn_left()
        elif action == 'turn_right':
            st.turn_right()
        elif action == 'shake':
            st.shake_step()
        elif action == 'pause':
            st.StopPlayAction_()

    # ---- the pause and result panel ---------------------------------------
    def handle_panel(self, event, pygame):
        """``gameState`` is not 0, so the panel is up and it owns the keyboard.

        ``-[Stage_1_E selectTapPointSoundStart]`` reads whichever row the finger is
        over and ``-[Stage_1_E tapCount]`` runs it on a double tap, so Up and Down
        walk the same rows in the same order and Enter is the double tap - the way
        the main menu was ported.  The lane keys are not attacks while it is up:
        nothing in the original reaches ``MovingShot:`` from the panel either, because
        the pan recogniser is swapped for the tap recogniser at 0x34f96.
        """
        if event.type != pygame.KEYDOWN:
            return
        name = pygame.key.name(event.key)
        st = self.stage
        if name == 'escape':
            self.quit = True
        elif name == 'f1':
            self.open_bindings = True
        elif name == 'up':
            st.pause_move(-1)
        elif name == 'down':
            st.pause_move(1)
        elif name in ('return', 'enter', 'space'):
            if st.selectMenu:
                st.pause_activate()
            else:
                st.pause_move(1)          # nothing chosen yet: start at the top
        else:
            st.blindModeSelectedMenu()

    # ---- events ----------------------------------------------------------
    def handle(self, event, pygame):
        if event.type == pygame.QUIT:
            self.quit = True
            return
        # Alt+Tab away with a key down and its key-up goes to whatever took the focus,
        # so forget what is held rather than leave it stuck.
        if event.type in (getattr(pygame, 'WINDOWFOCUSLOST', -1),
                          getattr(pygame, 'ACTIVEEVENT', -1)):
            self.reset()
            return
        if self.stage.gameState != 0:
            self.reset()
            self.handle_panel(event, pygame)
            return
        if event.type == pygame.KEYDOWN:
            name = pygame.key.name(event.key)
            if name == 'escape':
                self.quit = True
                return
            if name == 'f1':
                self.open_bindings = True
                return
            action, pending = self.keymap.press(name)
            if action is not None:
                self._pending_at = None
                self.perform(action)
            elif pending:
                # might still become a longer chord; decide when the window closes
                self._pending_at = time.monotonic() + CHORD_WINDOW
        elif event.type == pygame.KEYUP:
            name = pygame.key.name(event.key)
            if self._pending_at is not None and name in self.keymap.held:
                # let go before the window closed - take it as it stands
                action = self.keymap.settle()
                self._pending_at = None
                self.perform(action)
            self.keymap.release(name)

    def pump(self):
        """Called once a frame, to close an open chord window."""
        if self.stage.gameState != 0:
            self._pending_at = None
            return
        if self._pending_at is not None and time.monotonic() >= self._pending_at:
            self._pending_at = None
            self.perform(self.keymap.settle())

    def reset(self):
        self._pending_at = None
        self.keymap.clear_held()
