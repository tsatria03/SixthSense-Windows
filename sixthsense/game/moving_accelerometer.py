"""``MovingAccelerometer`` - which way the player is facing.

Facing is an ``Angle`` in whole degrees, stepped 10 at a time, plus a coarse compass
reading ``PostionEWSN`` derived from it.

    -[MovingAccelerometer rotationLeft]       0xfed8   Angle -= 10; if (Angle == -10) Angle = 350;
    -[MovingAccelerometer rotationRight]      0x10028  Angle += 10; if (Angle >= 360) Angle = 0;

``rotationLeft``/``rotationRight`` then set the 4-way compass, and
``rotationLeftEight``/``rotationRightEight`` (0x10178 / 0x10378) set the 8-way one, off
the same ``Angle``.  The thresholds are in radians, on ``Angle * M_PI / 180``:

    4-way   < pi/4 or > 7pi/4        -> 1   (N)
            pi/4 .. 3pi/4            -> 2   (E)
            3pi/4 .. 5pi/4           -> 3   (S)
            5pi/4 .. 7pi/4           -> 4   (W)

    8-way   < pi/8 or > 15pi/8       -> 1   (N)
            pi/8  ..  3pi/8          -> 5   (NE)
            3pi/8 ..  5pi/8          -> 2   (E)
            5pi/8 ..  7pi/8          -> 6   (SE)
            7pi/8 ..  9pi/8          -> 3   (S)
            9pi/8 .. 11pi/8          -> 7   (SW)
           11pi/8 .. 13pi/8          -> 4   (W)
           13pi/8 .. 15pi/8          -> 8   (NW)

``-[MovingAccelerometer accelerometer:didAccelerate:]`` (0xfc70) is what turns the phone
into a steering wheel:

    Pitch = atan(y / sqrt(x*x + z*z)) * 180 / M_PI;
    Roll  = atan(x / sqrt(y*y + z*z)) * 180 / M_PI;
    if (PosType == 0) { ... Pitch vs +-20 ... } else { ... }
    -> past +-20 degrees it calls rotationRight / rotationLeft, one 10-degree step per
       accelerometer callback.

Nothing in the binary creates a ``MovingAccelerometer`` or sends
``setListenerRotation:``, so the original never turns you.  The port keeps the class,
ported, for the one thing it does use: ``Stage_1_E`` reads its starting angle, 0, to set
the listener once as a stage begins.  The turn keys that once called
``rotationLeftEight``/``rotationRightEight`` were removed on 2026-09-23.
"""
from __future__ import annotations

import math

# PostionEWSN values
N, E, S, W, NE, SE, SW, NW = 1, 2, 3, 4, 5, 6, 7, 8

_PI = math.pi


class MovingAccelerometer:
    def __init__(self):
        self.acceler = None
        self.Pitch = 0.0
        self.Roll = 0.0
        self.PostionEWSN = N
        self.Angle = 0
        self.PosType = 0

    # -[MovingAccelerometer initWithAccelermeter:] 0xfbe8
    def initWithAccelermeter_(self, angle):
        self.Angle = int(angle)
        self.PostionEWSN = N
        self.PosType = 0
        return self

    # ---- 4-way ------------------------------------------------------------
    def _compass4(self):
        r = self.Angle * _PI / 180.0
        if r < _PI / 4 or r > 7 * _PI / 4:
            self.PostionEWSN = N
        elif r <= 3 * _PI / 4:
            self.PostionEWSN = E
        elif r <= 5 * _PI / 4:
            self.PostionEWSN = S
        elif r <= 7 * _PI / 4:
            self.PostionEWSN = W
        else:
            self.PostionEWSN = N

    # ---- 8-way ------------------------------------------------------------
    def _compass8(self):
        r = self.Angle * _PI / 180.0
        if _PI / 8 <= r <= 3 * _PI / 8:
            self.PostionEWSN = NE
        elif 3 * _PI / 8 <= r <= 5 * _PI / 8:
            self.PostionEWSN = E
        elif 5 * _PI / 8 <= r <= 7 * _PI / 8:
            self.PostionEWSN = SE
        elif 7 * _PI / 8 <= r <= 9 * _PI / 8:
            self.PostionEWSN = S
        elif 9 * _PI / 8 <= r <= 11 * _PI / 8:
            self.PostionEWSN = SW
        elif 11 * _PI / 8 <= r <= 13 * _PI / 8:
            self.PostionEWSN = W
        elif 13 * _PI / 8 <= r <= 15 * _PI / 8:
            self.PostionEWSN = NW
        else:
            self.PostionEWSN = N

    # -[MovingAccelerometer rotationLeft] 0xfed8
    def rotationLeft(self):
        self.Angle -= 10
        if self.Angle == -10:
            self.Angle = 350
        self._compass4()

    # -[MovingAccelerometer rotationRight] 0x10028
    def rotationRight(self):
        self.Angle += 10
        if self.Angle >= 360:
            self.Angle = 0
        self._compass4()

    # -[MovingAccelerometer rotationLeftEight] 0x10178
    def rotationLeftEight(self):
        self.Angle -= 10
        if self.Angle == -10:
            self.Angle = 350
        self._compass8()

    # -[MovingAccelerometer rotationRightEight] 0x10378
    def rotationRightEight(self):
        self.Angle += 10
        if self.Angle >= 360:
            self.Angle = 0
        self._compass8()

    # -[MovingAccelerometer accelerometer:didAccelerate:] 0xfc70
    def accelerometer_didAccelerate_(self, x, y, z):
        denom_p = math.sqrt(x * x + z * z)
        denom_r = math.sqrt(y * y + z * z)
        self.Pitch = math.atan(y / denom_p) * 180.0 / _PI if denom_p else 0.0
        self.Roll = math.atan(x / denom_r) * 180.0 / _PI if denom_r else 0.0
        self.tiltWithPitch_(self.Pitch)

    def tiltWithPitch_(self, pitch):
        """The +-20 degree comparison at 0xfdfc..0xfe48."""
        if pitch >= 20.0:
            self.rotationRightEight()
        elif pitch <= -20.0:
            self.rotationLeftEight()

    @property
    def radians(self):
        """``Angle`` as the listener rotation ``oalPlayback`` wants."""
        return self.Angle * _PI / 180.0

    def __repr__(self):
        return '<Facing %d deg EWSN=%d>' % (self.Angle, self.PostionEWSN)
