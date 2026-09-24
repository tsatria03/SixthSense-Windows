"""The run loop: ``platform/runloop.py``, NSTimer and performSelector:afterDelay:.

Each test drives a loop of its own with ``pump(now=...)``, so nothing waits on the real
clock and nothing of the game is loaded.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import _scratch_save                                             # noqa: E402,F401  never the real save

from sixthsense.platform import runloop                         # noqa: E402
from sixthsense.platform.runloop import RunLoop                 # noqa: E402


class _Target:
    def __init__(self):
        self.calls = []

    def bare(self):
        self.calls.append('bare')

    def takes(self, arg):
        self.calls.append(('takes', arg))

    def optional(self, arg=None):
        self.calls.append(('optional', arg))

    def breaks(self, *_):
        self.calls.append('breaks')
        raise TypeError('a mistake inside the callback')


def test_a_callback_that_raises_type_error_runs_once():
    """Its TypeError was taken for 'called with the wrong arguments' and it ran again."""
    loop, t = RunLoop(), _Target()
    loop.perform(t, 'breaks', None, 0.0)
    loop.scheduledTimer(0.0, t, 'breaks')
    loop.pump(now=runloop.clock() + 1.0)
    assert t.calls == ['breaks', 'breaks'], t.calls      # once each, not twice each


def test_each_callback_gets_what_it_can_take():
    loop, t = RunLoop(), _Target()
    loop.perform(t, 'bare', None, 0.0)
    loop.perform(t, 'takes', None, 0.0)              # no object: handed None
    loop.perform(t, 'takes', 'shot', 0.0)
    loop.perform(t, 'optional', None, 0.0)           # no object, and it can do without
    timer = loop.scheduledTimer(0.0, t, 'takes')     # a timer is handed itself
    loop.scheduledTimer(0.0, t, 'bare')
    loop.pump(now=runloop.clock() + 1.0)
    assert t.calls == ['bare', ('takes', None), ('takes', 'shot'), ('optional', None),
                       ('takes', timer), 'bare'], t.calls


def test_everything_due_runs_in_time_order_timers_and_performs_alike():
    """A timer due at 10 ms ran after a perform due at 12 ms: performs always went first."""
    loop, order = RunLoop(), []

    class T:
        def early(self, *_):
            order.append('timer at 10 ms')

        def late(self):
            order.append('perform at 12 ms')

        def first(self):
            order.append('perform at 5 ms')

    t = T()
    loop.perform(t, 'late', None, 0.012)
    loop.scheduledTimer(0.010, t, 'early')
    loop.perform(t, 'first', None, 0.005)
    loop.pump(now=runloop.clock() + 1.0)
    assert order == ['perform at 5 ms', 'timer at 10 ms', 'perform at 12 ms'], order


def test_the_same_fire_time_keeps_the_order_they_were_scheduled_in():
    loop, order = RunLoop(), []

    class T:
        def a(self, *_):
            order.append('a')

        def b(self, *_):
            order.append('b')

    t = T()
    loop.scheduledTimer(0.0, t, 'a')
    loop.perform(t, 'b', None, 0.0)
    now = runloop.clock() + 1.0
    for timer in loop._timers:
        timer.fireDate = now - 0.5
    loop._performs = [(now - 0.5, seq, p) for _d, seq, p in loop._performs]
    for _d, _s, p in loop._performs:
        p.due = now - 0.5
    loop.pump(now=now)
    assert order == ['a', 'b'], order


def test_a_repeating_timer_fires_once_a_pump_and_skips_what_it_missed():
    loop, t = RunLoop(), _Target()
    timer = loop.scheduledTimer(0.1, t, 'bare', repeats=True)
    now = runloop.clock() + 5.0                       # fifty intervals late
    loop.pump(now=now)
    assert t.calls == ['bare']
    assert abs(timer.fireDate - (now + 0.1)) < 1e-9
    assert timer.isValid() and timer in loop._timers


def test_the_clock_is_fine_grained():
    """time.monotonic moves in 15.6 ms steps on Windows; delays of a few ms were rounded."""
    assert runloop.clock is __import__('time').perf_counter
    a = runloop.clock()
    b = runloop.clock()
    while b == a:
        b = runloop.clock()
    assert b - a < 0.001, 'the clock steps by %.4f s' % (b - a)


def test_cancelling_leaves_no_empty_entries_behind():
    loop, t = RunLoop(), _Target()
    loop.perform(t, 'bare', None, 0.0)
    loop.perform(t, 'takes', 1, 5.0)
    loop.pump(now=runloop.clock() + 1.0)              # 'bare' ran
    assert list(loop._by_key) == [(id(t), 'takes')], loop._by_key
    loop.cancelPerform(t, 'takes')
    assert not loop._by_key
    loop.perform(t, 'bare', None, 5.0)
    loop.perform(t, 'takes', 2, 5.0)
    loop.cancelPerform(t)                             # every selector of the target
    assert not loop._by_key
    loop.pump(now=runloop.clock() + 10.0)
    assert t.calls == ['bare'], t.calls


def test_holding_stops_the_clock_and_resuming_moves_everything_on():
    loop, t = RunLoop(), _Target()
    p = loop.perform(t, 'bare', None, 0.0)
    loop.hold()
    loop.pump(now=runloop.clock() + 1.0)
    assert t.calls == [], 'something ran while the loop was held'
    due = p.due
    loop.resume()
    assert p.due >= due
    loop.pump(now=runloop.clock() + 1.0)
    assert t.calls == ['bare']


if __name__ == '__main__':
    fns = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    bad = 0
    for fn in fns:
        try:
            fn()
            print('ok    %s' % fn.__name__)
        except AssertionError as e:
            bad += 1
            print('FAIL  %s: %s' % (fn.__name__, e))
        except Exception as e:
            bad += 1
            print('ERROR %s: %r' % (fn.__name__, e))
    print('%d/%d passed' % (len(fns) - bad, len(fns)))
    sys.exit(1 if bad else 0)
