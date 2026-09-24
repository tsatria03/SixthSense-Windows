"""The main menu: the rows, the coin economy and the voice-over toggle."""
from __future__ import annotations

import os
import plistlib
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import _scratch_save                                             # noqa: E402,F401  never the real save

from sixthsense import paths                                     # noqa: E402
from sixthsense.game.app_delegate import AppDelegate             # noqa: E402
from sixthsense.game.main_controller import (COIN_INTERVAL, COIN_MAX,  # noqa: E402
                                             ROWS, MainController)
from sixthsense.platform import openal as al                     # noqa: E402
from sixthsense.platform import volume                           # noqa: E402
from sixthsense.platform.defaults import UserDefaults            # noqa: E402
from sixthsense.platform.music import MusicPlayer                # noqa: E402
from sixthsense.platform.runloop import RunLoop                  # noqa: E402


class _Recorder:
    def __init__(self):
        self.said = []
        self.stopped = 0

    def speak(self, text, interrupt=True):
        self.said.append(text)
        return True

    def stop(self):
        self.stopped += 1


def _menu(coins=3):
    d = UserDefaults.standardUserDefaults()
    # simulate a save that is already past its first run, so didFinishLaunching's
    # FIREST grant below never overwrites the COIN this helper is about to set.
    d.setObject_forKey_('1', 'FIREST')
    d.setObject_forKey_(str(coins), 'COIN')
    d.setObject_forKey_('1', 'TUTORIAL')
    d.removeObjectForKey_('COIN_TIMER')
    d.removeObjectForKey_('COIN_TIMER_START')
    d.synchronize()
    app = AppDelegate.shared()
    if app.playback is None:
        app.didFinishLaunching()
    RunLoop.main().reset()
    m = MainController(speech=_Recorder())
    m.viewDidLoad()
    return m


def test_the_rows_are_the_originals():
    """The rows selectTapPointSoundStart (0x9825) claims, with their sounds and their
    original numbers, less ranking (5) and Game Center (8)."""
    assert [r[0] for r in ROWS] == [1, 2, 3, 4, 6, 7]
    assert [r[3] for r in ROWS] == ['coin', 'title', 'start', 'tutorial',
                                    'store', 'modechange']
    assert [r[2] for r in ROWS] == [334, 16, 17, 23, 18, 331]
    # every one of them is a real entry with a WAV behind it
    sl = plistlib.load(open(paths.path_for_resource('SoundList', 'plist'), 'rb'))
    for _n, _f, sound, _a in ROWS:
        assert paths.path_for_resource(sl[sound], 'wav'), sound


def test_the_menu_music_plays_under_the_rows():
    """BGMusicStart is a port addition - the original's MainController never starts music
    (only -[Stage_1_E GameEndAction:] does, 0x330da) - so its gain is the port's to choose.
    It plays at volume.MENU_MUSIC_DB, no louder than the 0.2 every row is read at, instead
    of the 1.0 it started at, which talked over the rows."""
    app = AppDelegate.shared()
    if app.playback is None:
        app.didFinishLaunching()
    pb = app.playback
    calls = []
    pb.startBGPlayer_type_soundGain_Loop_ = lambda n, t, g, l: calls.append((n, g, l))
    try:
        app.BGMusicStart()
        assert calls == [('bgm_main_menu', volume.menu_music(), True)], calls
        assert volume.menu_music() <= 0.2, \
            'the menu music is louder than the rows it plays under'
    finally:
        del pb.startBGPlayer_type_soundGain_Loop_        # back to the real player


class _FakeAL:
    """Enough of platform/openal.AL for MusicPlayer, with nothing behind it."""

    def __init__(self):
        self.calls = []
        self.state = al.AL_PLAYING

    def gen_source(self):
        return 1

    def gen_buffer(self):
        return 2

    def buffer_data(self, *a):
        pass

    def delete_buffer(self, bid):
        self.calls.append(('delete', bid))

    def source_state(self, _sid):
        return self.state

    def alGetError(self):
        return 0

    def alSource3f(self, *a):
        pass

    def alSourcei(self, _sid, param, value):
        self.calls.append(('sourcei', param, value))

    def alSourcef(self, _sid, param, value):
        self.calls.append(('gain', value) if param == al.AL_GAIN else ('sourcef', param))

    def alSourceStop(self, _sid):
        self.calls.append(('stop',))

    def alSourcePlay(self, _sid):
        self.calls.append(('play',))


