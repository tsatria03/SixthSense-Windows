#!/usr/bin/env python
"""SixthSense - Windows port.  Entry point.

``kr.co.bitbee.sixsense`` 1.2 was an iPhone audio game: you walk down a corridor in the
dark and shoot what you hear coming.  This runs the same game on Windows, off the same
data files, with OpenAL Soft doing what iOS's OpenAL did.

Run it with headphones on - the game says so itself (``SoundList[234]``).

    python SixthSense.py                 the menu, as the original opens
    python SixthSense.py --stage         straight into the stage
    python SixthSense.py --tutorial      straight into the tutorial
    python SixthSense.py --game DIR      read the app bundle from somewhere else
    python SixthSense.py --debug         nothing hurts you, and no kill, score or gold counts

The screen loop below stands in for ``UINavigationController``: the menu pushes the
stage or the tutorial, and when one ends the menu comes back.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time

log = logging.getLogger('main')


def _new_stage():
    from sixthsense.game.stage_1_e import Stage_1_E
    st = Stage_1_E()
    st.viewDidLoad()
    return st


def _new_tutorial():
    from sixthsense.game.stage_tutorial import Stage_Tutorial
    st = Stage_Tutorial()
    st.viewDidLoad()
    return st


def _new_test_range(testWeapon):
    from sixthsense.game.stage_1_test import Stage_1_TEST
    st = Stage_1_TEST(testWeapon)
    st.viewDidLoad()
    return st


def _new_menu():
    from sixthsense.game.main_controller import MainController
    m = MainController()
    m.viewDidLoad()
    return m


def _new_intro():
    from sixthsense.game.intro import StartIntroPage
    page = StartIntroPage()
    page.viewDidLoad()
    return page


def _new_screen(name, arg=None):
    """One of the blind-mode screens the shop row leads to.

    The original pushes these onto a ``UINavigationController``; the frame loop keeps
    a stack of its own and does the same.
    """
    from sixthsense.game.inventory import (DetailInventoryController,
                                           InventoryController)
    from sixthsense.game.store import (DetailStoreController, MainStoreController,
                                       StoreController)
    made = {
        'store': lambda: MainStoreController(),
        'store_weapons': lambda: StoreController(),
        'store_detail': lambda: DetailStoreController(arg),
        'inventory': lambda: InventoryController(),
        'inventory_detail': lambda: DetailInventoryController(arg),
    }[name]()
    made.startRead()
    return made


#: The screens that play: the clock stops under F1 and losing focus pauses them.
STAGES = ('stage', 'tutorial', 'weapon_test')

#: The screens that are pushed rather than swapped in.
PUSHED = ('store', 'store_weapons', 'store_detail', 'inventory',
          'inventory_detail')


def main(argv=None):
    ap = argparse.ArgumentParser(description='SixthSense (Windows port)')
    ap.add_argument('--game', help="the original app bundle's contents, or a folder "
                                    'holding Payload/sixsense.app (default: game/)')
    ap.add_argument('--stage', action='store_true',
                    help='skip the menu and start the stage')
    ap.add_argument('--tutorial', action='store_true',
                    help='skip the menu and start the tutorial')
    ap.add_argument('--skip-tutorial', action='store_true',
                    help='write TUTORIAL=1, exactly as the tutorial does when it is '
                         'finished; Stage_1_E does not walk until that key is set')
    ap.add_argument('--no-window', action='store_true',
                    help='run headless (keyboard input unavailable)')
    ap.add_argument('--no-intro', action='store_true',
                    help='open on the menu instead of the splash and the warning')
    ap.add_argument('--debug', action='store_true',
                    help='nothing hurts you and you cannot die, and no kill, '
                         'headshot, score or gold counts')
    ap.add_argument('-v', '--verbose', action='store_true')
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(levelname)-7s %(name)-8s %(message)s')

    from sixthsense import paths
    if args.game:
        paths.set_game(args.game)

    from sixthsense.game.app_delegate import AppDelegate
    from sixthsense.platform.defaults import UserDefaults
    from sixthsense.platform.runloop import RunLoop

    app = AppDelegate.shared()
    app.didFinishLaunching()
    app.debug = args.debug
    from sixthsense.platform.keymap import KeyMap
    KeyMap.shared().debug = args.debug
    defaults = UserDefaults.standardUserDefaults()
    loop = RunLoop.main()

    if args.skip_tutorial:
        defaults.setObject_forKey_('1', 'TUTORIAL')
        defaults.synchronize()

    # ---- headless -------------------------------------------------------
    if args.no_window:
        obj = _new_tutorial() if args.tutorial else _new_stage()
        try:
            while obj.running:
                loop.pump()
                time.sleep(1.0 / 60.0)
        except KeyboardInterrupt:
            pass
        obj.teardown()
        return 0

    import pygame
    from sixthsense.ui.focus import focus_lost, interrupt_stop
    from sixthsense.ui.input import Input
    from sixthsense.ui.keybind_screen import KeyBindScreen
    from sixthsense.ui.menu_input import MenuInput
    from sixthsense.ui.screen_input import ScreenInput

    # Only what the port uses.  pygame.init() also starts the SDL mixer, which opens a
    # second audio device beside the OpenAL one the whole game plays through.
    pygame.display.init()
    pygame.font.init()
    pygame.display.set_caption('SixthSense (debug)' if args.debug else 'SixthSense')
    display = pygame.display.set_mode((640, 400))
    font = pygame.font.SysFont('Consolas', 16)
    clock = pygame.time.Clock()
    bindings = KeyBindScreen()
    showing_bindings = False

    if args.tutorial:
        kind, obj = 'tutorial', _new_tutorial()
    elif args.stage:
        kind, obj = 'stage', _new_stage()
    elif args.no_intro:
        kind, obj = 'menu', _new_menu()
    else:
        kind, obj = 'intro', _new_intro()
    if kind == 'menu':
        inp = MenuInput(obj)
    elif kind == 'intro':
        inp = ScreenInput(obj)
    else:
        inp = Input(obj)
    stack = []                     # (kind, screen, input) below the current one

    quitting = False
    while not quitting:
        closing = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                # The window's close button or Alt+F4 quits the game from any screen.
                # Escape is a key, not this, so it still goes back, pauses or leaves
                # the menu as each screen decides.
                closing = True
                break
            if focus_lost(event, pygame) and kind in STAGES:
                interrupt_stop(obj)         # losing focus is pressing P (ui/focus.py)
            if showing_bindings:
                bindings.handle(event, pygame)
            else:
                inp.handle(event, pygame)
        if closing:
            break

        # F1 - the bindings see all the input.  Over a stage or the tutorial the clock
        # stops too, so no zombie walks while you read, and it starts again where it
        # was when they close.  Behind a menu it keeps ticking.
        if getattr(inp, 'open_bindings', False):
            inp.open_bindings = False
            if hasattr(inp, 'reset'):
                inp.reset()
            showing_bindings = True
            if kind in STAGES:
                loop.hold()
            bindings.open()
        elif showing_bindings and bindings.done:
            showing_bindings = False
            loop.resume()
            if hasattr(inp, 'reset'):
                inp.reset()

        if hasattr(inp, 'pump'):
            inp.pump()
        loop.pump()

        # ---- screen changes ---------------------------------------------
        if not showing_bindings:
            want = getattr(obj, 'next_screen', None)
            if want:
                obj.next_screen = None
                name, arg = want if isinstance(want, tuple) else (want, None)
                if name in PUSHED:
                    stack.append((kind, obj, inp))
                    kind, obj = name, _new_screen(name, arg)
                    inp = ScreenInput(obj)
                elif name == 'menu':
                    obj.teardown()              # the intro is replaced, not stacked
                    kind, obj = 'menu', _new_menu()
                    inp = MenuInput(obj)
                elif name == 'weapon_test':
                    # -[DetailStoreController testAction:] pushes Stage_1_TEST over the
                    # weapon's page, and its back row pops back to it.
                    stack.append((kind, obj, inp))
                    kind, obj = name, _new_test_range(arg)
                    inp = Input(obj)
                else:
                    obj.teardown()
                    kind = name
                    obj = _new_tutorial() if name == 'tutorial' else _new_stage()
                    inp = Input(obj)
                log.info('-> %s', name)
            elif getattr(obj, 'done', False) and stack:
                obj.teardown()
                kind, obj, inp = stack.pop()
                log.info('-> %s', kind)
            elif kind == 'weapon_test' and not obj.running:
                obj.teardown()
                kind, obj, inp = stack.pop()
                log.info('-> %s', kind)
            elif kind in ('stage', 'tutorial') and not obj.running:
                obj.teardown()
                kind, obj = 'menu', _new_menu()
                inp = MenuInput(obj)
                log.info('-> menu')
            elif inp.quit:
                if kind == 'menu':
                    quitting = True
                else:
                    obj.teardown()          # Escape in the tutorial
                    kind, obj = 'menu', _new_menu()
                    inp = MenuInput(obj)
                    log.info('-> menu')

        # ---- drawing ----------------------------------------------------
        display.fill((12, 12, 16))
        if showing_bindings:
            lines = bindings.render_lines()
        elif kind == 'menu':
            lines = _menu_lines(obj)
        elif kind == 'intro':
            lines = _intro_lines(obj)
        elif kind in PUSHED:
            lines = _screen_lines(kind, obj)
        else:
            lines = _stage_lines(obj, inp)
        y = 12
        for line in lines:
            display.blit(font.render(line, True, (205, 205, 215)), (16, y))
            y += 19
        pygame.display.flip()
        clock.tick(60)

    obj.teardown()
    # ...and every screen still stacked under it, or the menu under the shop would
    # keep its coin timer running.
    while stack:
        stack.pop()[1].teardown()
    pygame.quit()
    return 0


def _menu_lines(menu):
    from sixthsense.game.main_controller import ROWS
    out = ['SixthSense   headphones recommended', '',
           'coins %d      next coin in %s' % (menu.app.Coin, menu.coin_clock), '']
    if getattr(menu, 'message', ''):
        out += [menu.message, '']
    for num, _flag, _sound, action in ROWS:
        out.append('%s %s' % ('>' if num == menu.selectMenu else ' ', action))
    out += ['', 'Up/Down move   Enter choose   F1 key bindings   Esc quit']
    return out


def _intro_lines(page):
    if page.splash:
        return ['SixthSense', '', '0_splash2.png']
    out = ['SixthSense   headphones required', '']
    # wrap the warning the original puts on explainLabel
    words, line = page.text.split(), ''
    for w in words:
        if len(line) + len(w) + 1 > 72:
            out.append(line)
            line = w
        else:
            line = (line + ' ' + w).strip()
    out.append(line)
    out += ['', 'Enter or Escape skips to the menu', 'Up/Down reads the two rows']
    return out


#: What each shop and inventory row is called, for anyone who can see the window.
#: The player hears the original's own WAV.
SCREEN_ROWS = {
    'store': {1: 'back', 2: 'weapon shop', 4: 'inventory', 5: 'coin store',
              6: 'restore purchases'},
    'store_weapons': {1: 'back', 2: 'your gold', 3: 'shotgun', 4: 'M4A1',
                      5: 'AK47', 6: 'MG80', 7: 'japanese sword', 8: 'grenade',
                      9: 'buy every weapon'},
    'store_detail': {1: 'back', 2: 'name', 3: 'ammo capacity',
                     4: 'effective range', 5: 'damage', 6: 'price',
                     7: 'buy', 8: 'try'},
    'inventory': {1: 'back', 2: 'grenade', 3: 'knife', 4: 'colt', 5: 'shotgun',
                  6: 'M4A1', 7: 'AK47', 8: 'MG80', 9: 'japanese sword'},
    'inventory_detail': {1: 'back', 2: 'name', 3: 'ammo capacity',
                         4: 'effective range', 5: 'damage', 6: 'price',
                         7: 'state', 8: 'equip / unequip'},
}
SCREEN_TITLE = {
    'store': 'STORE', 'store_weapons': 'WEAPON SHOP', 'store_detail': 'WEAPON',
    'inventory': 'INVENTORY', 'inventory_detail': 'WEAPON',
}


def _screen_lines(kind, screen):
    out = ['SixthSense   %s' % SCREEN_TITLE[kind], '',
           'gold %d' % screen.app.haveGold]
    if kind in ('store_detail', 'inventory_detail'):
        out.append('%s   ammo %s   range %dm   damage %d   price %dG'
                   % (screen.__class__.__name__, screen.ammocapacity,
                      screen.effetiverange, screen.power, screen.price))
        if hasattr(screen, 'used'):
            out.append('state: %s' % ('equipped' if screen.used else 'unequipped'))
        if getattr(screen, 'message', ''):
            out.append(screen.message)
    out.append('')
    names = SCREEN_ROWS[kind]
    for row in screen.rows():
        out.append('%s %s' % ('>' if row == screen.selectMenu else ' ',
                              names.get(row, 'row %d' % row)))
    out += ['', 'Up/Down move   Enter choose   Esc back   F1 key bindings']
    return out


#: What each row of the panel is called, for the screen.  The player hears the
#: original's own WAV; this is only for anyone who can see the window.
PANEL_ROWS = {
    1: 'paused / game over', 2: 'zombies killed', 3: 'headshots', 4: 'score',
    5: 'gold', 9: 'rank', 10: 'top score', 6: 'continue / next stage',
    7: 'restart (costs a coin)', 8: 'main menu',
}
PANEL_TITLE = {1: 'PAUSED', 2: 'MISSION COMPLETE', 3: 'GAME OVER'}


def _panel_lines(stage):
    """``-[Stage_1_E selectTapPointSoundStart]``'s ten bands, as a list."""
    out = ['SixthSense   %s' % PANEL_TITLE.get(stage.gameState, ''), '',
           'zombies %s   headshots %s   score %s   gold %s'
           % (stage.killZombiesLabel, stage.HeadShotLabel,
              stage.ScoreLabel, stage.GoldLabel),
           'top score %s   rank %s' % (stage.TopScoreLabel, stage.RankLabel),
           '']
    for row in stage.pause_rows():
        out.append('%s %s' % ('>' if row == stage.selectMenu else ' ',
                              PANEL_ROWS[row]))
    out += ['', 'Up/Down move   Enter choose   F1 key bindings'
            + ('   Esc resume' if stage.gameState == 1 else '')]
    return out


