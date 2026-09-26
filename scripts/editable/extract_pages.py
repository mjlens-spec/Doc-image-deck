# -*- coding: utf-8 -*-
"""Step 1 · Pull the full-bleed page image out of every slide.

Usage: extract_pages.py <deck.pptx | deck.pdf> <workdir>
Writes <workdir>/01_原图/pNN.png and <workdir>/manifest.json.
For a PPTX, the full-bleed picture (>= 97% of the slide) is the page to rebuild; every other
shape on the slide (logos, page numbers, pasted photos) is kept as-is and recorded by shape id.
For a PDF, the largest embedded image per page is used (falls back to a 2x render).
"""
import os, sys, io, json, subprocess, glob, shutil
from PIL import Image
sys.path.insert(1, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); import hostos as H

src, work = sys.argv[1], sys.argv[2]
out = os.path.join(work, '01_原图'); os.makedirs(out, exist_ok=True)
pages = []
if src.lower().endswith('.pptx'):
    from pptx import Presentation
    prs = Presentation(src)
    SW, SH = prs.slide_width, prs.slide_height
    for n, s in enumerate(prs.slides, 1):
        pid = 'p%02d' % n
        full, keep = None, []
        for sh in s.shapes:
            if full is None and sh.shape_type == 13 and sh.width * sh.height >= 0.97 * SW * SH:
                full = sh
            else:
                keep.append(dict(id=sh.shape_id, name=sh.name, type=str(sh.shape_type)))
        rec = dict(pid=pid, slide=n, keep=keep)
        if full is not None:
            im = Image.open(io.BytesIO(full.image.blob))
            fn = os.path.join(out, pid + '.png')
            if full.image.content_type == 'image/png' and im.mode == 'RGB':
                open(fn, 'wb').write(full.image.blob)
            else:
                im.convert('RGB').save(fn)
            rec.update(image=os.path.relpath(fn, work), size=list(im.size), bg_shape_id=full.shape_id,
                       box=[full.left, full.top, full.width, full.height])
        pages.append(rec)
        print(pid, rec.get('size'), 'keep:', [k['name'] for k in keep], flush=True)
    meta = dict(source=os.path.abspath(src), kind='pptx', slide_size=[SW, SH], pages=pages)
else:
    tmp = os.path.join(work, 'tmp', 'pdfimg'); os.makedirs(tmp, exist_ok=True)
    npages = H.pdf_page_count(src)
    for n in range(1, npages + 1):
        pid = 'p%02d' % n
        cands = H.pdf_page_images(src, n, tmp)
        fn = os.path.join(out, pid + '.png')
        im = cands[0] if cands else None
        if im is None or im.size[0] < 1600:
            H.render_pdf(src, fn[:-4], dpi=288, first=n, single=True)
            im = Image.open(fn)
        else:
            im.convert('RGB').save(fn)
        pages.append(dict(pid=pid, slide=n, image=os.path.relpath(fn, work), size=list(im.size), keep=[]))
        print(pid, im.size, flush=True)
    meta = dict(source=os.path.abspath(src), kind='pdf', slide_size=[12192000, 6858000], pages=pages)
st = os.stat(src)
meta['source_stat'] = [st.st_size, int(st.st_mtime)]      # run_editable.py re-extracts when the source changes
json.dump(meta, open(os.path.join(work, 'manifest.json'), 'w'), ensure_ascii=False, indent=1)
print('pages:', len(pages))
