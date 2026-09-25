# -*- coding: utf-8 -*-
"""Review sheets: images in a labelled grid.

Usage:
  contact_sheet.py <out.jpg> label=path [label=path ...] [--cols 2] [--width 900]
  contact_sheet.py <out_prefix> --raw <raw_dir> [--cols 3] [--per 12]      (selected version of every page)
"""
import os, sys, json, argparse
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hostos

def font(size):
    return hostos.ui_font(size, bold=True)

def sheet(items, out, cols, width, max_ratio=None):
    """Each tile: a label strip above the image, so the label never hides page content.
    max_ratio: images taller than width × max_ratio keep only their top part, so one long image does not stretch its row."""
    f = font(max(16, width // 32))
    strip = f.size + 14
    tiles = []
    for label, path in items:
        im = Image.open(path).convert('RGB')
        im = im.resize((width, int(im.height * width / im.width)), Image.LANCZOS)
        if max_ratio and im.height > width * max_ratio:
            im = im.crop((0, 0, width, int(width * max_ratio)))
        t = Image.new('RGB', (width, im.height + strip), (30, 30, 30))
        ImageDraw.Draw(t).text((8, 6), label, fill=(255, 220, 0), font=f)
        t.paste(im, (0, strip))
        tiles.append(t)
    th = max(t.height for t in tiles)
    rows = (len(tiles) + cols - 1) // cols
    s = Image.new('RGB', (cols * width + (cols + 1) * 12, rows * th + (rows + 1) * 12), (240, 240, 240))
    for i, t in enumerate(tiles):
        s.paste(t, (12 + (i % cols) * (width + 12), 12 + (i // cols) * (th + 12)))
    s.save(out, quality=85)
    print(out)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out'); ap.add_argument('items', nargs='*'); ap.add_argument('--raw', default='')
    ap.add_argument('--cols', type=int, default=2); ap.add_argument('--width', type=int, default=900); ap.add_argument('--per', type=int, default=12)
    a = ap.parse_args()
    if a.raw:
        sel = json.load(open(os.path.join(a.raw, 'selected.json'), encoding='utf-8'))
        items = [('%s  %s' % (pid.upper(), f), os.path.join(a.raw, f)) for pid, f in sorted(sel.items())]
        for k in range(0, len(items), a.per):
            sheet(items[k:k + a.per], '%s_%d.jpg' % (a.out, k // a.per + 1), a.cols, a.width)
    else:
        sheet([tuple(x.split('=', 1)) for x in a.items], a.out, a.cols, a.width)

if __name__ == '__main__':
    main()
