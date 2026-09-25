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
     7          modechange_flag   331  "voice over on button" / 332 "...off button"
     8          gamecenter_flag   367  "game center button10"

**DIVERGENCE:** rows 5 and 8, ranking and Game Center, are left out.  Both opened
online services (the publisher's ranking server and Apple's Game Center) that the
Windows port does not have, so the menu goes 4, 6, 7 and wraps.  The rest keep the
original's numbers.

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
from .blind_screen import whole

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
SOUND_COIN_COUNT = 334
#: How long after "number of coins" the count is read (0x9bec..0x9c0c): 1.6 s.
READ_COIN_COUNT_DELAY = 1.6
SOUND_NO_COIN = 358
SOUND_RANKING_NOTICE = 364

# selectMenu, flag, sound, what it does
ROWS = (
    (1, 'coin_flag', SOUND_COIN_COUNT, 'coin'),
    (2, 'main_title_flag', SOUND_TITLE, 'title'),
    (3, 'start_game_flag', SOUND_GAME_START, 'start'),
    (4, 'tutorial_flag', SOUND_TUTORIAL, 'tutorial'),
    (6, 'store_flag', SOUND_STORE, 'store'),
    (7, 'modechange_flag', SOUND_VOICEOVER_ON_BUTTON, 'modechange'),
)
#: PORT ADDITION: what the screen reader says for each row with voice over off.
#: The coin row and the voice over row are made in ``row_text``.
ROW_TEXT = {
    'title': 'Sixth Sense: The Zombies',
    'start': 'Game start, Button',
    'tutorial': 'Tutorial, Button',
    'store': 'Store, Button',
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
        self.app.mode = self.app.saved_mode()
        self.app.BGMusicStart()
        self.selectMenu = 2
        self.blindModeSelectedMenu()
        self._coinCatchUp()
        self._coinClockSafetyNet()

    def _coinClockSafetyNet(self):
        """PORT ADDITION: with fewer than COIN_MAX coins and no clock counting down,
        start one.  The original only starts the clock when a coin is spent
        (coinTiemrControlStart, 0xbe01), so a save that reached 0 coins without a
        clock - edited by hand, or put back from an older backup after damage - never
        got a coin again, and the coin row read "0 minutes 0 seconds".  In play there is
        always a clock whenever the coins are under the cap, so this changes nothing
        there."""
        if self.app.Coin < COIN_MAX and self.coinTimer is None:
            self.coinTiemrControlStart()

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
            # 0xa2b8: the row names what choosing it does, 332 "voice over off button"
            # while voice over is on and 331 "voice over on button" while it is off.
            return SOUND_VOICEOVER_OFF_BUTTON if self.app.mode else SOUND_VOICEOVER_ON_BUTTON
        return sound

    def row_text(self, n=None):
        """What the screen reader says for a row, with voice over off."""
        action = self._row(n)[3]
        if action == 'coin':
            text = 'Number of coins, %s.' % whole(self.app.Coin)
            if self.app.Coin >= COIN_MAX:
                return text + ' The coin is full.'
            left = self.app._coin_timer_remaining()
            return text + ' The coin is charged after %d minutes %d seconds.' % (
                left // 60, left % 60)
        if action == 'modechange':
            return 'Voice over off, Button' if self.app.mode else 'Voice over on, Button'
        return ROW_TEXT[action]

    # -[MainController blindModeSelectedMenu] 0x90d0 - highlight the row and say it
    def blindModeSelectedMenu(self):
        num, flag, _s, action = self._row()
        for f in self._flags:
            self._flags[f] = False
        self.StopElseSpeak()
        self._flags[flag] = True
        if self.app.screen_reader:
            self._say(self.row_text())
            log.info('menu: %s', action)
            return
        self.app.playSound_Gain_Pos_z_reprats_(
            self.row_sound(), 0.2, (0.0, 0.0), 0, False)
        if action == 'coin':
            # -[MainController readNumberOfCoin] 0x97ed reads the count after the name,
            # 1.6 s later (0x9bec..0x9c0c: the double's high word is 0x3ff99999)
            RunLoop.main().perform(self, 'readNumberOfCoin', None, READ_COIN_COUNT_DELAY)
        log.info('menu: %s', action)

    # -[MainController readNumberOfCoin] 0x97ed
    def readNumberOfCoin(self, *_):
        # type 3 (0x9812): after the digits, say "coins are full" or say "after"
        # and read the time to the next one.
        self.app.TTSNumber_type_(self.app.Coin, 3)

    def move(self, delta):
        """Up and Down walk the rows in order and wrap, skipping the numbers the port
        leaves out."""
        nums = [r[0] for r in ROWS]
        if self.selectMenu in nums:
            i = (nums.index(self.selectMenu) + delta) % len(nums)
        else:
            i = 0 if delta > 0 else len(nums) - 1
        self.selectMenu = nums[i]
        self.blindModeSelectedMenu()

    def jump(self, last=False):
        """PORT ADDITION: Home and End in the screen reader mode, the first row or the
        last, as a screen reader's own lists go."""
        nums = [r[0] for r in ROWS]
        self.selectMenu = nums[-1] if last else nums[0]
        self.blindModeSelectedMenu()

    # ============================================================ activating
    # -[MainController tapCount] 0x9350 - a double tap runs the selected row
    def activate(self):
        action = self._row()[3]
        if action in ('coin', 'title'):
            self.blindModeSelectedMenu()
            return
        # tapCount sends StartGame: (0x9420) and Store: (0x9438), the two wrappers that
        # click first; Tutorial and the mode change are sent their actions directly.
        if action == 'start':
            self.StartGame_(None)
        elif action == 'tutorial':
            self.TutorialAction_(None)
        elif action == 'modechange':
            self.ModeChageAction_(None)
        elif action == 'store':
            self.Store_(None)

    # -[MainController StartGame:] 0xac50
    def StartGame_(self, *_):
        """Stop what is speaking, click (0xad32, 10 at 0.2) and go on to
        ``StartGameAction:`` - coin or no coin, so an empty purse clicks before its
        "no coin".  The headphone and VoiceOver checks in front (0xac60..0xacfa) belong
        to the phone and are left out."""
        self.StopElseSpeak()
        self.app.playSound_Gain_Pos_z_reprats_(SOUND_UI_SELECT, 0.2, (0.0, 0.0), 0, False)
        self.StartGameAction_(None)

    # -[MainController Store:] 0xb67c
    def Store_(self, *_):
        """Click (0xb6a8, 10 at 0.2), then ``StoreAction:``."""
        self.app.playSound_Gain_Pos_z_reprats_(SOUND_UI_SELECT, 0.2, (0.0, 0.0), 0, False)
        self.StoreAction_(None)

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
        if self.app.Coin >= 1 or self.app.debug:     # 0xb324; --debug needs no coin
            if not self.app.debug:                   # ...and spends none
                self.app.Coin -= 1
                d.setObject_forKey_(str(self.app.Coin), 'COIN')
                d.synchronize()
                self.coinTiemrControlStart()
            # No click here: StartGameAction: plays only 358 (0xb5a0); the click is
            # StartGame:'s, before it.
            # 0xb3f8 always pushes Stage_1_E, whose MapInitInBundle (0x2e08e-0x2e0dc)
            # runs the tutorial inline while TUTORIAL is 0, so the first game's coin
            # pays for the tutorial too.  The port runs that tutorial in
            # Stage_Tutorial, which counts down into the game when it ends.
            if d.intForKey_('TUTORIAL') == 0:
                self.next_screen = ('tutorial', True)
            else:
                self.next_screen = 'stage'
        else:
            # 0xb472-0xb5a0: the original puts the sentence on maskLabel1 and fades it
            # over 7 s, and plays 358 - nothing about it is spoken. The port used to
            # add its own spoken line on top of the recording; that was never here.
            # With voice over off, the screen reader reads the sentence instead.
            # DIVERGENCE: the original's sentence (0xb5ad6) goes on to "You can buy
            # coin at the store or share with friends at the ranking page", and the
            # port has neither, so only what the recording says is kept.
            self.message = 'No coin.'
            if self.app.screen_reader:
                self._say(self.message)
            else:
                self.app.playNoCoin_(0.2)

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
        # 0xb982 / 0xbb5e: the recording of the mode you switched to, 22 "voice over
        # off" or 21 "voice over on" - the last recording before the screen reader
        # takes over, or the first after it hands back.
        self.app.playSound_Gain_Pos_z_reprats_(
            SOUND_VOICEOVER_OFF if self.app.screen_reader else SOUND_VOICEOVER_ON,
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