class _FakeOwner:
    def __init__(self):
        self.al = _FakeAL()


def test_the_menu_music_carries_on_when_the_menu_comes_back():
    """A menu is built fresh every time the player comes back from a stage, the shop or
    the tutorial, and each one calls BGMusicStart.  The music player leaves a source
    alone when it is asked for the file it is already playing, so the music carries on
    instead of jumping back to its first bar - it only takes the new gain."""
    owner = _FakeOwner()
    player = MusicPlayer(owner)
    song = paths.path_for_resource('bgm_main_menu', 'wav')
    other = paths.path_for_resource('bgm_cave', 'wav')
    assert song and other, 'the menu music or the cave music is missing'

    player.play(song, 0.2, -1)
    assert ('play',) in owner.al.calls, 'the first play did not start anything'

    owner.al.calls.clear()
    player.play(song, 0.1, -1)                    # the menu comes back
    assert ('stop',) not in owner.al.calls, 'the same file was stopped and rewound'
    assert ('play',) not in owner.al.calls, 'the same file was restarted'
    assert ('gain', 0.1) in owner.al.calls, 'the new gain was not applied'
    assert player.volume == 0.1

    owner.al.calls.clear()
    player.play(other, 0.02, -1)                  # a different file still starts over
    assert ('play',) in owner.al.calls, 'a different file did not start'

    owner.al.calls.clear()
    owner.al.state = al.AL_STOPPED                # it ran out, so it plays again
    player.play(other, 0.02, -1)
    assert ('play',) in owner.al.calls, 'a finished file did not start again'


def test_changing_the_music_frees_the_file_it_had():
    """OpenAL refuses to delete a buffer that is still attached to a source, so the order
    matters: stop the source, take the buffer off it with AL_BUFFER 0, then delete.  The
    player used to delete first, which freed nothing and held a 2 to 3 MB file for the life
    of the process - and a level change swaps two of them."""
    owner = _FakeOwner()
    player = MusicPlayer(owner)
    song = paths.path_for_resource('bgm_main_menu', 'wav')
    other = paths.path_for_resource('bgm_cave', 'wav')
    assert song and other, 'the menu music or the cave music is missing'

    player.play(song, 0.2, -1)
    owner.al.calls.clear()
    player.play(other, 0.02, -1)

    order = [c for c in owner.al.calls
             if c[0] in ('stop', 'delete') or (c[0] == 'sourcei' and c[1] == al.AL_BUFFER)]
    assert order[0] == ('stop',), order
    assert order[1] == ('sourcei', al.AL_BUFFER, 0), 'the buffer was not detached first'
    assert order[2][0] == 'delete', 'the old buffer was not deleted'
    detach = order.index(('sourcei', al.AL_BUFFER, 0))
    delete = [i for i, c in enumerate(order) if c[0] == 'delete'][0]
    assert detach < delete, 'deleting before detaching frees nothing'


def test_there_is_no_exit_row():
    """exit_flag and Exit: exist, but no row claims them and nothing plays sound 20."""
    assert 'exit' not in [r[3] for r in ROWS]


def test_it_opens_on_the_title_and_wraps():
    m = _menu()
    try:
        assert m.selectMenu == 2                      # 0x85c1
        seen = []
        for _ in range(len(ROWS)):
            m.move(1)
            seen.append(m._row()[3])
        assert seen == ['start', 'tutorial', 'store', 'modechange',
                        'coin', 'title'], seen
        m.selectMenu = 1
        m.move(-1)
        assert m.selectMenu == 7, 'moving up off the top did not wrap'
    finally:
        m.teardown()


def test_a_game_costs_a_coin_and_starts_the_clock():
    """-[MainController StartGameAction:] 0xb2ed"""
    m = _menu(coins=2)
    try:
        m.selectMenu = 3
        m.activate()
        assert m.next_screen == 'stage'
        assert m.app.Coin == 1, 'the coin was not spent'
        assert UserDefaults.standardUserDefaults().intForKey_('COIN') == 1
        assert m.coin_clock == '30:00', m.coin_clock
        assert m.coinTimer is not None, 'the recharge clock did not start'
    finally:
        m.teardown()


