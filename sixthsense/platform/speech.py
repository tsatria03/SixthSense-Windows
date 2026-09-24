"""PORT ADDITION: a synthesiser, for the words the game's own recordings cannot say.

SixthSense speaks entirely through its 269 recorded WAVs, which ``SoundList.plist`` names
by number. That covers everything the original ever needed to say - and nothing the
key-binding screen needs, which is key names ("Left Arrow", "Left Shift"), action names,
and whatever the player has just bound. The only letters or digits in the bundle are
``zero``..``nine``, recorded for the number reader.

So those words go to the player's screen reader, or to a plain voice when none is running.
Before every line, the first of these that can speak says it:

    NVDA         through its own controller client, vendor/nvda/nvdaControllerClient64.dll
    the others   through Prism (the prismatoid package): JAWS, ZDSR, ZoomText, System
                 Access, PC-Talker, Boy PC Reader, Sense Reader, Window-Eyes, and Narrator
    a voice      SAPI 5 through Prism, or Windows' OneCore voices if SAPI will not start,
                 for a player with no screen reader running at all
    nothing      if none of them can speak; the game still works, it just says nothing

NVDA keeps a client of its own because asking it "are you running?" before every line is
cheap and certain, and a player with NVDA never loads Prism at all. Prism is optional: if it
is not installed, or its library will not load, the log says so and NVDA carries on alone.

With voice over on, the game stays self-voicing and this is only for the lines no
recording covers. With it off, the menus speak through here too.
"""
from __future__ import annotations

import ctypes
import logging
import os
import time
from ctypes import wintypes

from .. import paths

log = logging.getLogger('speech')

#: The screen readers Prism speaks to, by its own names for them (``prism.BackendId``), in
#: the order they are tried.  NVDA is first only as a backstop, for when its own client
#: above cannot load.  Narrator is last: Prism reaches it through UI Automation, which says
#: it is ready whether or not Narrator is running, so the game asks Windows instead.
READERS = ('NVDA', 'JAWS', 'ZDSR', 'ZOOM_TEXT', 'SYSTEM_ACCESS', 'PC_TALKER',
           'BOY_PC_READER', 'SENSE_READER', 'WINDOW_EYES', 'UIA')
NARRATOR = 'UIA'
NARRATOR_EXE = 'narrator.exe'
#: The plain voices, for a player with no screen reader running.
VOICES = ('SAPI', 'ONE_CORE')
#: Set to 1 by the tests: nothing is ever spoken or cut off, and neither NVDA's client nor
#: Prism is loaded.  The game itself never sets it.
SILENT_ENV = 'SIXTHSENSE_SILENT'


class _Nvda:
    """The NVDA controller client, ``vendor/nvda/nvdaControllerClient64.dll``."""

    def __init__(self):
        self.dll = None
        if not os.path.exists(paths.NVDA_DLL):
            return
        try:
            self.dll = ctypes.windll.LoadLibrary(str(paths.NVDA_DLL))
            self.dll.nvdaController_testIfRunning.restype = ctypes.c_ulong
            self.dll.nvdaController_speakText.argtypes = [ctypes.c_wchar_p]
            self.dll.nvdaController_speakText.restype = ctypes.c_ulong
            self.dll.nvdaController_cancelSpeech.restype = ctypes.c_ulong
            self.dll.nvdaController_brailleMessage.argtypes = [ctypes.c_wchar_p]
            self.dll.nvdaController_brailleMessage.restype = ctypes.c_ulong
        except (OSError, AttributeError):
            log.info('NVDA controller client not available')
            self.dll = None

    def running(self):
        return bool(self.dll is not None and self.dll.nvdaController_testIfRunning() == 0)

    def speak(self, text, interrupt):
        if not self.running():
            return False
        if interrupt:
            self.dll.nvdaController_cancelSpeech()
        self.dll.nvdaController_speakText(text)
        self.dll.nvdaController_brailleMessage(text)
        return True

    def stop(self):
        if self.running():
            self.dll.nvdaController_cancelSpeech()


