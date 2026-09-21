"""``MakeMaps`` - the three-layer grid the stage walks over.

``maps`` is an array of rows, each row an array of cell dictionaries.  Every cell carries
the same four keys, written by the initialisers below:

    "X"  column, as a decimal string      "Y"  row, as a decimal string
    "G"  ground layer  (g_CH1_E)          "A"  action layer (a_CH1_E.txt)
    "V"  sound layer   (s_CH1_E.txt)

``-[MakeMaps initWithMapGroundFileString:soundPosFileName:actionPosFileName:]`` (0xf6b0)
takes the three files already read into strings, splits each by "\\n" and each row by " ",
and builds the grid:

    for (y = 0; y < ground.count; y++) {
        g = [ground[y] componentsSeparatedByString:@" "];
        s = [sound [y] componentsSeparatedByString:@" "];
        a = [action[y] componentsSeparatedByString:@" "];
        row = [NSMutableArray array];
        for (x = 0; x < g.count; x++) {
            d = [NSMutableDictionary dictionary];
            [d setObject:[NSString stringWithFormat:@"%d", y] forKey:@"Y"];
            [d setObject:[NSString stringWithFormat:@"%d", x] forKey:@"X"];
            [d setObject:s[x] forKey:@"V"];
            [d setObject:g[x] forKey:@"G"];
            [d setObject:a[x] forKey:@"A"];
            [row addObject:d];
        }
        [maps addObject:row];
    }

``-[MakeMaps initWithMapGroundFile:soundPosFileName:]`` (0xf3bc) is the other shape: it
reads two *unsplit* files out of the bundle (``stage1ground``/``stage1sound``, 400x400
single characters, no separators) and indexes them by character, with no "A" layer.

The shipped CH1 map is 701 rows of 41 columns.  Column 20 holds ground 21 for rows
21..679 - a one-cell-wide corridor - and ground 23 at rows 387 and 388.  The action layer
fires the tutorial/stage beats: 9, 8, 10 then 1..7 as Y decreases, which is the direction
the player walks (``-[Stage_1_E MainControl]`` steps ``playerYplot`` down by one).
"""
from __future__ import annotations

import logging

log = logging.getLogger('maps')



def _int(v, default=0):
    """``-[NSString intValue]`` on a cell."""
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return default


class MakeMaps:
    def __init__(self):
        self.dataIN = False
        self.maps = []
        self.mapsFollowing = []

    # -[MakeMaps initWithMapGroundFileString:soundPosFileName:actionPosFileName:] 0xf6b0
    def initWithMapGroundFileString_soundPosFileName_actionPosFileName_(
            self, ground, sound, action):
        g_rows = (ground or '').split('\n')
        s_rows = (sound or '').split('\n')
        a_rows = (action or '').split('\n')
        self.maps = []
        for y in range(len(g_rows)):
            g = g_rows[y].split(' ')
            s = s_rows[y].split(' ') if y < len(s_rows) else []
            a = a_rows[y].split(' ') if y < len(a_rows) else []
            row = []
            for x in range(len(g)):
                row.append({
                    'Y': str(y),
                    'X': str(x),
                    'V': s[x] if x < len(s) else '0',
                    'G': g[x],
                    'A': a[x] if x < len(a) else '0',
                })
            self.maps.append(row)
        return self

    # -[MakeMaps initWithMapGroundFile:soundPosFileName:] 0xf3bc
    def initWithMapGroundFile_soundPosFileName_(self, ground, sound):
        """The character-indexed form used by ``stage1ground``/``stage1sound``."""
        g_rows = (ground or '').split('\n')
        s_rows = (sound or '').split('\n')
        self.maps = []
        for y in range(len(g_rows)):
            g = g_rows[y]
            s = s_rows[y] if y < len(s_rows) else ''
            row = []
            for x in range(len(g)):
                row.append({
                    'Y': str(y),
                    'X': str(x),
                    'V': s[x] if x < len(s) else '0',
                    'G': g[x],
                })
            self.maps.append(row)
        return self

    # -[MakeMaps initWithMapsX:MapsY:MapsData:] 0xf1d4
    def initWithMapsX_MapsY_MapsData_(self, mapsX, mapsY, mapsData):
        """An empty grid of ``mapsX`` x ``mapsY`` cells, with ``mapsData`` painted in."""
        self.maps = []
        w, h = _int(mapsX), _int(mapsY)
        for y in range(h):
            row = []
            for x in range(w):
                v = self.DataInMethodXplot_yPlot_data_(x, y, mapsData)
                row.append({'Y': str(y), 'X': str(x), 'V': v if v is not None else '0'})
            self.maps.append(row)
        return self

    # -[MakeMaps DataInMethodXplot:yPlot:data:] 0xf0ec
    def DataInMethodXplot_yPlot_data_(self, xplot, yplot, data):
        """The "V" of the first entry of ``data`` whose X and Y match, else nil."""
        if not data:
            return None
        for d in data:
            if _int(d.get('X')) == xplot and _int(d.get('Y')) == yplot:
                return d.get('V')
        return None

    # -[MakeMaps movePlayGroundState:PlotY:] 0xfa54
    #   return [[[[maps objectAtIndex:y] objectAtIndex:x] objectForKey:@"G"] intValue];
    def movePlayGroundState_PlotY_(self, x, y):
        try:
            return _int(self.maps[y][x]['G'])
        except (IndexError, KeyError):
            return 0

    # -[MakeMaps movePlayActionState:PlotY:] 0xfab8 - the same with @"A".
    def movePlayActionState_PlotY_(self, x, y):
        try:
            return _int(self.maps[y][x].get('A', '0'))
        except (IndexError, KeyError):
            return 0

    # -[MakeMaps MovingPlotX:PlotY:] 0xf950
    #   40 rows y-19..y+20 by 40 columns x-19..x+20 of the "V" layer.
    #   (the loops are `for (r = 0; r < 0x28; r++)` and `for (c = -19; c < 0x15; c++)`)
    def MovingPlotX_PlotY_(self, x, y):
        out = []
        for r in range(40):
            row = self.maps[(y - 19) + r]
            inner = []
            for c in range(-19, 21):
                inner.append(row[x + c]['V'])
            out.append(inner)
        return out

    # The same window, but keeping whole cells so the caller can read X/Y/V together.
    # -[Stage_1_E mapPlotSound] walks the cells, not the bare values.
    def MovingPlotCellsX_PlotY_(self, x, y):
        out = []
        for r in range(40):
            yy = (y - 19) + r
            if not (0 <= yy < len(self.maps)):
                out.append([])
                continue
            row = self.maps[yy]
            inner = []
            for c in range(-19, 21):
                xx = x + c
                if 0 <= xx < len(row):
                    inner.append(row[xx])
            out.append(inner)
        return out

    @property
    def height(self):
        return len(self.maps)

    @property
    def width(self):
        return len(self.maps[0]) if self.maps else 0