def test_the_menu_never_plays_the_earphone_warning():
    """PORT ADDITION: the earphone warning (234) now plays once from the intro
    screen (see tests/case/intro.py), not from the menu at all - it used to play
    at menu load, talking over the title, then briefly from Start Game instead,
    which repeated every time a game was started."""
    played = []
    d = UserDefaults.standardUserDefaults()
    d.setObject_forKey_('1', 'FIREST')
    d.setObject_forKey_('3', 'COIN')
    d.setObject_forKey_('1', 'TUTORIAL')
    d.removeObjectForKey_('COIN_TIMER')
    d.removeObjectForKey_('COIN_TIMER_START')
    d.synchronize()
    app = AppDelegate.shared()
    if app.playback is None:
        app.didFinishLaunching()
    RunLoop.main().reset()
    real_play = app.playSound_Gain_Pos_z_reprats_
    app.playSound_Gain_Pos_z_reprats_ = \
        lambda num, *a, **k: (played.append(num), real_play(num, *a, **k))[-1]
    m = MainController(speech=_Recorder())
    try:
        m.viewDidLoad()
        assert 234 not in played, 'the earphone warning played at menu load'
        m.selectMenu = 3
        m.activate()
        assert 234 not in played, 'the earphone warning played from Start Game'
    finally:
        app.playSound_Gain_Pos_z_reprats_ = real_play
        m.teardown()


def test_the_first_start_spends_a_coin_on_the_tutorial():
    """0xb2ed never reads TUTORIAL: Start spends a coin and pushes Stage_1_E, which runs
    the tutorial inline first.  The port sends the first run to Stage_Tutorial, told
    to count down into the game when it ends."""
    m = _menu(coins=2)
    d = UserDefaults.standardUserDefaults()
    d.setObject_forKey_('0', 'TUTORIAL')
    d.synchronize()
    try:
        m.selectMenu = 3
        m.activate()
        assert m.next_screen == ('tutorial', True), m.next_screen
        assert m.app.Coin == 1, 'the first game did not spend a coin'
        assert m.coinTimer is not None
    finally:
        m.teardown()


def test_the_first_start_with_no_coin_is_refused():
    m = _menu(coins=0)
    d = UserDefaults.standardUserDefaults()
    d.setObject_forKey_('0', 'TUTORIAL')
    d.synchronize()
    try:
        m.selectMenu = 3
        m.activate()
        assert m.next_screen is None, m.next_screen
    finally:
        m.teardown()


def test_spending_a_coin_does_not_restart_a_running_clock():
    """0xbe3a: coinTiemrControlStart returns at once while coinTimer already
    exists, instead of rewriting COIN_TIMER and losing the elapsed progress."""
    m = _menu(coins=3)
    try:
        m.selectMenu = 3
        m.activate()
        first_timer = m.coinTimer
        d = UserDefaults.standardUserDefaults()
        stamp = d.stringForKey_('COIN_TIMER')
        m.selectMenu = 3
        m.activate()
        assert m.coinTimer is first_timer, 'a second coin restarted the clock'
        assert d.stringForKey_('COIN_TIMER') == stamp, 'COIN_TIMER was rewritten'
    finally:
        m.teardown()


def test_no_coin_means_no_game():
    """0xb472-0xb5a0: the original only plays 358 and shows the sentence as text
    on maskLabel1 - nothing about it is spoken."""
    m = _menu(coins=0)
    try:
        m.selectMenu = 3
        m.activate()
        assert m.next_screen is None, 'it started a game with no coin'
        assert 'No coin' in m.message
        assert not m.speech.said, 'the recording should not be spoken over'
    finally:
        m.teardown()


