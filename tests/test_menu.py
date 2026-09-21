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
        assert m.coin_clock == '10:00', m.coin_clock
        assert m.coinTimer is not None, 'the recharge clock did not start'
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


def test_a_coin_comes_back_after_ten_minutes():
    """coinTiemrControlStart (0xbe01) / coinUpTimer (0xc0b1): 600 s, capped at 5."""
    assert COIN_INTERVAL == 600.0
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
