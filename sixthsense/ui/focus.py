"""Losing the window's focus is pressing P.

The original does this when the app goes to the background: ``applicationDidEnterBackground:``
posts ``InterruptON`` (0x4d90), and the stage and the tutorial answer it with
``interruptStop``, which calls ``StopPlayAction:`` (0x2c6ce, 0x84962) - the stop button,
the same call P makes here.  So everything P does, this does: the pause panel in a stage,
every time, and in the tutorial whatever P does there.
Nothing else observes the notification, so the menus ignore it.  Coming back does not
resume anything; the panel waits for Continue, as it does after P.

What ``InterruptOff`` does on the way back, rebuilding the audio device
(``-[Stage_1_E audioRestart]`` 0x2c5bc), is ``AL.check_device`` here, which the frame
loop runs once a second and as soon as the window has focus again.
"""
from __future__ import annotations

import logging

log = logging.getLogger('focus')


def focus_lost(event, pygame):
    return event.type == getattr(pygame, 'WINDOWFOCUSLOST', None)


def interrupt_stop(screen):
    """``-[Stage_1_E interruptStop]`` / ``-[Stage_Tutorial interruptStop]``: the stop
    button, for whichever stage is up.  Returns True if the screen has one."""
    stop = getattr(screen, 'StopPlayAction_', None)
    if stop is None:
        return False
    log.info('window lost focus: stop, as P')
    stop(None)
    return True
