# -*- coding: utf-8 -*-
"""OCR consensus for one page: every segment is re-read from its own crop at two scales and the three
readings (page, crop x1.0, crop x1.6) are merged character by character (2-of-3 majority).
Spaces and geometry always come from the page reading (its glyph boxes)."""
import os, re, json, difflib, subprocess, tempfile
from PIL import Image

EQUIV = {'–': '-', '—': '-', '－': '-', '·': '•', '。': '。', '，': '，', '：': '：'}
BULLETS = set('•·◆◇。●○')

def _k(c):
    return EQUIV.get(c, c)

def crop_readings(img, segs, ocr_bin, scales=(1.0, 1.6), pad_right=0.6):
    """Return, per segment, a list of crop readings (text only, spaces removed)."""
    tmp = tempfile.mkdtemp(prefix='ocrv_')
    jobs = []
    W, H = img.size
    for i, s in enumerate(segs):
        x0, y0, x1, y1 = s['box']; h = max(8, y1 - y0)
        pl, pr = s.get('pad_l', 0.6), s.get('pad_r', pad_right)
        box = (max(0, int(x0 - pl * h)), max(0, int(y0 - 0.45 * h)), min(W, int(x1 + pr * h)), min(H, int(y1 + 0.45 * h)))
        for sc in scales:
            c = img.crop(box)
            if sc != 1.0:
                c = c.resize((int(c.width * sc), int(c.height * sc)), Image.LANCZOS)
            fn = os.path.join(tmp, '%d_%.1f.png' % (i, sc)); c.save(fn, compress_level=1)
            # target band in crop coords
            jobs.append((i, fn, ((x0 - box[0]) * sc, (y0 - box[1]) * sc, (x1 - box[0]) * sc, (y1 - box[1]) * sc)))
    lst = os.path.join(tmp, 'list.txt'); open(lst, 'w').write('\n'.join(j[1] for j in jobs))
    out = subprocess.run([ocr_bin, '--batch', lst], capture_output=True, text=True).stdout
    res = json.loads(out or '{}')
    reads = [[] for _ in segs]
    for i, fn, (tx0, ty0, tx1, ty1) in jobs:
        lines = res.get(fn, [])
        th = ty1 - ty0
        picked = []
        for L in lines:
            ov = min(L['y1'], ty1) - max(L['y0'], ty0)
            if ov > 0.5 * min(th, L['y1'] - L['y0']) and L['x1'] > tx0 - 0.3 * th and L['x0'] < tx1 + 0.3 * th:
                picked.append(L)
        picked.sort(key=lambda L: L['x0'])
        reads[i].append(''.join(L['text'] for L in picked).replace(' ', ''))
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)
    return reads

DASHES = set('—–-~～·')
GAP = ' '          # placeholder for a glyph-wide gap where the page OCR probably dropped a character

def is_word(c):
    if '\u2460' <= c <= '\u24ff' or '\u2776' <= c <= '\u2793':      # circled numbers are badges, not words
        return False
    return c.isalnum() or '\u3400' <= c <= '\u9fff'

def vote(page_text, others):
    """Character-level 2-of-3 merge (page + two crop readings). Returns (text, changed).
    Accepts substitutions of letters/digits/CJK and insertions agreed by both crop readings; never
    deletes (Vision tends to drop characters such as 的) and never swaps punctuation. Spaces and
    glyph-gap placeholders of page_text are kept; a placeholder that receives an insertion disappears."""
    base = page_text.replace(' ', '').replace(GAP, '')
    others = [o for o in others if o]
    if len(others) < 2 or not base:
        return page_text.replace(GAP, ' '), False
    kb = [_k(c) for c in base]
    rep = [dict() for _ in base]; ins = [dict() for _ in range(len(base) + 1)]
    for o in others:
        o = o.replace(GAP, '')
        ko = [_k(c) for c in o]
        for tag, a0, a1, b0, b1 in difflib.SequenceMatcher(None, kb, ko, autojunk=False).get_opcodes():
            if tag == 'replace' and a1 - a0 == b1 - b0:
                for j in range(a1 - a0):
                    rep[a0 + j][o[b0 + j]] = rep[a0 + j].get(o[b0 + j], 0) + 1
            elif tag == 'insert' or (tag == 'replace' and b1 - b0 > a1 - a0):
                seg = o[b0:b1] if tag == 'insert' else None
                if tag == 'replace':            # e.g. page '眗' vs crop '的成': treat as substitution + insertion
                    continue
                ins[a0][seg] = ins[a0].get(seg, 0) + 1
    out = []; changed = False; bi = 0; used = set()
    def take_ins(pos, at_gap=False):
        nonlocal changed
        for sg, v in ins[pos].items():
            if v < 2 or pos in used:
                continue
            edge = pos == 0 or pos == len(base)
            if all(is_word(c) or c in DASHES for c in sg) and not (edge and any(c in DASHES for c in sg)) and (not edge or at_gap or len(sg) == 1):
                if out and out[-1] == ' ' and not at_gap:
                    out.pop()                   # the page OCR's space was the dropped glyph's gap
                out.append(sg); used.add(pos); changed = True
                return True
        return False
    for c in page_text:
        if c == ' ':
            out.append(' '); continue
        if c == GAP:
            if not take_ins(bi, at_gap=True):
                out.append(' ')
            continue
        take_ins(bi)
        v = rep[bi]
        alt = max(v, key=v.get) if v else c
        if v.get(alt, 0) >= 2 and _k(alt) != _k(c) and is_word(alt) and is_word(c):
            out.append(alt); changed = True
        else:
            out.append(c)
        bi += 1
    take_ins(bi)
    return ''.join(out), changed

ORNAMENT = set('J/+|\\✦✧◆◇*')
def strip_ornaments(text):
    """Drop decorative marks the OCR reads as characters at the ends of a line (swash 'J', sparkle '+', '/')."""
    t = text.strip()
    t = re.sub(r'(?<=[。！？」』])\s*[CcDd)）(（一—J+/]{1,2}$', '', t)      # moon / dash / swash after the last full stop
    while len(t) > 1 and t[-1] in ORNAMENT and (t[-2] in '。，！？」』）' or t[-2] == ' ' or ('\u3400' <= t[-2] <= '\u9fff' and t[-1] != '+')):
        t = t[:-1].rstrip()
    while len(t) > 1 and t[0] in ORNAMENT - {'+'} and (t[1] == ' ' or '㐀' <= t[1] <= '鿿'):
        t = t[1:].lstrip()
    return t
