# -*- coding: utf-8 -*-
"""Font registry shared by fitting (PIL / FreeType) and assembly (PowerPoint typeface names).

Each family maps weight -> (font file, variable-font wght or None, PowerPoint typeface, bold flag).
Only weights verified to render correctly in PowerPoint for Mac are listed
(Noto Serif SC variable: ExtraLight maps to the wrong instance in PowerPoint, so it is left out).
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

def _fontdir(fn):
    for d in ('~/Library/Fonts', '/Library/Fonts'):
        if os.path.exists(os.path.join(os.path.expanduser(d), fn)):
            return os.path.expanduser(d)
    return os.path.expanduser('~/Library/Fonts')
UF = _fontdir('NotoSerifSC-wght.ttf')
FAMILIES = {
    'serif': dict(label='思源宋体 Noto Serif SC', weights={
        'Light':    (os.path.join(UF, 'NotoSerifSC-wght.ttf'), 300, 'Noto Serif SC Light', False),
        'Regular':  (os.path.join(UF, 'NotoSerifSC-wght.ttf'), 400, 'Noto Serif SC', False),
        'Medium':   (os.path.join(UF, 'NotoSerifSC-wght.ttf'), 500, 'Noto Serif SC Medium', False),
        'SemiBold': (os.path.join(UF, 'NotoSerifSC-wght.ttf'), 600, 'Noto Serif SC SemiBold', False),
        'Bold':     (os.path.join(UF, 'NotoSerifSC-wght.ttf'), 700, 'Noto Serif SC', True),
        'Black':    (os.path.join(UF, 'NotoSerifSC-wght.ttf'), 900, 'Noto Serif SC Black', False),
    }),
    'sans': dict(label='思源黑体 Noto Sans CJK SC', weights={
        'Light':   (os.path.join(UF, 'NotoSansCJKsc-Light.otf'), None, 'Noto Sans CJK SC Light', False),
        'DemiLight': (os.path.join(UF, 'NotoSansCJKsc-DemiLight.otf'), None, 'Noto Sans CJK SC DemiLight', False),
        'Regular': (os.path.join(UF, 'NotoSansCJKsc-Regular.otf'), None, 'Noto Sans CJK SC', False),
        'Medium':  (os.path.join(UF, 'NotoSansCJKsc-Medium.otf'), None, 'Noto Sans CJK SC Medium', False),
        'Bold':    (os.path.join(UF, 'NotoSansCJKsc-Bold.otf'), None, 'Noto Sans CJK SC', True),
        'Black':   (os.path.join(UF, 'NotoSansCJKsc-Black.otf'), None, 'Noto Sans CJK SC Black', False),
    }),
}

def face_of(fam, w):
    f = FAMILIES[fam]['weights'][w]
    return f[2], f[3]

_cache = {}
def font(fam, w, px):
    k = (fam, w, int(round(px * 4)))
    if k not in _cache:
        path, wght, _, _ = FAMILIES[fam]['weights'][w]
        f = ImageFont.truetype(path, max(4, k[2] / 4.0))
        if wght is not None:
            f.set_variation_by_axes([wght])
        _cache[k] = f
    return _cache[k]

_rcache = {}
def render(text, fam, w, px, track=0.0, alpha=False, track_runs=None):
    if not alpha and track_runs is None and track == 0.0:
        k = (text, fam, w, round(px, 2))
        if k not in _rcache:
            if len(_rcache) > 20000: _rcache.clear()
            _rcache[k] = _render(text, fam, w, px)
        return _rcache[k]
    return _render(text, fam, w, px, track, alpha, track_runs)

def _render(text, fam, w, px, track=0.0, alpha=False, track_runs=None):
    """Lay out text char by char on a baseline (same model as PowerPoint: advance + spc after each char).
    Returns ink box relative to (origin, baseline), coverage, char cells; with alpha=True also the
    anti-aliased coverage image and its offset (ox, oy) from (origin, baseline)."""
    f = font(fam, w, px)
    pad = int(px * 1.5) + 12
    adv = [f.getlength(c) for c in text]
    width = int(sum(adv) + max(0.0, track) * max(0, len(text) - 1) + 2 * pad)
    Hh = int(px * 2.6) + 2 * pad
    im = Image.new('L', (max(width, 10), Hh), 0)
    d = ImageDraw.Draw(im)
    x = float(pad); base = pad + int(px * 1.5); cells = []
    for i, c in enumerate(text):
        d.text((x, base), c, font=f, fill=255, anchor='ls')
        cells.append((x - pad, x - pad + adv[i]))
        x += adv[i] + (track_runs[i] if track_runs else track)
    a = np.asarray(im)
    m = a > 127
    ys, xs = np.where(m.any(1))[0], np.where(m.any(0))[0]
    if not len(ys):
        return None
    x0, x1, y0, y1 = xs[0], xs[-1] + 1, ys[0], ys[-1] + 1
    out = dict(x0=x0 - pad, x1=x1 - pad, top=y0 - base, bot=y1 - base, cov=float(m[y0:y1, x0:x1].mean()), cells=cells,
               adv_total=x - pad)
    if alpha:
        out.update(alpha=a.astype(np.float32) / 255.0, ox=-pad, oy=-base)
    return out
