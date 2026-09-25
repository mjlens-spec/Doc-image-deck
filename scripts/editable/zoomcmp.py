# -*- coding: utf-8 -*-
"""QA helper: crop the same region from the source page and the PowerPoint render, stacked.
Usage: zoomcmp.py <workdir> <pdf> <page_index_in_pdf> <pid> x0 y0 x1 y1 <out.png>   (coords in source px)"""
import os, sys, subprocess
from PIL import Image
work, pdf, idx, pid = sys.argv[1:5]
x0, y0, x1, y1 = map(int, sys.argv[5:9]); out = sys.argv[9]
src = Image.open(os.path.join(work, '01_原图', pid + '.png')).convert('RGB')
W, H = src.size
tmp = os.path.join(work, 'tmp', 'zoom_%s' % idx)
if not os.path.exists(tmp + '.png') or os.path.getmtime(tmp + '.png') < os.path.getmtime(pdf):
    subprocess.run(['pdftoppm', '-png', '-f', idx, '-l', idx, '-singlefile', '-scale-to-x', str(W), '-scale-to-y', str(H), pdf, tmp], check=True)
ren = Image.open(tmp + '.png').convert('RGB')
a, b = src.crop((x0, y0, x1, y1)), ren.crop((x0, y0, x1, y1))
o = Image.new('RGB', (x1 - x0, 2 * (y1 - y0) + 6), 'red'); o.paste(a, (0, 0)); o.paste(b, (0, y1 - y0 + 6))
s = min(1.0, 1800.0 / (x1 - x0)); o = o.resize((int(o.width * s), int(o.height * s)), Image.LANCZOS)
o.save(out)