def _stage_lines(stage, inp):
    if stage.gameState != 0:
        return _panel_lines(stage)
    p = stage.gamePlayer
    w = stage.weaponSource[p.useWepon]
    lines = [
        'SixthSense   headphones recommended',
        '',
        'HP %d      weapon %s (%d rounds)' % (
            p.HP, '-' if w is None else
            ('#%d dmg %d rng %d' % (w.WeaponNumber, w.Damage, w.Range)),
            0 if w is None else w.BulletCount),
        'cell (%d, %d)   facing %d deg   mode %d   level %d' % (
            p.playerXplot, p.playerYplot, stage.facing.Angle,
            stage.gameMode, stage.LVUP),
        'kills %d   headshots %d   score %d' % (
            p.killMonsterCount, p.HeadShotCount, stage.score),
        '',
        'monsters:',
    ]
    for m in stage.MonsterBuffer:
        lines.append('   kind %-3d lane %d  %4.0f cm  bearing %3d%s' % (
            m.monsterNumber, m.MovingType, m.monsterRange, m.MovingPosAngle,
            '   HEAD OPEN' if m.headShotFlag else ''))
    km = inp.keymap
    lines += ['',
              'attack   9:00 %s   10:30 %s   12 %s   1:30 %s   3:00 %s'
              % tuple(km.keys_text('lane%d' % i) for i in range(1, 6)),
              'reload %s   turn %s / %s   weapon %s'
              % (km.keys_text('reload'), km.keys_text('turn_left'),
                 km.keys_text('turn_right'), km.keys_text('next_weapon')),
              'shake %s   pause %s   F1 key bindings   Esc %s'
              % (km.keys_text('shake'), km.keys_text('pause'),
                 'back to the menu' if getattr(stage, 'ESCAPE_LEAVES', False) else 'pause')]
    if stage.app.debug:
        lines.append('debug   %s next level   %s next section   %s spawn   %s choose   '
                     '%s hold   %s where'
                     % tuple(km.keys_text(a) for a in (
                         'debug_next_level', 'debug_next_section', 'debug_spawn',
                         'debug_spawn_kind',
                         'debug_freeze', 'debug_monsters')))
    return lines


if __name__ == '__main__':
    sys.exit(main())