def test_no_coin_stops_after_its_first_two_words():
    """DIVERGENCE: 358 goes on to the coin store and the ranking page, which are
    gone, so it is stopped in the pause after "no coin"."""
    from sixthsense.game.app_delegate import NO_COIN_WORDS_SECONDS
    m = _menu(coins=0)
    app = m.app
    try:
        m.selectMenu = 3
        m.activate()
        i = app.CheckSoundBuf_(358)
        assert i != -1 and app.aSoundBufControlData[i].bIsPlaying, '358 never played'
        loop = RunLoop.main()
        t0 = time.monotonic()
        while time.monotonic() - t0 < NO_COIN_WORDS_SECONDS - 0.3:
            loop.pump()
            time.sleep(0.004)
        assert app.aSoundBufControlData[i].bIsPlaying, '358 stopped before "no coin"'
        while time.monotonic() - t0 < NO_COIN_WORDS_SECONDS + 0.3:
            loop.pump()
            time.sleep(0.004)
        assert not app.aSoundBufControlData[i].bIsPlaying, \
            '358 went on to the coin store and the ranking page'
    finally:
        m.teardown()

def test_debug_mode_starts_a_game_without_a_coin_and_spends_none():
    for coins in (0, 3):
        m = _menu(coins=coins)
        m.app.debug = True
        try:
            d = UserDefaults.standardUserDefaults()
            # The menu may already have its clock running (the safety net starts one
            # whenever the coins are under the cap); Start must leave it as it was.
            clock = (d.stringForKey_('COIN_TIMER_START'), d.stringForKey_('COIN_TIMER'))
            m.selectMenu = 3
            m.activate()
            assert m.next_screen == 'stage', 'debug mode refused to start with %d coins' % coins
            assert m.app.Coin == coins, 'debug mode spent a coin'
            assert d.intForKey_('COIN') == coins
            assert (d.stringForKey_('COIN_TIMER_START'), d.stringForKey_('COIN_TIMER')) \
                == clock, 'debug mode changed the coin clock'
        finally:
            m.app.debug = False
            m.teardown()

def test_the_tutorial_row_needs_no_coin():
    m = _menu(coins=0)
    try:
        m.selectMenu = 4
        m.activate()
        assert m.next_screen == 'tutorial'
        assert m.app.Coin == 0
    finally:
        m.teardown()


def test_a_coin_comes_back_after_thirty_minutes():
    """coinTiemrControlStart (0xbe01) / coinUpTimer (0xc0b1): 1800 s, capped at 5."""
    assert COIN_INTERVAL == 1800.0
    assert COIN_MAX == 5
    m = _menu(coins=1)
    try:
        m.coinTiemrControlStart()
        assert m.coinTimer is not None
        # wind the clock back past the interval
        d = UserDefaults.standardUserDefaults()
        past = time.strftime('%Y-%m-%d %H:%M:%S',
                             time.localtime(time.time() - COIN_INTERVAL - 5))
        d.setObject_forKey_(past, 'COIN_TIMER')
        d.synchronize()
        before = m.app.Coin
        m.coinUpTimer(None)
        assert m.app.Coin == before + 1, 'no coin was granted'
        assert d.intForKey_('COIN') == before + 1
    finally:
        m.teardown()


def test_the_clock_stops_at_five():
    m = _menu(coins=COIN_MAX)
    try:
        m.coinTiemrControlStart()
        assert m.coinTimer is None, 'the clock runs with a full purse'
    finally:
        m.teardown()


def _menu_with_timer_state(coins, coin_timer_start, away_seconds):
    """Like ``_menu`` but sets up a COIN_TIMER of its own, for the catch-up
    tests (0x8aca-0x8b14), instead of clearing it."""
    d = UserDefaults.standardUserDefaults()
    d.setObject_forKey_('1', 'FIREST')
    d.setObject_forKey_(str(coins), 'COIN')
    d.setObject_forKey_('1', 'TUTORIAL')
    d.setObject_forKey_(coin_timer_start, 'COIN_TIMER_START')
    away = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() - away_seconds))
    d.setObject_forKey_(away, 'COIN_TIMER')
    d.synchronize()
    app = AppDelegate.shared()
    if app.playback is None:
        app.didFinishLaunching()
    RunLoop.main().reset()
    m = MainController(speech=_Recorder())
    m.viewDidLoad()
    return m


