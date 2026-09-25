# -*- coding: utf-8 -*-
"""One review image per page pair: layer overlay with a labelled grid in source pixels (every 320 px),
for reading off exclusion boxes. Usage: review_grid.py <workdir> <out.jpg> pidA [pidB]"""
import os, sys
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(1, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); import hostos as H
work, out = sys.argv[1], sys.argv[2]; pids = sys.argv[3:]
f = H.ui_font(26, bold=True)
tiles = []
for pid in pids:
    im = Image.open(os.path.join(work, '02_分层', pid, 'debug.jpg')).convert('RGB').resize((1600, 900))
    dr = ImageDraw.Draw(im); k = 1600 / 3840.0
    for v in range(0, 3841, 320):
        dr.line([(v * k, 0), (v * k, 900)], fill=(255, 0, 255), width=1)
        dr.text((v * k + 3, 2), str(v), fill=(255, 0, 255), font=f)
    for v in range(0, 2161, 320):
        dr.line([(0, v * k), (1600, v * k)], fill=(255, 0, 255), width=1)
        dr.text((3, v * k + 2), str(v), fill=(255, 0, 255), font=f)
    dr.rectangle([1480, 850, 1600, 900], fill='black'); dr.text((1490, 855), pid.upper(), fill='yellow', font=f)
    tiles.append(im)
sheet = Image.new('RGB', (1600, len(tiles) * 910), 'white')
for i, t in enumerate(tiles): sheet.paste(t, (0, i * 910))
sheet.save(out, quality=82)
