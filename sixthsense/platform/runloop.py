"""``NSTimer`` and ``-performSelector:withObject:afterDelay:`` on one cooperative run loop.

Almost all of the game's timing is deferred main-thread work: ``MonsterControl`` runs its
walk cycle on ``NSTimer scheduledTimerWithTimeInterval:...repeats:YES``, and ``Stage_1_E``
chains nearly every consequence of an action through ``performSelector:withObject:
afterDelay:`` with the *length of the sound that is playing* as the delay (see
``-[Stage_1_E MovingShot:]`` scheduling ``stopShot:`` after ``[weapon ShotTime]``).

Both land in the same queue here, ordered by fire time, and ``RunLoop.pump`` drains
everything due.  A perform is identified by ``(target, selector)`` exactly as
``+cancelPreviousPerformRequestsWithTarget:selector:object:`` identifies it, so cancelling
works the same way.

Delays are wall-clock, like the original's; the loop never advances a timer faster than
real time, so a slow frame makes timers late rather than bunched - ``NSTimer`` behaves the
same way.
"""
from __future__ import annotations

import heapq
import itertools
import logging
import time

log = logging.getLogger('runloop')


class Timer:
    """``NSTimer``."""

    __slots__ = ('interval', 'target', 'selector', 'userInfo', 'repeats',
                 'fireDate', '_valid', '_loop', '_seq')

    def __init__(self, loop, interval, target, selector, userInfo, repeats, seq):
        self.interval = float(interval)
        self.target = target
        self.selector = selector
        self.userInfo = userInfo
        self.repeats = bool(repeats)
        self.fireDate = time.monotonic() + self.interval
        self._valid = True
        self._loop = loop
        self._seq = seq

    def isValid(self):
        return self._valid

    def invalidate(self):
        """``-[NSTimer invalidate]``"""
        self._valid = False

    def fire(self):
        fn = getattr(self.target, self.selector, None)
        if fn is None:
            log.error('timer selector missing: %s.%s', type(self.target).__name__, self.selector)
            self._valid = False
            return
        try:
            fn(self)
        except TypeError:
            fn()


class _Perform:
    __slots__ = ('due', 'target', 'selector', 'obj', 'seq', 'cancelled')

    def __init__(self, due, target, selector, obj, seq):
        self.due = due
        self.target = target
        self.selector = selector
        self.obj = obj
        self.seq = seq
        self.cancelled = False


class RunLoop:
    _instance = None

    @classmethod
    def main(cls):
        if cls._instance is None:
            cls._instance = RunLoop()
        return cls._instance

    def __init__(self):
        self._timers = []                 # list[Timer]
        self._performs = []               # heap of (due, seq, _Perform)
        self._by_key = {}                 # (id(target), selector) -> list[_Perform]
        self._seq = itertools.count()
        self._held_at = None              # when hold() stopped the clock

    # ---- NSTimer ---------------------------------------------------------
    def scheduledTimer(self, interval, target, selector, userInfo=None, repeats=False):
        """``+[NSTimer scheduledTimerWithTimeInterval:target:selector:userInfo:repeats:]``"""
        t = Timer(self, interval, target, selector, userInfo, repeats, next(self._seq))
        self._timers.append(t)
        return t

    # ---- performSelector:withObject:afterDelay: --------------------------
    def perform(self, target, selector, obj=None, delay=0.0):
        p = _Perform(time.monotonic() + max(0.0, float(delay)), target, selector, obj,
                     next(self._seq))
        heapq.heappush(self._performs, (p.due, p.seq, p))
        self._by_key.setdefault((id(target), selector), []).append(p)
        return p

    def cancelPerform(self, target, selector=None):
        """``+cancelPreviousPerformRequestsWithTarget:selector:object:``; with no selector,
        the ``+cancelPreviousPerformRequestsWithTarget:`` form."""
        if selector is None:
            tid = id(target)
            for (t, _sel), lst in list(self._by_key.items()):
                if t == tid:
                    for p in lst:
                        p.cancelled = True
                    lst.clear()
            return
        for p in self._by_key.pop((id(target), selector), ()):
            p.cancelled = True

    # ---- driving ---------------------------------------------------------
    def pump(self, now=None):
        """Run everything due.  Called once per frame by the app's main loop."""
        if self._held_at is not None:
            return
        now = time.monotonic() if now is None else now

        while self._performs and self._performs[0][0] <= now:
            _due, _seq, p = heapq.heappop(self._performs)
            lst = self._by_key.get((id(p.target), p.selector))
            if lst:
                try:
                    lst.remove(p)
                except ValueError:
                    pass
            if p.cancelled:
                continue
            fn = getattr(p.target, p.selector, None)
            if fn is None:
                log.error('perform selector missing: %s.%s',
                          type(p.target).__name__, p.selector)
                continue
            try:
                if p.obj is None:
                    try:
                        fn()
                    except TypeError:
                        fn(None)
                else:
                    fn(p.obj)
            except Exception:
                log.exception('perform %s.%s', type(p.target).__name__, p.selector)

        if self._timers:
            alive = []
            for t in self._timers:
                if not t._valid:
                    continue
                if t.fireDate <= now:
                    try:
                        t.fire()
                    except Exception:
                        log.exception('timer %s.%s', type(t.target).__name__, t.selector)
                    if t.repeats and t._valid:
                        # NSTimer schedules the next fire from the previous fire date and
                        # skips missed ones rather than catching up.
                        t.fireDate += t.interval
                        if t.fireDate <= now:
                            t.fireDate = now + t.interval
                    else:
                        t._valid = False
                if t._valid:
                    alive.append(t)
            self._timers = alive

    def hold(self):
        """PORT ADDITION: stop the clock, for the F1 binding screen over a stage.
        Nothing fires until ``resume``, which moves every due date on by the time
        that was held, so the stage picks up where it left off."""
        if self._held_at is None:
            self._held_at = time.monotonic()

    def resume(self):
        if self._held_at is None:
            return
        gap = time.monotonic() - self._held_at
        self._held_at = None
        for t in self._timers:
            t.fireDate += gap
        for _due, _seq, p in self._performs:
            p.due += gap
        self._performs = [(p.due, seq, p) for _due, seq, p in self._performs]
        heapq.heapify(self._performs)

    @property
    def held(self):
        return self._held_at is not None

    def reset(self):
        self._held_at = None
        self._timers.clear()
        self._performs.clear()
        self._by_key.clear()


def main_loop() -> RunLoop:
    return RunLoop.main()