def test_time_away_grants_a_coin_per_interval_and_keeps_the_leftover():
    """0x8aca-0x8b14: two intervals and ten minutes away grants two coins, and
    the clock keeps counting from the leftover ten minutes rather than
    resetting to a fresh interval (0x8bd8-0x8cf6)."""
    leftover = 600
    m = _menu_with_timer_state(coins=1, coin_timer_start='1',
                               away_seconds=COIN_INTERVAL * 2 + leftover)
    try:
        d = UserDefaults.standardUserDefaults()
        assert m.app.Coin == 3, 'two intervals away should grant two coins'
        assert d.intForKey_('COIN') == 3
        assert d.stringForKey_('COIN_TIMER_START') == '1', 'still under the cap'
        remaining = m.app._coin_timer_remaining()
        expected = COIN_INTERVAL - leftover
        assert abs(remaining - expected) <= 5, \
            'the leftover progress was not kept: %r, expected close to %r' % (remaining, expected)
    finally:
        m.teardown()


def test_time_away_caps_at_five_and_stops_the_clock():
    """0x8b06-0x8b22: past the cap, Coin clamps to 5 and COIN_TIMER_START clears."""
    m = _menu_with_timer_state(coins=4, coin_timer_start='1', away_seconds=COIN_INTERVAL * 5)
    try:
        d = UserDefaults.standardUserDefaults()
        assert m.app.Coin == COIN_MAX
        assert d.intForKey_('COIN') == COIN_MAX
        assert d.stringForKey_('COIN_TIMER_START') == '0', 'the clock should have stopped'
    finally:
        m.teardown()


def test_a_save_with_no_coins_and_no_clock_starts_the_clock():
    """PORT ADDITION: a save at 0 coins with no clock, as a hand edit or an older
    backup can leave it, used to stay at 0 for ever and read "0 minutes 0 seconds".
    Opening the menu now starts the clock, and the coin row reads a real time."""
    m = _menu(coins=0)
    try:
        d = UserDefaults.standardUserDefaults()
        assert d.stringForKey_('COIN_TIMER_START') == '1', 'the clock did not start'
        assert m.coinTimer is not None and m.coinTimer.isValid()
        left = m.app._coin_timer_remaining()
        assert COIN_INTERVAL - 5 <= left <= COIN_INTERVAL, 'the clock reads %r' % left
        m.app.mode = 0
        m.selectMenu = 1
        assert '0 minutes 0 seconds' not in m.row_text(), m.row_text()
    finally:
        m.app.mode = 1
        m.teardown()


def test_a_full_purse_starts_no_clock():
    """At the cap there is nothing to count down to, so no clock starts."""
    m = _menu(coins=COIN_MAX)
    try:
        d = UserDefaults.standardUserDefaults()
        assert d.stringForKey_('COIN_TIMER_START') != '1', 'a clock started at the cap'
        assert m.coinTimer is None
    finally:
        m.teardown()


def test_a_running_clock_is_left_alone():
    """A clock already counting down keeps its time; the safety net does not restart
    it (the same rule as 0xbe3a)."""
    m = _menu_with_timer_state(coins=2, coin_timer_start='1', away_seconds=600)
    try:
        left = m.app._coin_timer_remaining()
        assert abs(left - (COIN_INTERVAL - 600)) <= 5, 'the clock was restarted: %r' % left
    finally:
        m.teardown()


def test_mode_change_toggles_voice_over():
    """-[MainController ModeChageAction:] 0xb831"""
    m = _menu()
    try:
        d = UserDefaults.standardUserDefaults()
        before = m.app.mode
        m.selectMenu = 7
        m.activate()
        assert m.app.mode != before
        assert d.intForKey_('EYEMODE') == m.app.mode, 'EYEMODE was not saved'
        m.activate()
        assert m.app.mode == before, 'it did not toggle back'
    finally:
        m.teardown()


def test_there_is_no_ranking_or_game_center_row():
    """Rows 5 and 8 opened the publisher's ranking server and Apple's Game Center,
    which the port does not have, so they are left out, and moving never lands on
    them."""
    actions = [r[3] for r in ROWS]
    assert 'ranking' not in actions and 'gamecenter' not in actions
    m = _menu()
    try:
        for _ in range(2 * len(ROWS)):
            m.move(1)
            assert m.selectMenu not in (5, 8), m.selectMenu
        for _ in range(2 * len(ROWS)):
            m.move(-1)
            assert m.selectMenu not in (5, 8), m.selectMenu
    finally:
        m.teardown()


def test_the_store_row_opens_the_shop():
    """-[MainController StoreAction:] 0xb6d0 pushes mainStoreController."""
    m = _menu()
    try:
        m.selectMenu = 6
        m.activate()
        assert m.next_screen == 'store'
    finally:
        m.teardown()


