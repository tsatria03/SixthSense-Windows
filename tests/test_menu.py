"""The main menu: the eight rows, the coin economy and the voice-over toggle."""
from __future__ import annotations

import os
import plistlib
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sixthsense import paths                                     # noqa: E402
from sixthsense.game.app_delegate import AppDelegate             # noqa: E402
from sixthsense.game.main_controller import (COIN_INTERVAL, COIN_MAX,  # noqa: E402
                                             ROWS, MainController)
from sixthsense.platform.defaults import UserDefaults            # noqa: E402
from sixthsense.platform.runloop import RunLoop                  # noqa: E402


class _Recorder:
    def __init__(self):
        self.said = []

    def speak(self, text, interrupt=True):
        self.said.append(text)
        return True

    def stop(self):
        pass


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
    """The eight rows selectTapPointSoundStart (0x9825) claims, with their sounds."""
    assert [r[0] for r in ROWS] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert [r[3] for r in ROWS] == ['coin', 'title', 'start', 'tutorial',
                                    'ranking', 'store', 'modechange', 'gamecenter']
    assert [r[2] for r in ROWS] == [334, 16, 17, 23, 333, 18, 332, 367]
    # every one of them is a real entry with a WAV behind it
    sl = plistlib.load(open(paths.path_for_resource('SoundList', 'plist'), 'rb'))
    for _n, _f, sound, _a in ROWS:
        assert os.path.exists(os.path.join(paths.sounds(), sl[sound] + '.wav')), sound


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
        assert seen == ['start', 'tutorial', 'ranking', 'store', 'modechange',
                        'gamecenter', 'coin', 'title'], seen
        m.selectMenu = 1
        m.move(-1)
        assert m.selectMenu == 8, 'moving up off the top did not wrap'
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


def test_starting_before_the_tutorial_spends_no_coin():
    """0x2e08e-0x2e0dc: the original runs the tutorial before a coin is ever at
    stake. The port sends the player to its own tutorial screen instead."""
    m = _menu(coins=2)
    d = UserDefaults.standardUserDefaults()
    d.setObject_forKey_('0', 'TUTORIAL')
    d.synchronize()
    try:
        m.selectMenu = 3
        m.activate()
        assert m.next_screen == 'tutorial'
        assert m.app.Coin == 2, 'a coin was spent before the tutorial was done'
        assert m.coinTimer is None
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
    m = _menu(coins=0)
    try:
        m.selectMenu = 3
        m.activate()
        assert m.next_screen is None, 'it started a game with no coin'
        assert any('No coin' in s for s in m.speech.said)
    finally:
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


def test_the_server_rows_decline_instead_of_pretending():
    """Ranking and Game Center need the publisher's server.  The Store does not -
    its gold is a local key - so it is ported and opens."""
    m = _menu()
    try:
        for num, action in ((5, 'ranking'), (8, 'gamecenter')):
            m.speech.said.clear()
            m.selectMenu = num
            m.activate()
            assert m.next_screen is None, '%s pushed a screen' % action
            assert m.speech.said, '%s said nothing at all' % action
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
