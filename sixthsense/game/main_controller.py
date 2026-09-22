"""``MainController`` - the main menu. Ported from 0x81f0..0xccb0.

The menu is self-voiced from the game's own WAVs, and it is built for a finger rather
than a cursor: ``-[MainController selectTapPointSoundStart]`` (0x9825) maps the *Y
coordinate* of a touch to a row, sets ``selectMenu``, raises that row's flag and plays
its name; a double tap then activates whatever ``selectMenu`` is on
(``-[MainController tapCount]`` 0x9350). The whole blind path is gated on
``[AppDelegate mode]`` - ``-[MainController Menu:]`` returns immediately when it is 0,
which is the sighted button layout.

The eight rows, in screen order, with the flag and sound each one owns:

    selectMenu  flag              sound
     1          coin_flag         334  "number of coins"
     2          main_title_flag    16  "Six Sense _ The Zombies"
     3          start_game_flag    17  "Game Start Button"
     4          tutorial_flag      23  "Tutorial Button"
     5          ranking_flag      333  "ranking button"
     6          store_flag         18  "Store Button"
     7          modechange_flag   332  "voice over off button" / 331 "...on button"
     8          gamecenter_flag   367  "game center button10"

``exit_flag`` and ``Exit:`` exist and ``exitButton`` is in the nib, but no row in
``selectTapPointSoundStart`` claims it and no code plays sound 20 - so Exit is not
reachable from the blind menu at all. Reproduced: the port has no Exit row either, and
Escape quits.

**A game costs a coin.** ``-[MainController StartGameAction:]`` (0xb2ed):

    if (Coin >= 1) { Coin--; save COIN; [self coinTiemrControlStart]; push the stage; }
    else           { play 358 "no coin"; show "No coin. You can buy coin at the store
                     or share with friends at the ranking page." }

and the coins come back on a timer, but only while none is already counting down.
``coinTiemrControlStart`` (0xbe01) returns at once if ``coinTimer`` already exists;
otherwise it writes ``COIN_TIMER`` (now, "yyyy-MM-dd HH:mm:ss"), sets
``COIN_TIMER_START`` to "1", starts the clock, and stops if ``Coin >= 5``.
``coinUpTimer`` (0xc0b1) counts that down and, at zero, grants one coin, clears
``COIN_TIMER_START`` and restarts the clock while ``Coin <= 4``. The interval is
1800 s, not the "10:00" the original's label text shows (0xc1ee). So: one coin
per thirty minutes, five at most, one per game. ``viewDidLoad`` also grants
coins for time spent away, at the same rate and cap (0x8aca-0x8b14).
"""
from __future__ import annotations

import logging
import time

from ..platform.defaults import UserDefaults
from ..platform.runloop import RunLoop
from .app_delegate import AppDelegate, COIN_INTERVAL, COIN_MAX

log = logging.getLogger('menu')

SOUND_UI_SELECT = 10
SOUND_TITLE = 16
SOUND_GAME_START = 17
SOUND_STORE = 18
SOUND_TUTORIAL = 23
SOUND_VOICEOVER_ON = 21
SOUND_VOICEOVER_OFF = 22
SOUND_VOICEOVER_ON_BUTTON = 331
SOUND_VOICEOVER_OFF_BUTTON = 332
SOUND_RANKING = 333
SOUND_COIN_COUNT = 334
SOUND_NO_COIN = 358
SOUND_RANKING_NOTICE = 364
SOUND_GAMECENTER = 367

# selectMenu, flag, sound, what it does
ROWS = (
    (1, 'coin_flag', SOUND_COIN_COUNT, 'coin'),
    (2, 'main_title_flag', SOUND_TITLE, 'title'),
    (3, 'start_game_flag', SOUND_GAME_START, 'start'),
    (4, 'tutorial_flag', SOUND_TUTORIAL, 'tutorial'),
    (5, 'ranking_flag', SOUND_RANKING, 'ranking'),
    (6, 'store_flag', SOUND_STORE, 'store'),
    (7, 'modechange_flag', SOUND_VOICEOVER_OFF_BUTTON, 'modechange'),
    (8, 'gamecenter_flag', SOUND_GAMECENTER, 'gamecenter'),
)
FIRST_ROW = ROWS[0][0]
LAST_ROW = ROWS[-1][0]