def test_a_new_save_starts_with_voice_over_on():
    """DIVERGENCE: a save with no EYEMODE is self-voiced, not the original's mode 0."""
    d = UserDefaults.standardUserDefaults()
    d.removeObjectForKey_('EYEMODE')
    d.synchronize()
    m = _menu()
    try:
        assert m.app.mode == 1
        assert not m.app.screen_reader
    finally:
        m.teardown()


def test_the_voice_over_row_says_what_choosing_it_does():
    """0xa2b8: while voice over is on the row is 332, "voice over off button", and
    while it is off it is 331, "voice over on button" - what choosing it does."""
    m = _menu()
    try:
        m.app.mode = 1
        assert m.row_sound(7) == 332                    # voice over off button
        m.app.mode = 0
        assert m.row_sound(7) == 331                    # voice over on button
        assert m.row_text(7) == 'Voice over on, Button'
    finally:
        m.app.mode = 1
        m.teardown()


def test_moving_off_the_coin_row_stops_the_time_to_the_next_coin():
    """The coin row reads the count, "after", then the minutes 2 s later and the
    seconds after that.  Moving away once "after" has played used to leave the
    minutes and seconds queued, and they were read over the next row."""
    import time as _time
    from sixthsense.game import app_delegate as A
    m = _menu(coins=3)
    app = m.app
    app.mode = 1
    played = []
    real = app.playSound_Gain_Pos_z_reprats_
    app.playSound_Gain_Pos_z_reprats_ = lambda n, *a: (played.append(n), real(n, *a))
    loop = RunLoop.main()

    def run(until, limit):
        end = _time.monotonic() + limit
        while _time.monotonic() < end and not until():
            loop.pump()
            _time.sleep(0.01)
    try:
        m.selectMenu = 1
        m.blindModeSelectedMenu()
        run(lambda: A.TTS_COIN_AFTER in played, 8.0)
        assert A.TTS_COIN_AFTER in played, 'the coin row never said "after"'
        played.clear()
        m.move(1)                                       # on to the title row
        run(lambda: False, 4.0)
        late = [n for n in played if n in range(10) or n in (A.TTS_MINUTES, A.TTS_SECONDS)]
        assert not late, 'the time to the next coin was read over the next row: %r' % played
    finally:
        del app.playSound_Gain_Pos_z_reprats_
        m.teardown()


def test_turning_voice_over_off_speaks_through_the_screen_reader():
    """0xb982: turning it off plays the recording 22, "voice over off", as the
    original does; from then on the rows speak through the screen reader."""
    d = UserDefaults.standardUserDefaults()
    m = _menu()
    played = []
    real = m.app.playSound_Gain_Pos_z_reprats_
    m.app.playSound_Gain_Pos_z_reprats_ = lambda n, *a: (played.append(n), real(n, *a))
    try:
        m.app.mode = 1
        m.selectMenu = 7
        said = len(m.speech.said)
        m.activate()
        assert m.app.mode == 0
        assert played[-1] == 22, played
        assert len(m.speech.said) == said, 'the screen reader spoke the toggle'
        m.app.__dict__.pop('playSound_Gain_Pos_z_reprats_', None)
        m.move(-1)
        assert m.speech.said[-1] == 'Store, Button'
        m.move(-4)                  # store, tutorial, start, title, coin
        assert m.speech.said[-1].startswith('Number of coins, 3.'), m.speech.said[-1]
        m.move(1)
        assert m.speech.said[-1] == 'Sixth Sense: The Zombies'
    finally:
        m.app.__dict__.pop('playSound_Gain_Pos_z_reprats_', None)
        m.app.mode = 1
        d.setObject_forKey_('1', 'EYEMODE')
        d.synchronize()
        m.teardown()


class _Pygame:
    """Just enough of pygame for a keyboard handler: key-downs named by their key."""
    KEYDOWN, KEYUP, QUIT = 1, 2, 3

    class key:
        @staticmethod
        def name(k):
            return k


class _Key:
    def __init__(self, name):
        self.type = _Pygame.KEYDOWN
        self.key = name


