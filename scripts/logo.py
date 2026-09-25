# -*- coding: utf-8 -*-
"""Stage 2 · Build the logo files compose.py lays over every slide: one for light backgrounds, one for dark ones.

Usage: logo.py <project> <logo>[::<dark version>] [<logo> ...] [--corner bl] [--height 0.32] [--name 联合Logo]
               [--ink "#656565"]

Each logo is a file path (relative to the project or absolute); `a.png::a_white.png` gives the version for light
backgrounds and the one for dark backgrounds ("::" because a single colon is part of Windows paths). Several logos are joined left to right with a thin "×", scaled to the
same visual weight (equal square root of area), so a stacked two-line logo and a wide one look balanced.
When only one version exists it is derived: a white logo gets its white strokes recoloured to --ink for light
backgrounds; a dark logo gets its dark neutral strokes turned white for dark backgrounds. Coloured parts (brand marks,
dots, accents) keep their colour. Opaque files with a plain white or black background get that background removed.
Writes 00_Logo/<name>_浅底用_<suffix>.png, _深底用_ and 预览.png (both on light and dark grounds), and sets
project.json "logos" (relative paths). Look at 预览.png before composing: derived versions need a human check.
"""
import os, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deckenv as E

D_LOGO = '00_Logo'


def load(path):
    """RGBA logo trimmed to its visible pixels; a plain white or black background becomes transparent."""
    from PIL import Image
    im = Image.open(path).convert('RGBA')
    if im.getextrema()[3][0] == 255:                              # no transparency at all
        px = im.load()
        corners = [px[0, 0], px[im.width - 1, 0], px[0, im.height - 1], px[im.width - 1, im.height - 1]]
        bg = tuple(sorted(c[i] for c in corners)[1] for i in range(3))
        if min(bg) > 225 or max(bg) < 30:
            data = [(r, g, b, 0) if abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) < 60 else (r, g, b, a)
                    for r, g, b, a in pixels(im)]
            im.putdata(data)
    box = im.getchannel('A').point(lambda a: 255 if a > 16 else 0).getbbox()
    return im.crop(box) if box else im


def pixels(im):
    return list(getattr(im, 'get_flattened_data', im.getdata)())     # getdata is deprecated from Pillow 12


def neutral(r, g, b):
    return max(r, g, b) - min(r, g, b) < 30


def tone(im):
    """'white', 'dark' or 'colour': the brightness of the neutral (grey-scale) strokes of the logo."""
    px = pixels(im)
    lum = [0.299 * r + 0.587 * g + 0.114 * b for r, g, b, a in px if a > 128 and neutral(r, g, b)]
    if len(lum) < 0.3 * sum(1 for p in px if p[3] > 128):
        return 'colour'
    mean = sum(lum) / len(lum)
    return 'white' if mean > 200 else 'dark' if mean < 120 else 'colour'


def recolor(im, rgb, which):
    """Recolour neutral strokes: which='light' turns near-white strokes into rgb, 'dark' turns dark greys into rgb."""
    out = im.copy()
    data = []
    for r, g, b, a in pixels(im):
        hit = a and neutral(r, g, b) and (min(r, g, b) > 170 if which == 'light' else max(r, g, b) < 130)
        data.append(rgb + (a,) if hit else (r, g, b, a))
    out.putdata(data)
    return out


def versions(spec, proj, ink):
    """(for light backgrounds, for dark backgrounds, note) from 'a.png' or 'a.png::b.png'."""
    parts = [p if os.path.isabs(p) else os.path.join(proj, p) for p in spec.split('::') if p]
    for p in parts:
        if not os.path.exists(p):
            raise SystemExit('Logo 文件不存在：%s' % p)
    first = load(parts[0])
    if len(parts) > 1:
        return first, load(parts[1]), '提供了浅底、深底两个版本'
    t = tone(first)
    if t == 'white':
        return recolor(first, ink, 'light'), first, '只有反白版：浅底用版本由白色笔画改为 %s 生成' % ('#%02X%02X%02X' % ink)
    if t == 'dark':
        return first, recolor(first, (255, 255, 255), 'dark'), '只有深色版：深底用版本由深色笔画改为白色生成'
    return first, first, '彩色版，浅底、深底共用；深底上看不清时请提供反白版'


