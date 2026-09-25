# -*- coding: utf-8 -*-
"""Proofreading sheet: every line that contains a character outside GB2312 level 1 (typical OCR misreads),
every line whose three OCR readings disagree, plus optional extra lines matching a regex. Each row: source crop above, recognised text below.
Usage: proof_sheet.py <workdir> <out_prefix> [regex]"""
import os, sys, json, re, difflib
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(1, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); import hostos as H
work, prefix = sys.argv[1], sys.argv[2]
extra = re.compile(sys.argv[3]) if len(sys.argv) > 3 else None
ALLOW = set(json.load(open(os.path.join(work, 'config.json'))).get('proof_allow', ''))
f = H.ui_font(30)
def level1(c):
    try: b = c.encode('gb2312')
    except Exception: return False
    return len(b) == 2 and 0xB0 <= b[0] <= 0xD7
man = json.load(open(os.path.join(work, 'manifest.json')))
rows = []
for pg in man['pages']:
    lj = os.path.join(work, '02_分层', pg['pid'], 'layers.json')
    if not os.path.exists(lj): continue
    L = json.load(open(lj)); img = None
    for p in L['paragraphs']:
        for l in p['lines']:
            t = l['text']
            bad = [c for c in t if '一' <= c <= '鿿' and not level1(c) and c not in ALLOW]
            Wd = lambda x: re.sub(r'[^\u4e00-\u9fffA-Za-z0-9]', '', x)
            fin = Wd(t)
            def substantive(r):
                # a reading disagrees in substance when it substitutes a character or has extra characters
                # inside the line; missing function words (的 …) and edge spill-over are not flagged
                a, b = fin, Wd(r)
                if not b or a == b:
                    return False
                for tag, a0, a1, b0, b1 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
                    if tag == 'replace':
                        return True
                    if tag == 'insert' and 0 < a0 < len(a):
                        return True
                    if tag == 'delete' and not set(a[a0:a1]) <= set('的了之地得'):
                        return True
                return False
            dis = [r for r in l.get('reads', []) + [l.get('ocr', '')] if substantive(r)]
            if bad or dis or (extra and extra.search(t)):
                img = img or Image.open(os.path.join(work, pg['image'])).convert('RGB')
                x0, y0, x1, y1 = l['ink']; h = y1 - y0
                c = img.crop((x0 - 10, y0 - 8, x1 + 10, y1 + 8))
                c = c.resize((max(1, int(c.width * 60 / c.height)), 60))
                rows.append((pg['pid'], t, ''.join(bad) + (' / '.join(dis)[:60] if dis else ''), c))
out = []
for k in range(0, len(rows), 14):
    chunk = rows[k:k + 14]
    W = max(1700, max(r[3].width for r in chunk) + 20)
    sheet = Image.new('RGB', (W, 116 * len(chunk)), 'white'); dr = ImageDraw.Draw(sheet)
    for j, (pid, t, bad, c) in enumerate(chunk):
        sheet.paste(c, (10, j * 116 + 4))
        dr.text((10, j * 116 + 68), '%s  %s' % (pid, t), fill=(200, 0, 0), font=f)
        dr.text((10 + int(f.getlength('%s  %s' % (pid, t))) + 30, j * 116 + 68), '[%s]' % bad, fill=(0, 90, 200), font=f)
    fn = '%s_%d.png' % (prefix, k // 14 + 1); sheet.save(fn); out.append(fn)
print(len(rows), 'lines'); print('\n'.join(out))
