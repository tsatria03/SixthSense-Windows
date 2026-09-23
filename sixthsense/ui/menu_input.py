"""The menu's keyboard, in place of touch exploration and the double tap.

``-[MainController selectTapPointSoundStart]`` reads whichever row your finger is over
and ``-[MainController tapCount]`` runs it on a double tap. A keyboard has no finger,
so Up and Down walk the same rows in the same order, reading each one with the same
WAV, and Enter is the double tap.
"""
from __future__ import annotations

import logging

log = logging.getLogger('menu.input')


class MenuInput:
    def __init__(self, menu):
        self.menu = menu
        self.quit = False
        self.open_bindings = False

    def handle(self, event, pygame):
        if event.type == pygame.QUIT:
            self.quit = True
            return
        if event.type != pygame.KEYDOWN:
            return
        name = pygame.key.name(event.key)
        if name == 'escape':
            self.quit = True
        elif name == 'f1':
            self.open_bindings = True
        elif name == 'up':
            self.menu.move(-1)
        elif name == 'down':
            self.menu.move(1)
        elif name in ('return', 'enter', 'space'):
            self.menu.activate()
        elif name in ('home', 'end') and self.menu.app.screen_reader:
            # the screen reader mode: the first row or the last, as its lists go
            self.menu.jump(last=(name == 'end'))
        elif name in ('left', 'right') and self.menu.app.screen_reader:
            # ...and Left and Right as VoiceOver's flicks: right is the next row
            self.menu.move(1 if name == 'right' else -1)
        elif name == 'home':
            self.menu.selectMenu = 1
            self.menu.blindModeSelectedMenu()
        else:
            # anything else just repeats where you are, as the original does when a
            # finger lands back on the same row
            self.menu.blindModeSelectedMenu()