class _ProcessEntry(ctypes.Structure):
    """``PROCESSENTRY32W``"""
    _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
                ('th32ProcessID', wintypes.DWORD), ('th32DefaultHeapID', ctypes.c_size_t),
                ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
                ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', ctypes.c_long),
                ('dwFlags', wintypes.DWORD), ('szExeFile', ctypes.c_wchar * 260)]


def process_running(exe):
    """Whether a program with this file name is running, from Windows' own process list.
    A few milliseconds; False wherever the list cannot be read."""
    try:
        k32 = ctypes.WinDLL('kernel32')
        k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        k32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry)]
        k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry)]
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        snap = k32.CreateToolhelp32Snapshot(2, 0)            # TH32CS_SNAPPROCESS
    except (OSError, AttributeError):
        return False
    if not snap or snap == wintypes.HANDLE(-1).value:        # INVALID_HANDLE_VALUE
        return False
    try:
        entry = _ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        exe = exe.lower()
        more = k32.Process32FirstW(snap, ctypes.byref(entry))
        while more:
            if entry.szExeFile.lower() == exe:
                return True
            more = k32.Process32NextW(snap, ctypes.byref(entry))
        return False
    finally:
        k32.CloseHandle(snap)


def _load_prism():
    """Prism's registry and its backend ids, or an exception if it cannot be had."""
    from prism import BackendId, Context
    return Context(), BackendId


class _Prism:
    """Every screen reader but NVDA's own client, and the plain voices, through Prism.

    A screen reader started while the game runs is looked for every few seconds, and one
    that stops or fails is let go at once, so the next line goes to whatever can still
    speak.  ``loader``, ``narrator_running`` and ``clock`` are there for the tests.
    """

    PROBE_EVERY = 5.0       # seconds between looks for a screen reader, while none is in use
    CHECK_EVERY = 1.0       # seconds between asking the one in use whether it still runs
    RETRY_VOICE = 5.0       # seconds before trying the voices again, after they failed

    def __init__(self, loader=_load_prism, narrator_running=None, clock=time.monotonic):
        self.narrator_running = narrator_running or (lambda: process_running(NARRATOR_EXE))
        self.clock = clock
        self.ctx = self.ids = None
        self.readers = []
        self.voices = []
        try:
            self.ctx, self.ids = loader()
            present = {self.ctx.id_of(i) for i in range(self.ctx.backends_count)}
            self.readers = self._ids(READERS, present)
            self.voices = self._ids(VOICES, present)
            log.info('Prism: %d screen readers and %d voices',
                     len(self.readers), len(self.voices))
        except Exception as exc:            # not installed, or its library will not load
            log.info('Prism not available (%s): NVDA only', exc)
            self.ctx = None
        self.reader = None                  # (id, backend) of the screen reader in use
        self.voice = None
        self.next_probe = 0.0
        self.checked = 0.0
        self.next_voice_try = 0.0

    def _ids(self, names, present):
        """The ids of these names that this Prism has, in the order given."""
        found = []
        for name in names:
            bid = getattr(self.ids, name, None)
            if bid is not None and bid in present:
                found.append(bid)
        return found

    def _is_narrator(self, bid):
        return bid == getattr(self.ids, NARRATOR, None)

    def _running(self, bid, backend):
        if self._is_narrator(bid):
            return self.narrator_running()
        try:
            return bool(backend.features.is_supported_at_runtime)
        except Exception:
            return False

    def _let_go(self, why):
        log.info('speech: %s let go (%s)', self.reader[1].name, why)
        self.reader = None
        self.next_probe = 0.0               # look for another at once

    def current_reader(self):
        """The screen reader to speak through, or None."""
        if self.ctx is None:
            return None
        now = self.clock()
        if self.reader is not None and now - self.checked >= self.CHECK_EVERY:
            self.checked = now
            if not self._running(*self.reader):
                self._let_go('no longer running')
        if self.reader is None and now >= self.next_probe:
            self.next_probe = now + self.PROBE_EVERY
            for bid in self.readers:
                if self._is_narrator(bid) and not self.narrator_running():
                    continue                # not even made while Narrator is off
                try:
                    backend = self.ctx.create(bid)
                except Exception:
                    continue
                if self._running(bid, backend):
                    self.reader, self.checked = (bid, backend), now
                    break
        return None if self.reader is None else self.reader[1]

    def current_voice(self):
        """The plain voice to speak through, or None."""
        if self.ctx is None:
            return None
        if self.voice is None and self.clock() >= self.next_voice_try:
            self.next_voice_try = self.clock() + self.RETRY_VOICE
            for bid in self.voices:
                try:
                    self.voice = self.ctx.create(bid)
                    break
                except Exception:
                    continue
        return self.voice

    @staticmethod
    def _say(backend, text, interrupt):
        if backend.features.supports_output:
            backend.output(text, interrupt)         # speech, and braille where there is a display
        else:
            backend.speak(text, interrupt)

    def speak_reader(self, text, interrupt):
        """Say it through the screen reader in use; the backend's name, or None."""
        backend = self.current_reader()
        if backend is None:
            return None
        try:
            self._say(backend, text, interrupt)
            return backend.name
        except Exception as exc:
            self._let_go(exc)
            return None

    def speak_voice(self, text, interrupt):
        """Say it through the plain voice; the voice's name, or None."""
        backend = self.current_voice()
        if backend is None:
            return None
        try:
            self._say(backend, text, interrupt)
            return backend.name
        except Exception as exc:
            log.info('speech: %s voice failed (%s)', backend.name, exc)
            self.voice = None
            return None

    def stop(self):
        if self.reader is not None:
            try:
                self.reader[1].stop()
            except Exception:
                pass
        if self.voice is not None:
            try:
                self.voice.stop()
            except Exception:
                pass
            # A plain voice (SAPI or OneCore) can keep playing what it had
            # already queued even after stop(), unlike a real screen reader's
            # own cancel.  Freeing it and building a fresh one next time tears
            # down whatever audio is still playing underneath it.
            self.voice = None
            self.next_voice_try = 0.0        # so the next line gets it at once


