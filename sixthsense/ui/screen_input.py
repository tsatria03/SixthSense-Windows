"""The keyboard for the shop and inventory screens.

Same story as ``menu_input.py``: the original reads whichever row your finger is over
(``selectTapPointSoundStart``) and runs it on a double tap (``tapCount``), so Up and
Down walk the rows in the same order, reading each with the same WAV, and Enter is the
double tap.  Escape is the Back row, which every one of these screens has.
"""
from __future__ import annotations

import logging

log = logging.getLogger('screen.input')


class ScreenInput:
    def __init__(self, screen):
        self.screen = screen
        self.quit = False
        self.open_bindings = False

    def handle(self, event, pygame):
        if event.type == pygame.QUIT:
            self.quit = True
            return
        if event.type != pygame.KEYDOWN:
            return
        name = pygame.key.name(event.key)
        s = self.screen
        if name == 'escape':
            s.goBackAction_()
        elif name == 'f1':
            self.open_bindings = True
        elif name == 'up':
            s.move(-1)
        elif name == 'down':
            s.move(1)
        elif name in ('return', 'enter', 'space'):
            if s.selectMenu:
                s.activate()
            else:
                s.move(1)
        elif name in ('home', 'end') and s.screen_reader:
            # the screen reader mode: the first row or the last, as its lists go
            s.jump(last=(name == 'end'))
        elif name in ('left', 'right') and s.screen_reader:
            # ...and Left and Right as VoiceOver's flicks: right is the next row
            s.move(1 if name == 'right' else -1)
