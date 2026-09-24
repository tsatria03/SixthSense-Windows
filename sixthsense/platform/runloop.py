"""``NSTimer`` and ``-performSelector:withObject:afterDelay:`` on one cooperative run loop.

Almost all of the game's timing is deferred main-thread work: ``MonsterControl`` runs its
walk cycle on ``NSTimer scheduledTimerWithTimeInterval:...repeats:YES``, and ``Stage_1_E``
chains nearly every consequence of an action through ``performSelector:withObject:
afterDelay:`` with the *length of the sound that is playing* as the delay (see
``-[Stage_1_E MovingShot:]`` scheduling ``stopShot:`` after ``[weapon ShotTime]``).

Timers and performs are kept apart, but ``RunLoop.pump`` runs everything due as one queue
in fire-time order, whichever kind each is, the earlier scheduled first when two fall due
together - as one ``NSRunLoop`` would.  A perform is identified by ``(target, selector)``
exactly as ``+cancelPreviousPerformRequestsWithTarget:selector:object:`` identifies it, so
cancelling works the same way.

Delays are wall-clock, like the original's, read from ``clock`` (``time.perf_counter``,
not ``time.monotonic``, whose 15.6 ms steps on Windows would round short delays); the loop
never advances a timer faster than real time, so a slow frame makes timers late rather
than bunched - ``NSTimer`` behaves the same way.

Whether a callback is handed its timer or object is decided from its signature before it
is called, never by calling it again when it raises ``TypeError``: an error inside a
callback is logged once, and the callback never runs twice.
"""
from __future__ import annotations

import heapq
import inspect
import itertools
import logging
import time

log = logging.getLogger('runloop')

#: The loop's clock, in seconds.  Anything comparing against a fire date uses this.
clock = time.perf_counter


def _takes(fn, *args) -> bool:
    """Whether ``fn`` can be called with ``args``, judged from its signature without
    calling it.  A callable Python cannot see into is taken to accept them."""
    try:
        inspect.signature(fn).bind(*args)
    except TypeError:
        return False
    except ValueError:
        return True
    return True


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
        self.fireDate = clock() + self.interval
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
        # NSTimer hands the timer to its selector; a callback that takes nothing gets nothing
        if _takes(fn, self):
            fn(self)
        else:
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
        p = _Perform(clock() + max(0.0, float(delay)), target, selector, obj,
                     next(self._seq))
        heapq.heappush(self._performs, (p.due, p.seq, p))
        self._by_key.setdefault((id(target), selector), []).append(p)
        return p

    def cancelPerform(self, target, selector=None):
        """``+cancelPreviousPerformRequestsWithTarget:selector:object:``; with no selector,
        the ``+cancelPreviousPerformRequestsWithTarget:`` form."""
        if selector is None:
            tid = id(target)
            for key in [k for k in self._by_key if k[0] == tid]:
                for p in self._by_key.pop(key):
                    p.cancelled = True
            return
        for p in self._by_key.pop((id(target), selector), ()):
            p.cancelled = True

    # ---- driving ---------------------------------------------------------
    def pump(self, now=None):
        """Run everything due, earliest first, timers and performs alike.  Called once
        per frame by the app's main loop."""
        if self._held_at is not None:
            return
        now = clock() if now is None else now

        while True:
            self._drop_cancelled()
            perform = self._performs[0][2] if self._performs else None
            timer = min((t for t in self._timers if t._valid and t.fireDate <= now),
                        key=lambda t: (t.fireDate, t._seq), default=None)
            if perform is not None and perform.due > now:
                perform = None
            if perform is None and timer is None:
                break
            if timer is None or (perform is not None
                                 and (perform.due, perform.seq) <= (timer.fireDate, timer._seq)):
                heapq.heappop(self._performs)
                self._run_perform(perform)
            else:
                self._run_timer(timer, now)
        self._timers = [t for t in self._timers if t._valid]

    def _drop_cancelled(self):
        while self._performs and self._performs[0][2].cancelled:
            heapq.heappop(self._performs)

    def _forget(self, p):
        """Take a perform out of the cancel index, and its key with it once empty."""
        key = (id(p.target), p.selector)
        lst = self._by_key.get(key)
        if lst:
            try:
                lst.remove(p)
            except ValueError:
                pass
            if not lst:
                del self._by_key[key]

    def _run_perform(self, p):
        self._forget(p)
        fn = getattr(p.target, p.selector, None)
        if fn is None:
            log.error('perform selector missing: %s.%s', type(p.target).__name__, p.selector)
            return
        try:
            if p.obj is not None:
                fn(p.obj)
            elif _takes(fn):
                fn()
            else:
                fn(None)
        except Exception:
            log.exception('perform %s.%s', type(p.target).__name__, p.selector)

    def _run_timer(self, t, now):
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

    def hold(self):
        """PORT ADDITION: stop the clock, for the F1 binding screen over a stage.
        Nothing fires until ``resume``, which moves every due date on by the time
        that was held, so the stage picks up where it left off."""
        if self._held_at is None:
            self._held_at = clock()

    def resume(self):
        if self._held_at is None:
            return
        gap = clock() - self._held_at
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