def test_home_and_end_in_the_screen_reader_mode():
    """With voice over off, Home and End go to the first row and the last, in the main
    menu and in the shop, as a screen reader's own lists do.  With voice over on, End
    stays where it was."""
    from sixthsense.game.main_controller import ROWS
    from sixthsense.game.store import MainStoreController
    from sixthsense.ui.menu_input import MenuInput
    from sixthsense.ui.screen_input import ScreenInput
    m = _menu()
    shop = MainStoreController(speech=_Recorder())
    try:
        m.app.mode = 0
        keys = MenuInput(m)
        keys.handle(_Key('end'), _Pygame)
        assert m.selectMenu == ROWS[-1][0], 'End went to row %d' % m.selectMenu
        keys.handle(_Key('home'), _Pygame)
        assert m.selectMenu == ROWS[0][0], 'Home went to row %d' % m.selectMenu

        rows = shop.rows()
        keys = ScreenInput(shop)
        keys.handle(_Key('end'), _Pygame)
        assert shop.selectMenu == rows[-1], 'End went to row %d' % shop.selectMenu
        assert shop.speech.said, 'End did not read the row'
        keys.handle(_Key('home'), _Pygame)
        assert shop.selectMenu == rows[0], 'Home went to row %d' % shop.selectMenu

        m.app.mode = 1
        m.selectMenu = 3
        MenuInput(m).handle(_Key('end'), _Pygame)
        assert m.selectMenu == 3, 'End jumped with voice over on'
        shop.selectMenu = rows[1]
        ScreenInput(shop).handle(_Key('end'), _Pygame)
        assert shop.selectMenu == rows[1], 'End jumped in the shop with voice over on'
    finally:
        m.app.mode = 1
        shop.teardown()
        m.teardown()


def test_left_and_right_move_like_voiceovers_flicks_in_the_screen_reader_mode():
    """With voice over off, Right goes to the next row and Left to the previous one, in
    the main menu and in the shop, as VoiceOver's flicks did.  With voice over on, Left
    and Right only repeat the row in the main menu, and do nothing in the shop."""
    from sixthsense.game.main_controller import ROWS
    from sixthsense.game.store import MainStoreController
    from sixthsense.ui.menu_input import MenuInput
    from sixthsense.ui.screen_input import ScreenInput
    m = _menu()
    shop = MainStoreController(speech=_Recorder())
    nums = [r[0] for r in ROWS]
    try:
        m.app.mode = 0
        keys = MenuInput(m)
        m.selectMenu = nums[1]
        keys.handle(_Key('right'), _Pygame)
        assert m.selectMenu == nums[2], 'Right went to row %d' % m.selectMenu
        keys.handle(_Key('left'), _Pygame)
        keys.handle(_Key('left'), _Pygame)
        assert m.selectMenu == nums[0], 'Left went to row %d' % m.selectMenu
        keys.handle(_Key('left'), _Pygame)
        assert m.selectMenu == nums[-1], 'Left did not wrap to the last row'

        rows = shop.rows()
        keys = ScreenInput(shop)
        shop.select(rows[0])
        shop.speech.said.clear()
        keys.handle(_Key('right'), _Pygame)
        assert shop.selectMenu == rows[1], 'Right went to row %d' % shop.selectMenu
        assert shop.speech.said, 'Right did not read the row'
        keys.handle(_Key('left'), _Pygame)
        assert shop.selectMenu == rows[0], 'Left went to row %d' % shop.selectMenu

        m.app.mode = 1
        m.selectMenu = nums[2]
        MenuInput(m).handle(_Key('right'), _Pygame)
        assert m.selectMenu == nums[2], 'Right moved with voice over on'
        shop.selectMenu = rows[1]
        ScreenInput(shop).handle(_Key('left'), _Pygame)
        assert shop.selectMenu == rows[1], 'Left moved in the shop with voice over on'
    finally:
        m.app.mode = 1
        shop.teardown()
        m.teardown()


def test_no_coin_is_read_by_the_screen_reader_with_voice_over_off():
    m = _menu(coins=0)
    try:
        m.app.mode = 0
        m.selectMenu = 3
        m.activate()
        assert m.next_screen is None
        assert m.speech.said[-1] == 'No coin.', m.speech.said
    finally:
        m.app.mode = 1
        m.teardown()


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
