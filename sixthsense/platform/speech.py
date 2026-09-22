"""PORT ADDITION: a synthesiser, for the one screen the game's own voice cannot read.

SixthSense speaks entirely through its 269 recorded WAVs, which ``SoundList.plist`` names
by number. That
covers everything the original ever needed to say - and nothing the key-binding screen
needs, which is key names ("Left Arrow", "Left Shift"), action names, and whatever the
player has just bound. The only letters or digits in the bundle are ``zero``..``nine``,
recorded for the number reader.

So the binding screen gets a real synthesiser:

    NVDA      through its controller client, when NVDA is running
    SAPI 5    otherwise, through comtypes - works with no screen reader at all
    silent    if neither is available; the screen still works, it just says nothing

Nothing else in the port uses this. The game itself stays self-voicing.
"""
from __future__ import annotations

import ctypes
import logging
import os

from .. import paths

log = logging.getLogger('speech')


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


class _Sapi:
    """SAPI 5, for players without a screen reader running."""

    SVSF_ASYNC = 1
    SVSF_PURGE = 2

    def __init__(self):
        self.voice = None
        try:
            import comtypes.client
            self.voice = comtypes.client.CreateObject('SAPI.SpVoice')
        except Exception:
            log.info('SAPI not available (pip install comtypes)')
            self.voice = None

    def speak(self, text, interrupt):
        if self.voice is None:
            return False
        flags = self.SVSF_ASYNC | (self.SVSF_PURGE if interrupt else 0)
        self.voice.Speak(text, flags)
        return True

    def stop(self):
        if self.voice is not None:
            self.voice.Speak('', self.SVSF_ASYNC | self.SVSF_PURGE)


class Speech:
    _shared = None

    @classmethod
    def shared(cls):
        if cls._shared is None:
            cls._shared = Speech()
        return cls._shared

    def __init__(self):
        self.nvda = _Nvda()
        self._sapi = None

    @property
    def sapi(self):
        # built on first use, so a player with NVDA never pays for the COM object
        if self._sapi is None:
            self._sapi = _Sapi()
        return self._sapi

    def speak(self, text, interrupt=True):
        if not text:
            return False
        if self.nvda.speak(text, interrupt):
            return True
        return self.sapi.speak(text, interrupt)

    def stop(self):
        self.nvda.stop()
        if self._sapi is not None:
            self._sapi.stop()

    @property
    def available(self):
        return self.nvda.running() or self.sapi.voice is not None

    @property
    def which(self):
        if self.nvda.running():
            return 'NVDA'
        if self.sapi.voice is not None:
            return 'SAPI 5'
        return 'none'