# Rows the port cannot honour: all three want the publisher's server, which is gone.
SERVER_BACKED = {
    'ranking': 'The ranking page needs the game’s server, which is gone.',
    'gamecenter': 'Game Center is not available here.',
}


class MainController:
    """The menu. ``next_screen`` is what the frame loop should put up next."""

    def __init__(self, speech=None):
        self.app = AppDelegate.shared()
        self.selectMenu = 2                 # 0x85c1 viewDidLoad starts on the title
        self.tapCount = 0
        self.coinTimer = None
        self.coinTimeCounter = 0
        self.min = 0
        self.sec = 0
        self.next_screen = None             # 'stage' | 'tutorial' | None
        self.quit = False
        self.speech = speech
        self.message = ''                   # maskLabel1
        self._flags = {f: False for _n, f, _s, _a in ROWS}

    # ================================================================ entry
    # -[MainController viewDidLoad] 0x85c1
    def viewDidLoad(self):
        d = UserDefaults.standardUserDefaults()
        self.app.Coin = d.intForKey_('COIN')
        # -[MainController checkVoiceOverApple] 0xc735 reads the saved mode
        self.app.mode = d.intForKey_('EYEMODE') if d.objectForKey_('EYEMODE') is not None \
            else d.intForKey_('DEFAULTEYEMODE')
        self.app.BGMusicStart()
        self.selectMenu = 2
        self.blindModeSelectedMenu()
        self._coinCatchUp()

    # -[MainController viewDidLoad] 0x8946-0x8d12 - grant coins for time spent
    # away, at the recharge rate, capped at COIN_MAX (0x8aca-0x8b14).
    def _coinCatchUp(self):
        if self.app.Coin > COIN_MAX - 1:                  # 0x8952: cmp r0, 4
            return
        d = UserDefaults.standardUserDefaults()
        if d.stringForKey_('COIN_TIMER_START') != '1':    # 0x89a8: nothing running
            return
        started = d.stringForKey_('COIN_TIMER')
        try:
            t0 = time.mktime(time.strptime(started, '%Y-%m-%d %H:%M:%S'))
        except (ValueError, TypeError):
            return
        elapsed = int(time.time() - t0)
        if elapsed <= COIN_INTERVAL:                       # 0x8aca
            self.coinTiemrControlStartBackGroundRestart()
            return
        self.app.Coin += elapsed // int(COIN_INTERVAL)     # 0x8ad6-0x8afe
        if self.app.Coin > COIN_MAX:                        # 0x8b0a: cmp r0, 6
            self.app.Coin = COIN_MAX
            d.setObject_forKey_('0', 'COIN_TIMER_START')
        else:
            # keep the leftover progress toward the next coin, rather than
            # resetting the clock to now (0x8bd8-0x8cf6)
            leftover = elapsed % int(COIN_INTERVAL)
            d.setObject_forKey_(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() - leftover)),
                'COIN_TIMER')
        d.setObject_forKey_(str(self.app.Coin), 'COIN')
        d.synchronize()
        self.coinTiemrControlStartBackGroundRestart()

    # -[MainController StopElseSpeak] 0x96e9 - silence every menu voice
    def StopElseSpeak(self):
        for _n, _f, sound, _a in ROWS:
            self.app.stopSoundBufNumber_(sound)
        for sound in (SOUND_VOICEOVER_ON_BUTTON, SOUND_VOICEOVER_OFF_BUTTON,
                      SOUND_NO_COIN, SOUND_RANKING_NOTICE):
            self.app.stopSoundBufNumber_(sound)
        self.app.readStop()
        if self.speech is not None:
            self.speech.stop()
        # 0x97e2: also cancel a pending readNumberOfCoin, or it fires over
        # whatever row the player has since moved to.
        RunLoop.main().cancelPerform(self, 'readNumberOfCoin')

    # =============================================================== moving
    def _row(self, n=None):
        n = self.selectMenu if n is None else n
        for row in ROWS:
            if row[0] == n:
                return row
        return ROWS[0]

    def row_sound(self, n=None):
        num, _flag, sound, action = self._row(n)
        if action == 'modechange':
            # 0xa270 / 0xa48c: which one depends on the mode it would switch to
            return SOUND_VOICEOVER_OFF_BUTTON if self.app.mode else SOUND_VOICEOVER_ON_BUTTON
        return sound

    # -[MainController blindModeSelectedMenu] 0x90d0 - highlight the row and say it
    def blindModeSelectedMenu(self):
        num, flag, _s, action = self._row()
        for f in self._flags:
            self._flags[f] = False
        self.StopElseSpeak()
        self._flags[flag] = True
        self.app.playSound_Gain_Pos_z_reprats_(
            self.row_sound(), 0.2, (0.0, 0.0), 0, False)
        if action == 'coin':
            # -[MainController readNumberOfCoin] 0x97ed reads the count after the name
            RunLoop.main().perform(self, 'readNumberOfCoin', None, 1.5)
        log.info('menu: %s', action)

    # -[MainController readNumberOfCoin] 0x97ed
    def readNumberOfCoin(self, *_):
        # type 3 (0x9812): after the digits, say "coins are full" or say "after"
        # and read the time to the next one.
        self.app.TTSNumber_type_(self.app.Coin, 3)

    def move(self, delta):
        n = self.selectMenu + delta
        if n < FIRST_ROW:
            n = LAST_ROW
        elif n > LAST_ROW:
            n = FIRST_ROW
        self.selectMenu = n
        self.blindModeSelectedMenu()

    # ============================================================ activating
    # -[MainController tapCount] 0x9350 - a double tap runs the selected row
    def activate(self):
        action = self._row()[3]
        if action in ('coin', 'title'):
            self.blindModeSelectedMenu()
            return
        if action == 'start':
            self.StartGameAction_(None)
        elif action == 'tutorial':
            self.TutorialAction_(None)
        elif action == 'modechange':
            self.ModeChageAction_(None)
        elif action == 'store':
            self.StoreAction_(None)
        elif action in SERVER_BACKED:
            self.StopElseSpeak()
            self.app.playSound_Gain_Pos_z_reprats_(
                SOUND_UI_SELECT, 0.2, (0.0, 0.0), 0, False)
            self._say(SERVER_BACKED[action])
            log.info('%s is not available: server-backed', action)

    def _say(self, text):
        """The one place the menu needs words the bundle has no recording for."""
        if self.speech is None:
            from ..platform.speech import Speech
            self.speech = Speech.shared()
        self.speech.speak(text)

    # -[MainController StoreAction:] 0xb6d0
    def StoreAction_(self, *_):
        """Push ``mainStoreController``.  Only two of its rows were purchases; the
        weapon shop spends the gold a run pays, which is a local key.

        0xb6d0 plays nothing of its own - the shop's first row reads itself as soon
        as it comes up."""
        self.StopElseSpeak()
        self.next_screen = 'store'

    # -[MainController StartGameAction:] 0xb2ed
    def StartGameAction_(self, *_):
        self.StopElseSpeak()
        d = UserDefaults.standardUserDefaults()
        if d.intForKey_('TUTORIAL') == 0:
            # The original runs the tutorial inline inside Stage_1_E's own
            # MapInitInBundle (0x2e08e-0x2e0dc) without spending a coin. The port
            # keeps the tutorial as its own screen, so send the player there
            # instead, still without a coin.
            self.app.playSound_Gain_Pos_z_reprats_(
                SOUND_UI_SELECT, 0.2, (0.0, 0.0), 0, False)
            self.next_screen = 'tutorial'
            return
        if self.app.Coin >= 1:                       # 0xb324
            self.app.Coin -= 1
            d.setObject_forKey_(str(self.app.Coin), 'COIN')
            d.synchronize()
            self.coinTiemrControlStart()
            self.app.playSound_Gain_Pos_z_reprats_(
                SOUND_UI_SELECT, 0.2, (0.0, 0.0), 0, False)
            self.next_screen = 'stage'
        else:
            # 0xb472-0xb5a0: the original puts the sentence on maskLabel1 and fades it
            # over 7 s, and plays 358 - nothing about it is spoken. The port used to
            # add its own spoken line on top of the recording; that was never here.
            self.app.playSound_Gain_Pos_z_reprats_(
                SOUND_NO_COIN, 0.2, (0.0, 0.0), 0, False)
            self.message = ('No coin. You can buy coin at the store or share with '
                            'friends at the ranking page.')

    # -[MainController TutorialAction:] 0xad5d
    def TutorialAction_(self, *_):
        self.StopElseSpeak()
        self.app.playSound_Gain_Pos_z_reprats_(
            SOUND_UI_SELECT, 0.2, (0.0, 0.0), 0, False)
        self.next_screen = 'tutorial'

    # -[MainController ModeChageAction:] 0xb831
    def ModeChageAction_(self, *_):
        d = UserDefaults.standardUserDefaults()
        self.app.mode = 0 if self.app.mode else 1
        d.setObject_forKey_(str(self.app.mode), 'EYEMODE')
        d.synchronize()
        self.StopElseSpeak()
        self.app.playSound_Gain_Pos_z_reprats_(
            SOUND_VOICEOVER_ON if self.app.mode else SOUND_VOICEOVER_OFF,
            0.2, (0.0, 0.0), 0, False)
        log.info('voice over %s', 'on' if self.app.mode else 'off')

    # ================================================================ coins
    # -[MainController coinTiemrControlStart] 0xbe01
    def coinTiemrControlStart(self):
        d = UserDefaults.standardUserDefaults()
        if self.app.Coin >= COIN_MAX:                # 0xbff6
            self.coinTiemrControlEnd()
            return
        if self.coinTimer is not None:               # 0xbe3a: a timer is already
            return                                    # running - do not restart it
        d.setObject_forKey_('1', 'COIN_TIMER_START')
        d.setObject_forKey_(time.strftime('%Y-%m-%d %H:%M:%S'), 'COIN_TIMER')
        d.synchronize()
        self.min, self.sec = 30, 0
        self.coinTimer = RunLoop.main().scheduledTimer(
            1.0, self, 'coinUpTimer', None, True)

    # -[MainController coinTiemrControlEnd] 0xc069
    def coinTiemrControlEnd(self):
        if self.coinTimer is not None and self.coinTimer.isValid():
            self.coinTimer.invalidate()
        self.coinTimer = None

    # -[MainController coinTimerControlStartBackGroundRestart] 0xbcfd
    def coinTiemrControlStartBackGroundRestart(self):
        d = UserDefaults.standardUserDefaults()
        if d.stringForKey_('COIN_TIMER_START') == '1' and self.app.Coin < COIN_MAX:
            if self.coinTimer is None or not self.coinTimer.isValid():
                self.coinTimer = RunLoop.main().scheduledTimer(
                    1.0, self, 'coinUpTimer', None, True)

    # -[MainController coinUpTimer] 0xc0b1
    def coinUpTimer(self, timer=None):
        d = UserDefaults.standardUserDefaults()
        started = d.stringForKey_('COIN_TIMER')
        if not started:
            self.coinTiemrControlEnd()
            return
        try:
            t0 = time.mktime(time.strptime(started, '%Y-%m-%d %H:%M:%S'))
        except ValueError:
            self.coinTiemrControlEnd()
            return
        left = COIN_INTERVAL - (time.time() - t0)
        if left > 0:
            self.min = int(left) // 60
            self.sec = int(left) % 60
            return
        # the clock ran out: one coin, and go again while there is room
        self.app.Coin += 1
        d.setObject_forKey_(str(self.app.Coin), 'COIN')
        d.setObject_forKey_('0', 'COIN_TIMER_START')
        d.synchronize()
        self.coinTiemrControlEnd()
        if self.app.Coin <= COIN_MAX - 1:            # 0xc3ea: cmp r0, 4
            self.coinTiemrControlStart()

    @property
    def coin_clock(self):
        return '%02d:%02d' % (self.min, self.sec)

    # ================================================================= misc
    def teardown(self):
        self.coinTiemrControlEnd()
        RunLoop.main().cancelPerform(self)
        self.StopElseSpeak()
