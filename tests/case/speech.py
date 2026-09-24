"""Who speaks the words no recording covers: ``platform/speech.py``.

NVDA first, through its own client; then the other screen readers through Prism, with
Narrator only while narrator.exe runs; then a plain voice through Prism.  Every piece here
is a stand-in - a fake NVDA, a fake Prism registry, a fake clock - so these tests never load
NVDA's client or Prism and never make a sound.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import _scratch_save                                             # noqa: E402,F401  never the real save

from sixthsense.platform.speech import Speech, _Prism                # noqa: E402


class _Nvda:
    def __init__(self, running=False):
        self.is_running = running
        self.said = []
        self.stopped = 0

    def running(self):
        return self.is_running

    def speak(self, text, interrupt):
        if not self.is_running:
            return False
        self.said.append(text)
        return True

    def stop(self):
        self.stopped += 1


class _Features:
    def __init__(self, backend):
        self._backend = backend

    @property
    def is_supported_at_runtime(self):
        return self._backend.is_running

    @property
    def supports_output(self):
        return self._backend.braille


class _Backend:
    """One Prism backend: a screen reader or a voice."""

    def __init__(self, name, running=True, braille=True, fails=False):
        self.name = name
        self.is_running = running
        self.braille = braille
        self.fails = fails
        self.spoken = []            # (how, text, interrupt)
        self.stopped = 0

    @property
    def features(self):
        return _Features(self)

    def _say(self, how, text, interrupt):
        if self.fails:
            raise RuntimeError('%s failed' % self.name)
        self.spoken.append((how, text, interrupt))

    def speak(self, text, interrupt=False):
        self._say('speak', text, interrupt)

    def output(self, text, interrupt=False):
        self._say('output', text, interrupt)

    def stop(self):
        self.stopped += 1


class _Ids:
    """Stands in for ``prism.BackendId``: the names are the ids."""
    NVDA, JAWS, ZDSR, ZOOM_TEXT, SYSTEM_ACCESS = 'NVDA', 'JAWS', 'ZDSR', 'ZOOM_TEXT', 'SYSTEM_ACCESS'
    PC_TALKER, BOY_PC_READER, SENSE_READER = 'PC_TALKER', 'BOY_PC_READER', 'SENSE_READER'
    WINDOW_EYES, UIA, SAPI, ONE_CORE = 'WINDOW_EYES', 'UIA', 'SAPI', 'ONE_CORE'


class _Context:
    """Stands in for ``prism.Context``, holding the backends by id."""

    def __init__(self, backends, broken=()):
        self.backends = backends          # id -> _Backend
        self.broken = set(broken)         # ids whose create() raises
        self.created = []

    @property
    def backends_count(self):
        return len(self.backends) + len(self.broken)

    def id_of(self, index):
        return (list(self.backends) + sorted(self.broken))[index]

    def create(self, bid):
        self.created.append(bid)
        if bid in self.broken:
            raise ValueError('Invalid or unsupported backend')
        return self.backends[bid]


class _Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def _speech(backends, nvda=False, narrator=False, broken=()):
    ctx = _Context(backends, broken)
    clock = _Clock()
    prism = _Prism(loader=lambda: (ctx, _Ids), narrator_running=lambda: narrator,
                   clock=clock)
    return Speech(nvda=_Nvda(nvda), prism=prism), ctx, clock


def test_nvda_speaks_first_and_prism_is_never_loaded():
    nvda = _Nvda(running=True)
    s = Speech(nvda=nvda)
    assert s.speak('Key bindings.') is True
    assert nvda.said == ['Key bindings.']
    assert s._prism is None, 'Prism was loaded for an NVDA player'


def test_jaws_speaks_when_nvda_is_not_running():
    jaws = _Backend('JAWS')
    s, _ctx, _clock = _speech({'JAWS': jaws, 'SAPI': _Backend('SAPI')})
    assert s.speak('Back to the game.') is True
    assert jaws.spoken == [('output', 'Back to the game.', True)]
    assert s.which == 'JAWS'


def test_the_first_running_screen_reader_in_order_wins():
    jaws = _Backend('JAWS', running=False)
    zoomtext = _Backend('ZoomText')
    pctalker = _Backend('PC-Talker')
    s, _ctx, _clock = _speech({'JAWS': jaws, 'PC_TALKER': pctalker, 'ZOOM_TEXT': zoomtext})
    s.speak('hello')
    assert zoomtext.spoken and not pctalker.spoken and not jaws.spoken


def test_narrator_is_used_only_while_narrator_is_running():
    uia = _Backend('UIA')              # says it is ready either way, as Prism's does
    sapi = _Backend('SAPI')
    s, ctx, _clock = _speech({'UIA': uia, 'SAPI': sapi}, narrator=False)
    s.speak('one')
    assert not uia.spoken, 'a line went to Narrator while it was off'
    assert sapi.spoken
    assert 'UIA' not in ctx.created, 'the Narrator backend was made while Narrator was off'

    uia2 = _Backend('UIA')
    s2, _ctx2, _clock2 = _speech({'UIA': uia2, 'SAPI': _Backend('SAPI')}, narrator=True)
    s2.speak('two')
    assert uia2.spoken == [('output', 'two', True)]


def test_a_voice_speaks_when_no_screen_reader_runs():
    sapi = _Backend('SAPI', braille=False)
    s, _ctx, _clock = _speech({'JAWS': _Backend('JAWS', running=False), 'SAPI': sapi})
    assert s.speak('Nothing pressed.') is True
    assert sapi.spoken == [('speak', 'Nothing pressed.', True)], 'no braille call on a voice'
    assert s.which == 'SAPI'


def test_onecore_steps_in_when_sapi_will_not_start():
    onecore = _Backend('OneCore')
    s, _ctx, _clock = _speech({'ONE_CORE': onecore}, broken=('SAPI',))
    assert s.speak('hello') is True
    assert onecore.spoken


def test_no_prism_means_nvda_alone_and_no_crash():
    def missing():
        raise ImportError('No module named prism')
    s = Speech(nvda=_Nvda(running=False), prism=_Prism(loader=missing))
    assert s.speak('hello') is False
    assert s.which == 'none' and s.available is False
    s.stop()                           # nothing to stop, and nothing breaks


def test_nothing_speaks_when_nothing_can():
    s, _ctx, _clock = _speech({'JAWS': _Backend('JAWS', running=False)})
    assert s.speak('hello') is False


def test_a_screen_reader_that_stops_is_let_go():
    jaws = _Backend('JAWS')
    sapi = _Backend('SAPI')
    s, _ctx, clock = _speech({'JAWS': jaws, 'SAPI': sapi})
    s.speak('one')
    assert jaws.spoken
    jaws.is_running = False
    clock.now += _Prism.CHECK_EVERY + 0.1
    s.speak('two')
    assert [t for _h, t, _i in sapi.spoken] == ['two'], 'the line did not move to the voice'


def test_a_screen_reader_started_later_is_found():
    jaws = _Backend('JAWS', running=False)
    sapi = _Backend('SAPI')
    s, _ctx, clock = _speech({'JAWS': jaws, 'SAPI': sapi})
    s.speak('one')
    assert sapi.spoken and not jaws.spoken
    jaws.is_running = True
    s.speak('two')
    assert not jaws.spoken, 'it looked again sooner than every few seconds'
    clock.now += _Prism.PROBE_EVERY + 0.1
    s.speak('three')
    assert [t for _h, t, _i in jaws.spoken] == ['three']


def test_a_screen_reader_that_fails_hands_the_line_to_the_voice():
    jaws = _Backend('JAWS', fails=True)
    sapi = _Backend('SAPI')
    s, _ctx, _clock = _speech({'JAWS': jaws, 'SAPI': sapi})
    assert s.speak('hello') is True
    assert [t for _h, t, _i in sapi.spoken] == ['hello']


def test_stop_reaches_whatever_is_speaking():
    jaws = _Backend('JAWS')
    s, _ctx, _clock = _speech({'JAWS': jaws})
    s.speak('hello')
    s.stop()
    assert jaws.stopped == 1
    assert s.nvda.stopped == 1


def test_stopping_a_voice_discards_it_so_stuck_audio_is_torn_down():
    """A plain voice (SAPI, OneCore) has no cancel as reliable as a real screen
    reader's, and can keep playing what it already queued even after stop().
    Freeing it so the next line gets a fresh backend tears down whatever
    playback is still stuck underneath the old one."""
    sapi = _Backend('SAPI', braille=False)
    s, ctx, _clock = _speech({'SAPI': sapi})
    s.speak('one')
    s.stop()
    assert sapi.stopped == 1
    sapi2 = _Backend('SAPI', braille=False)
    ctx.backends['SAPI'] = sapi2
    s.speak('two')
    assert sapi2.spoken == [('speak', 'two', True)], 'a fresh backend was not built'
    assert sapi.spoken == [('speak', 'one', True)], 'the old backend was reused'


def test_an_empty_line_says_nothing():
    jaws = _Backend('JAWS')
    s, _ctx, _clock = _speech({'JAWS': jaws})
    assert s.speak('') is False
    assert not jaws.spoken


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