def lockup(logos, cross_rgb, height=360):
    """Join logos left to right with a thin ×; equal visual weight; the tallest is `height` px."""
    from PIL import Image, ImageDraw
    import math
    S = 4                                                         # draw at 4× and scale down for clean edges
    weight = [math.sqrt(im.width * im.height) for im in logos]
    scale = [min(weight) / w for w in weight]                     # equal square root of area
    tall = max(im.height * k for im, k in zip(logos, scale))
    f = height * S / tall
    ims = [im.resize((max(1, int(im.width * k * f)), max(1, int(im.height * k * f))), Image.LANCZOS) for im, k in zip(logos, scale)]
    H = max(im.height for im in ims)
    gap, cw = int(H * 0.19), int(H * 0.17)
    W = sum(im.width for im in ims) + (len(ims) - 1) * (2 * gap + cw)
    out = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    x = 0
    for i, im in enumerate(ims):
        out.alpha_composite(im, (x, (H - im.height) // 2))
        x += im.width
        if i < len(ims) - 1:
            cx, cy = x + gap, H // 2 - cw // 2
            lw = max(2, int(H * 0.017))
            d.line((cx, cy, cx + cw, cy + cw), fill=cross_rgb + (255,), width=lw)
            d.line((cx, cy + cw, cx + cw, cy), fill=cross_rgb + (255,), width=lw)
            x += 2 * gap + cw
    return out.resize((W // S, H // S), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project'); ap.add_argument('logos', nargs='+')
    ap.add_argument('--corner', default='bl', choices=['bl', 'br', 'tl', 'tr'])
    ap.add_argument('--height', type=float, default=0)
    ap.add_argument('--name', default='')
    ap.add_argument('--ink', default='#656565')
    a = ap.parse_args()
    from PIL import Image
    proj = os.path.abspath(a.project)
    cfg = E.load_project(proj)
    ink = tuple(int(a.ink.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))
    light, dark = [], []
    for spec in a.logos:
        lt, dk, note = versions(spec, proj, ink)
        light.append(lt); dark.append(dk)
        print('%s：%s' % (spec, note))
    name = a.name or ('联合Logo' if len(a.logos) > 1 else 'Logo')
    os.makedirs(os.path.join(proj, D_LOGO), exist_ok=True)
    rel = {}
    for tag, ims, cross in (('浅底用', light, (160, 160, 160)), ('深底用', dark, (200, 200, 200))):
        im = lockup(ims, cross)
        fn = '%s_%s_%s.png' % (name, tag, cfg['suffix'])
        im.save(os.path.join(proj, D_LOGO, fn))
        rel[tag] = '%s/%s' % (D_LOGO, fn)
    lt, dk = (Image.open(os.path.join(proj, rel[t])) for t in ('浅底用', '深底用'))
    pv = Image.new('RGBA', (lt.width + 60, lt.height * 2 + 90), (244, 247, 250, 255))
    pv.paste((12, 28, 48, 255), (0, lt.height + 45, pv.width, pv.height))
    pv.alpha_composite(lt, (30, 22)); pv.alpha_composite(dk, (30, lt.height + 67))
    pv.convert('RGB').save(os.path.join(proj, D_LOGO, '预览.png'))
    height = a.height or (0.32 if len(a.logos) > 1 else 0.26)
    E.update_project(proj, logos=[dict(name=name, light=rel['浅底用'], dark=rel['深底用'], corner=a.corner, height_in=height)])
    print('已写入 project.json：%s 角，高 %.2f 英寸，宽高比 %.2f' % (a.corner, height, lt.width / float(lt.height)))
    print('先看 %s/预览.png 确认深浅两个版本，再生成提示词（预留角落按 Logo 尺寸计算）。' % D_LOGO)


if __name__ == '__main__':
    main()
