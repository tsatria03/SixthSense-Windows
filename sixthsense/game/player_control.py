"""``PlayerControl`` - the player's state.  A plain record; the original has no methods
beyond the accessors (0x12b94..0x12f71).

    HP                   3 at ``-[Stage_1_E viewDidLoad]`` 0x2cdc6
    useWepon             index into ``Stage_1_E.weaponSource``
    killMonsterCount     total kills, shown in ``targetMonsterCountLabel``
    HeadShotCount        headshot kills
    playerXplot          20   ) the start cell, 0x2cf04 / 0x2cf1a
    playerYplot          680  )
    gunEggCountAll / gunEggCountShot / gunEggCout / gunDamage
    killMonster1count .. killMonster11count, killMonster5000count
                         per-kind kill tallies, driven by ``-[Stage_1_E MonsterKillCount:]``
"""
from __future__ import annotations


class PlayerControl:
    def __init__(self):
        self.HP = 0
        self.useWepon = 0
        self.killMonsterCount = 0
        self.HeadShotCount = 0
        self.playerXplot = 0
        self.playerYplot = 0
        self.gunEggCountAll = 0
        self.gunEggCountShot = 0
        self.gunEggCout = 0
        self.gunDamage = 0
        self.killMonster1count = 0
        self.killMonster2count = 0
        self.killMonster3count = 0
        self.killMonster4count = 0
        self.killMonster5count = 0
        self.killMonster6count = 0
        self.killMonster7count = 0
        self.killMonster8count = 0
        self.killMonster9count = 0
        self.killMonster10count = 0
        self.killMonster11count = 0
        self.killMonster5000count = 0

    def __repr__(self):
        return '<Player HP=%d w=%d at (%d,%d) kills=%d>' % (
            self.HP, self.useWepon, self.playerXplot, self.playerYplot,
            self.killMonsterCount)