class Speech:
    _shared = None

    @classmethod
    def shared(cls):
        if cls._shared is None:
            cls._shared = Speech()
        return cls._shared

    def __init__(self, nvda=None, prism=None):
        # SIXTHSENSE_SILENT: the tests' way of never reaching the player's screen reader.
        # Stand-ins passed in are still used, so the tests of this class keep working.
        self.silent = (nvda is None and prism is None
                       and os.environ.get(SILENT_ENV) == '1')
        self.nvda = nvda if nvda is not None or self.silent else _Nvda()
        self._prism = prism
        self._heard_from = ''               # what spoke the last line, for the log

    @property
    def prism(self):
        # built on first use, so a player with NVDA never loads Prism
        if self._prism is None:
            self._prism = _Prism()
        return self._prism

    def _heard(self, who):
        """Log the speaker only when it changes, rather than on every line."""
        if who != self._heard_from:
            self._heard_from = who
            log.info('speech: %s', who or 'nothing can speak, so the game is silent')
        return who is not None

    def speak(self, text, interrupt=True):
        if not text or self.silent:
            return False
        text = str(text)
        if self.nvda.speak(text, interrupt):
            return self._heard('NVDA')
        who = self.prism.speak_reader(text, interrupt)
        if who is None:
            who = self.prism.speak_voice(text, interrupt)
        return self._heard(who)

    def stop(self):
        if self.silent:
            return
        self.nvda.stop()
        if self._prism is not None:
            self._prism.stop()

    @property
    def which(self):
        """What would speak the next line: 'NVDA', a Prism backend's name, or 'none'."""
        if self.silent:
            return 'none'
        if self.nvda.running():
            return 'NVDA'
        backend = self.prism.current_reader() or self.prism.current_voice()
        return backend.name if backend is not None else 'none'

    @property
    def available(self):
        return self.which != 'none'
