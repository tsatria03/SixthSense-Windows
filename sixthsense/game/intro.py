"""The opening screen: the splash, the warning and the story.

    -[startIntroPage ...]   0x16f68..0x18b20

Before it, ``-[AppDelegate application:didFinishLaunchingWithOptions:]`` puts up the
publisher's logo and plays its sound, *bitbee_1* (340), and 3.5 s later
``realStartIntro`` makes this the root view controller (0x4af0).  The port has no launch
of its own to put the logo in, so this screen plays it first (``viewDidLoad``).  Then it
shows ``0_splash2.png`` for two seconds (0x1745c stores 0x4000000000000000 as the delay),
then reads the player's saved settings and plays *Welcome to* - the warning about
headphones, noisy rooms and who should not play.  A double tap anywhere skips to the
menu.

``intro2storyPage`` (0x2b288..0x2c4d0) is the same screen with the story on it, and
**nothing in the binary ever creates one** - the story lives here, in ``shakeDevice``.
See ``docs/PORTING_STATUS.md``.
"""
from __future__ import annotations

import logging
import time

from ..platform import volume
from ..platform.defaults import UserDefaults
from ..platform.runloop import RunLoop
from .blind_screen import BlindScreen

log = logging.getLogger('intro')

SOUND_BGM_START_END = 11
SOUND_WELCOME = 14              # 0x17b32
SOUND_STORY = 15                # 0x171bc
SOUND_DOUBLE_TAP = 266          # 0x1844e

#: PORT ADDITION: not in the original at all - it only ever plays 234 from
#: MainController's StartGameAction:, gated on a headphone check Windows cannot
#: make. Saying it here instead, once, after the welcome message has had time to
#: finish, keeps the reminder without it colliding with the menu's own title read
#: - and a player who skips the intro never hears it, same as skipping cuts off
#: the welcome message itself.
SOUND_EARPHONE = 234

#: The publisher's logo sound, bitbee_1 (4.0 s), which the original plays at 0.2 the
#: moment it launches: -[AppDelegate application:didFinishLaunchingWithOptions:]
#: 0x44f0/0x4502, with no condition, as the logo comes up.
SOUND_LOGO = 340

#: PORT ADDITION: a moment of quiet before the logo sound, so it does not start the
#: instant the game opens (the dev, 2026-09-23: "500 to 1000ms").
LOGO_DELAY = 1.0

#: How long the logo is up before this screen is built: it fades in over 2.5 s
#: (0x459a: vmov.f64 d16, #2.5), then startIntro fades it out over 1.0 s (0x49da),
#: and only then does realStartIntro create startIntroPage (0x4af0).
LOGO_SECONDS = 2.5 + 1.0

#: 0x1745c: `mov.w r3, #0x40000000` - the high half of 2.0.
SPLASH_SECONDS = 2.0

#: PORT ADDITION: measured - 'Welcome to' (14) runs about 28.16 s.
WELCOME_SECONDS = 28.2


