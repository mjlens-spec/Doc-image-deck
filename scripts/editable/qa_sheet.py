# -*- coding: utf-8 -*-
"""Step 6 · Contact sheets for review: each row = source page | PowerPoint render of the editable slide.
Usage: qa_sheet.py <workdir> <deck.pdf> <out_prefix> [pages_per_sheet]
"""
import os, sys, glob, re, json, subprocess
sys.path.insert(1, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); import hostos as H
from PIL import Image, ImageDraw, ImageFont
work, pdf, prefix = sys.argv[1:4]
per = int(sys.argv[4]) if len(sys.argv) > 4 else 8
man = json.load(open(os.path.join(work, 'manifest.json')))
rd = os.path.join(work, 'tmp', 'sheet'); os.makedirs(rd, exist_ok=True)
for f in glob.glob(os.path.join(rd, 's-*.png')): os.remove(f)
H.render_pdf(pdf, os.path.join(rd, 's'), size=(960, 540))
rs = sorted(glob.glob(os.path.join(rd, 's-*.png')), key=lambda f: int(re.findall(r'-(\d+)\.png', f)[0]))
diff = {}
dj = os.path.join(work, '03_QA', 'diff.json')
if os.path.exists(dj):
    diff = json.load(open(dj)).get('diff', {})
lab = H.ui_font(22)
pages = man['pages']
outs = []
for k in range(0, len(pages), per):
    chunk = list(zip(pages[k:k + per], rs[k:k + per]))
    sheet = Image.new('RGB', (1940, len(chunk) * 560), 'white')
    for j, (pg, rp) in enumerate(chunk):
        a = Image.open(os.path.join(work, pg['image'])).convert('RGB').resize((960, 540), Image.LANCZOS)
        b = Image.open(rp).convert('RGB')
        sheet.paste(a, (0, j * 560)); sheet.paste(b, (980, j * 560))
        dr = ImageDraw.Draw(sheet)
        t = '%s  原图' % pg['pid'].upper(); t2 = '可编辑版（PowerPoint 渲染）'
        if pg['pid'] in diff:
            t2 += '  平均差 %.1f' % diff[pg['pid']]['mean']
        for x, tt in ((6, t), (986, t2)):
            dr.rectangle([x - 2, j * 560 + 4, x + 12 + 22 * len(tt) * 0.62, j * 560 + 34], fill=(255, 255, 255))
            dr.text((x + 4, j * 560 + 6), tt, fill=(200, 0, 0), font=lab)
    fn = '%s_%d.jpg' % (prefix, k // per + 1)
    sheet.save(fn, quality=82); outs.append(fn)
print('\n'.join(outs))