class StartIntroPage(BlindScreen):
    """-[startIntroPage selectTapPointSoundStart] 0x18244, tapCount 0x18728.

    Two rows, which is as many as a screen with nothing to choose needs: the message
    itself, and the line that tells you how to skip it.
    """

    ROWS = (1, 2)
    ROW_SOUND = {1: SOUND_WELCOME,          # 0x184ae, main_label_flag
                 2: SOUND_DOUBLE_TAP}       # 0x1844e, double_tap_flag
    STOP_SOUNDS = (SOUND_WELCOME,)          # 0x18618 - StopElseSpeak stops only 14
    ROW_TEXT = {2: 'You can skip by pressing Enter.'}

    def row_text(self, row):
        if row == 1:
            return WELCOME_TEXT
        return BlindScreen.row_text(self, row)

    def __init__(self, speech=None):
        BlindScreen.__init__(self, speech=speech)
        self.logo = False
        self.splash = True
        self.text = ''

    def viewDidLoad(self):
        """The game's launch: the publisher's logo and its sound first, as
        ``application:didFinishLaunchingWithOptions:`` does before this screen exists,
        and the screen itself ``LOGO_SECONDS`` later.  The port has no launch of its
        own to put the logo in, so this screen carries it, after ``LOGO_DELAY`` of
        quiet."""
        self.logo = True
        RunLoop.main().perform(self, 'play_logo', None, LOGO_DELAY)

    def play_logo(self, *_):
        self.app.playSound_Gain_Pos_z_reprats_(
            SOUND_LOGO, 0.2, (0.0, 0.0), 0, False)            # 0x4502
        RunLoop.main().perform(self, 'realStartIntro', None, LOGO_SECONDS)

    def skip_logo(self):
        """PORT ADDITION: Enter during the logo, or the quiet before it, goes straight
        to this screen and its welcome.  Escape still skips everything to the menu."""
        loop = RunLoop.main()
        loop.cancelPerform(self, 'play_logo')
        loop.cancelPerform(self, 'realStartIntro')
        self.app.stopSoundBufNumber_(SOUND_LOGO)
        self.realStartIntro()

    # -[AppDelegate realStartIntro] 0x4aa4, then -[startIntroPage viewDidLoad] 0x17234
    def realStartIntro(self, *_):
        self.logo = False
        self.splash = True                                    # 0_splash2.png
        RunLoop.main().perform(self, 'startIntro1', None, SPLASH_SECONDS)
        self._expire_week()
        # 0x174a6..0x175b6 loads TOKEN, EMAIL, NAME and FACEBOOK_ID and logs in to
        # the publisher's server.  There is no server; the keys are left alone.

    def _expire_week(self):
        """0x1763c: if the stored WEEKTIME has passed, the week's best score goes
        back to zero and the marker is dropped."""
        d = UserDefaults.standardUserDefaults()
        week = d.stringForKey_('WEEKTIME')
        if not week:
            return
        try:
            due = time.mktime(time.strptime(week, '%Y%m%d%H%M%S'))
        except ValueError:
            log.debug('WEEKTIME is not a date: %r', week)
            return
        if time.time() >= due:                                # 0x17754, seconds <= 0
            d.setObject_forKey_('0', 'TOPSCOREWEEK')          # 0x177ae
            d.removeObjectForKey_('WEEKTIME')                 # 0x177d0
            d.synchronize()

    # -[startIntroPage startIntro1] 0x177f4
    def startIntro1(self, *_):
        """The splash comes down, the saved game is read, and the warning plays."""
        self.splash = False                                   # 0x1781c
        d = UserDefaults.standardUserDefaults()
        self.app.mode = self.app.saved_mode()                 # 0x17890
        self.app.haveGold = d.intForKey_('GOLD')              # 0x178e4
        self.app.stage = d.intForKey_('STAGE')                # 0x17918
        self.text = WELCOME_TEXT
        self.select(1)                                        # 0x17ada, 0x17b32
        if not self.screen_reader:
            # Only behind this first reading: the welcome text already says to use
            # earphones, so a reread or the screen reader mode gets no reminder.
            RunLoop.main().perform(self, 'sound_earphone', None, WELCOME_SECONDS)

    def move(self, step):
        """Nothing to move between while the logo is up: on the phone there was no
        screen to touch yet."""
        if self.logo:
            return None
        return BlindScreen.move(self, step)

    def jump(self, last=False):
        if self.logo:
            return None
        return BlindScreen.jump(self, last)

    def StopElseSpeak(self):
        """Moving rows also stops the earphone reminder, or cancels its wait."""
        BlindScreen.StopElseSpeak(self)
        self.app.stopSoundBufNumber_(SOUND_EARPHONE)
        RunLoop.main().cancelPerform(self, 'sound_earphone')

    def sound_earphone(self, *_):
        self.play(SOUND_EARPHONE)

    # -[startIntroPage shakeDevice] 0x17178
    def shakeDevice(self):
        """The story, and the music under it.

        Nothing in ``startIntroPage`` calls this - ``skipAction`` only cancels it
        (0x1892e).  ``intro2storyPage`` is the screen that would have, and nothing
        creates one of those either, so *As the ozone* is never heard in the shipped
        game.  **Reproduced**: it is here, and nothing calls it.
        """
        self.app.stopSoundBufNumber_(SOUND_WELCOME)
        self.play(SOUND_STORY)
        self.text = STORY_TEXT
        if self.app.playback is not None:
            # 0x17224: the gain is 0x3D4CCCCD, 0.05, and Loop is YES.
            self.app.playback.startBGPlayer_type_soundGain_Loop_(
                'bgm_start_end', 'wav', volume.music(0.05), True)

    # -[startIntroPage tapCount] 0x18728 - a double tap anywhere skips.
    def activate(self):
        if self.logo:
            self.skip_logo()                                  # Enter skips the logo alone
            return self.selectMenu
        self.skipAction()
        return self.selectMenu

    # -[startIntroPage skipAction] 0x188bc
    def skipAction(self, *_):
        """PORT ADDITION to the original's: skipping during the logo, which the phone
        gave no way to do, stops its sound and never builds the screen."""
        for num in (SOUND_WELCOME, SOUND_BGM_START_END, SOUND_STORY,
                    SOUND_DOUBLE_TAP, SOUND_EARPHONE, SOUND_LOGO):
            self.app.stopSoundBufNumber_(num)
        RunLoop.main().cancelPerform(self, 'shakeDevice')
        RunLoop.main().cancelPerform(self, 'sound_earphone')
        RunLoop.main().cancelPerform(self, 'play_logo')
        RunLoop.main().cancelPerform(self, 'realStartIntro')
        RunLoop.main().cancelPerform(self, 'startIntro1')
        self.logo = False
        self.next_screen = 'menu'
        return True

    def goBackAction_(self, *_):
        """There is no Back on the opening screen; Escape skips, as a double tap
        does."""
        return self.skipAction()

    def teardown(self):
        RunLoop.main().cancelPerform(self)
        BlindScreen.teardown(self)


#: 0x17a9e, set on ``explainLabel`` behind sound 14.  The original's own wording, with
#: its layout whitespace collapsed.
WELCOME_TEXT = (
    'Welcome to [Sixth Sense : The zombie]. This game provides itself Voice Over '
    'function. Please turn off the Voice Over function for normal game progress. '
    '[Sixth Sense : The zombie] is a shooting game conducted by voice. You must use '
    'earphone supporting stereo before playing the game. Warning! It may be hard to '
    'play the game normally in a noisy environment. Also the old, weak or the '
    'pregnant should abstain from playing this game.'
)

#: 0x171e4, set on ``explainLabel`` behind sound 15 - what the story says.
STORY_TEXT = (
    'As the ozone layer has disappeared due to global environment destruction, '
    'people suffered from skin cancer. The cell increase project which can overcome '
    'skin cancer was carried out across the world. Although clinical test seemed to '
    'be successful, there was a very fatal side effect. It turned people into '
    'zombies with a big appetite. Zombie virus attacked the whole world in the blink '
    'of an eye and people hid in caves or basements avoiding light and zombies. You '
    'have to get rid of zombies only by voice to keep your families from '
    'approaching zombies.'
)
