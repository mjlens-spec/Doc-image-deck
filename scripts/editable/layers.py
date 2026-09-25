# -*- coding: utf-8 -*-
"""Step 3 · Reverse one page image into editable layers.

For every line of text: OCR box -> (optional) corpus correction -> fit font family (serif / sans),
weight, size, tracking, colour (per run, or a vertical gradient for foil type) and baseline, using
the same font outlines PowerPoint will use. Then paint the text out of the page with LaMa to get a
clean plate. Photos, icons, panels and ornaments stay in the plate.

Usage: layers.py <workdir> [pid ...]
Reads  <workdir>/manifest.json, 01_原图/<pid>.png, corpus.json (optional), config.json (optional)
Writes <workdir>/02_分层/<pid>/layers.json, plate.jpg, debug.jpg, preview.jpg
"""
import os, re, sys, json, subprocess, difflib, time
os.environ.setdefault('PYTORCH_MPS_HIGH_WATERMARK_RATIO', '0.4')   # keep LaMa's GPU memory bounded (16 GB machine, 2 workers)
os.environ.setdefault('PYTORCH_MPS_LOW_WATERMARK_RATIO', '0.25')
import numpy as np
import cv2
from PIL import Image, ImageFont, ImageDraw
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(1, os.path.dirname(HERE))
import hostos
from fonts import FAMILIES, font, render, face_of
from ocrvote import crop_readings, vote, strip_ornaments, GAP
from layers_spacing import char_layout

WORK = os.path.abspath(sys.argv[1])
CFG = json.load(open(os.path.join(WORK, 'config.json'))) if os.path.exists(os.path.join(WORK, 'config.json')) else {}
RUNTIME = hostos.RUNTIME
OCR_CMD = hostos.ocr_cmd(WORK)        # Apple Vision on macOS, RapidOCR on Windows (same JSON)
MIN_INK_H = CFG.get('min_ink_height_px', 18)          # at 3840 px page width; scaled to the page. Smaller text stays in the plate
MAX_BG_STD = CFG.get('max_background_std', 6.0)       # text over photos stays in the plate (ring texture, see texture_ring)

# ─────────────────────────────── OCR
def ocr(path):
    return json.loads(hostos.run_ocr([path], WORK) or '[]')

PUNCT_MAP = {'，': ',', '。': '.', '：': ':', '；': ';', '（': '(', '）': ')', '“': '"', '”': '"', '—': '-', '–': '-',
             '、': ',', '！': '!', '？': '?', '｜': '|', '／': '/', '丨': '|', '「': '"', '」': '"', '『': '"', '』': '"',
             '《': '"', '》': '"', '【': '(', '】': ')', '～': '~', '＋': '+', '％': '%', '×': 'X', '·': '', '•': ''}
def norm_map(s):
    out, idx = [], []
    for i, c in enumerate(s):
        c2 = PUNCT_MAP.get(c, c)
        if c2 == '' or c2.isspace() or c2 in '"\'.,;:!?()/|-~·' or not c2.isprintable():
            continue
        out.append(c2.upper()); idx.append(i)
    return ''.join(out), idx

def split_segments(L):
    """Cut an OCR line where the gap between glyphs is much wider than a glyph (table columns, split titles).
    Restore spaces the OCR dropped (gap clearly wider than the line's normal glyph gap) and en dashes.
    Each segment keeps `chars`: [(char, box or None)] aligned 1:1 with its text."""
    t, ch = L['text'], L.get('chars') or []
    h = L['y1'] - L['y0']
    if len(ch) != len(t):
        return [dict(text=t.strip(), box=[L['x0'], L['y0'], L['x1'], L['y1']], conf=L['conf'], chars=None)]
    items = [(c, b if len(b) == 4 else None) for c, b in zip(t, ch)]
    boxed = [(i, b) for i, (c, b) in enumerate(items) if b is not None and not c.isspace()]
    gaps = [boxed[k + 1][1][0] - boxed[k][1][2] for k in range(len(boxed) - 1)
            if not any(items[j][0].isspace() for j in range(boxed[k][0] + 1, boxed[k + 1][0]))]
    g0 = float(np.median(gaps)) if gaps else 0.0
    pieces, cur, last, last_i = [], [], None, None
    for i, (c, b) in enumerate(items):
        if c.isspace() or b is None:
            cur.append((c, None)); continue
        if c in '-－' and b[2] - b[0] > 0.42 * h:
            c = '–'
        if last is not None:
            gap = b[0] - last[2]
            if gap > 1.25 * h:
                pieces.append(cur); cur = []
            elif gap > g0 + 0.22 * h and not any(items[j][0].isspace() for j in range(last_i + 1, i)):
                cur.append((GAP if gap > g0 + 0.7 * h else ' ', None))
        cur.append((c, b)); last, last_i = b, i
    pieces.append(cur)
    out = []
    for p in pieces:
        while p and p[0][0].isspace(): p = p[1:]
        while p and p[-1][0].isspace(): p = p[:-1]
        bs = [b for _, b in p if b]
        if not p or not bs:
            continue
        out.append(dict(text=''.join(c for c, _ in p), box=[min(b[0] for b in bs), min(b[1] for b in bs),
                        max(b[2] for b in bs), max(b[3] for b in bs)], conf=L['conf'], chars=p))
    return out

OPENING = set('「『“‘（(《〈【')
SIGNS = set('+−-–—±~≈约')

# ─────────────────────────────── corpus correction
class Corpus:
    def __init__(self, segs):
        self.segs = segs
        self.norm = [norm_map(s) for s in segs]
        self.index = {}
        for k, (n, _) in enumerate(self.norm):
            for bg in set(n[i:i + 2] for i in range(len(n) - 1)):
                self.index.setdefault(bg, []).append(k)

    def match(self, raw, trust_digits=False):
        """Return (corrected_text, score, source) or None. Keeps OCR spacing; keeps the page digits unless trust_digits."""
        o, oidx = norm_map(raw)
        n = len(o)
        if n < 3:
            return None
        cnt = {}
        for bg in set(o[i:i + 2] for i in range(n - 1)):
            for k in self.index.get(bg, ()):
                cnt[k] = cnt.get(k, 0) + 1
        need = max(1, int(0.45 * (n - 1)))
        cands = sorted((k for k, c in cnt.items() if c >= need), key=lambda k: -cnt[k])[:40]
        best = None
        for k in cands:
            g, gidx = self.norm[k]
            sm = difflib.SequenceMatcher(None, o, g, autojunk=False)
            blocks = [b for b in sm.get_matching_blocks() if b.size]
            if not blocks:
                continue
            m = sum(b.size for b in blocks)
            g0, g1 = blocks[0].b, blocks[-1].b + blocks[-1].size
            o0, o1 = blocks[0].a, blocks[-1].a + blocks[-1].size
            score = m / float(max(n, g1 - g0))
            # unmatched OCR head/tail count against the match
            if o0 > 0 or o1 < n:
                score = m / float(max(n, g1 - g0) + (o0 + n - o1))
            if best is None or score > best[0]:
                best = (score, k, g0, g1, sm)
        if best is None:
            return None
        score, k, g0, g1, sm = best
        m_ = sum(b.size for b in sm.get_matching_blocks())
        one_sub = 4 <= n < 6 and g1 - g0 == n and m_ == n - 1       # short line, a single substituted glyph
        if score < (0.8 if n >= 6 else 0.999) and not one_sub:
            return None
        g, gidx = self.norm[k]
        seg = self.segs[k]
        span = seg[gidx[g0]: gidx[g1 - 1] + 1]
        if not trust_digits and re.findall(r'\d', span) != re.findall(r'\d', raw):   # digits: trust the page, not the draft
            return None
        craw = lambda b: seg[gidx[g0 + b]]                            # corpus char (original case / form)
        keep = [True] * len(raw); rep = {}; ins = {}
        for tag, a0, a1, b0, b1 in difflib.SequenceMatcher(None, o, g[g0:g1], autojunk=False).get_opcodes():
            if tag == 'equal':
                continue
            if tag == 'replace' and a1 - a0 == b1 - b0:
                for j in range(a1 - a0):
                    rep[oidx[a0 + j]] = craw(b0 + j)
                continue
            if tag == 'delete' and 0 < b0 < g1 - g0:
                between = seg[gidx[g0 + b0 - 1] + 1: gidx[g0 + b0]]      # corpus punctuation at this spot
                dash = [c for c in between if c in '—–-~～']
                if dash and all(raw[oidx[j]] in '一-—_' for j in range(a0, a1)):
                    for j in range(a0, a1):
                        rep[oidx[j]] = dash[min(j - a0, len(dash) - 1)]
                    continue
            if tag in ('replace', 'delete'):
                for j in range(a0, a1):
                    keep[oidx[j]] = False
            if tag in ('replace', 'insert'):
                pos = oidx[a0] if a0 < n else len(raw)
                ins[pos] = ins.get(pos, '') + ''.join(craw(b) for b in range(b0, b1))
        out = []
        for i, c in enumerate(raw):
            if ins.get(i) and out and out[-1] in (GAP, ' ') and i > 0 and raw[i - 1] == GAP:
                out.pop()                       # the gap was the missing glyph
            out.append(ins.get(i, ''))
            if keep[i]:
                out.append(rep.get(i, c))
        out.append(ins.get(len(raw), ''))
        txt = ''.join(out).strip()
        # verbatim corpus span: widen by the OCR characters left unmatched at either end (a misread first or
        # last glyph), then over adjacent punctuation (closing marks forward; opening marks and signs backward)
        blocks = [b for b in sm.get_matching_blocks() if b.size]
        o0, o1 = blocks[0].a, blocks[-1].a + blocks[-1].size
        ge0 = max(0, g0 - o0); ge1 = min(len(g), g1 + (n - o1))
        a_ = gidx[ge0]; b_ = gidx[ge1 - 1] + 1
        while b_ < len(seg) and not norm_map(seg[b_])[0] and seg[b_] not in OPENING and not seg[b_].isspace():
            b_ += 1
        while a_ > 0 and (seg[a_ - 1] in OPENING or seg[a_ - 1] in SIGNS):
            a_ -= 1
        self.last_span = seg[a_:b_].strip()
        return txt, score, seg, [i for i in range(len(raw)) if keep[i]]

def split_by_height(img, seg, manual=()):
    """A label and its value on one OCR line often differ in size (大号标签 + 小号说明). Find a gap where the
    glyph height changes by more than 25% and split the segment there. Returns a list of segments."""
    if not seg.get('chars') or len(seg['text'].replace(' ', '')) < 4:
        return [seg]
    for mx, my in manual:                                  # reviewer-given split point [x, y] in page pixels
        if seg['box'][0] < mx < seg['box'][2] and seg['box'][1] <= my <= seg['box'][3]:
            return [dict(seg, split_x=float(mx))]
    H, W, _ = img.shape
    x0, y0, x1, y1 = [int(round(v)) for v in seg['box']]
    h = max(8, y1 - y0)
    X0, Y0, X1, Y1 = max(0, x0 - 4), max(0, y0 - 2), min(W, x1 + 4), min(H, y1 + 2)
    crop = img[Y0:Y1, X0:X1]
    bg = local_bg(crop, h)
    d = np.sqrt(((crop.astype(np.float32) - bg.astype(np.float32)) ** 2).sum(-1))
    ink = d > max(14, 0.33 * np.percentile(d, 99.5))
    cols = ink.any(0); cr, st = [], None
    for i, v in enumerate(list(cols) + [False]):
        if v and st is None: st = i
        if not v and st is not None: cr.append((st, i)); st = None
    if len(cr) < 5:
        return [seg]
    hts = []
    for a, b in cr:
        r = np.where(ink[:, a:b].any(1))[0]
        hts.append(r[-1] - r[0] + 1 if len(r) else 0)
    gaps_all = [cr[i][0] - cr[i - 1][1] for i in range(1, len(cr))]
    g75 = float(np.percentile(gaps_all, 75)) if gaps_all else 0.0
    best = None
    for k in range(2, len(cr) - 1):
        gap = cr[k][0] - cr[k - 1][1]
        if gap < 1.5 * g75:
            continue
        hl = float(max(hts[max(0, k - 2):k])); hr = float(max(hts[k:k + 2]))
        if min(hl, hr) <= 0 or gap < 0.12 * min(hl, hr):
            continue
        # the glyphs next to the gap must look like the rest of their side (a size change, not one tall glyph)
        hl2 = float(np.median(sorted(hts[:k])[-3:])); hr2 = float(np.median(sorted(hts[k:])[-3:]))
        ratio = max(hl, hr) / min(hl, hr)
        if ratio > 1.3 and max(hl2, hr2) / max(1.0, min(hl2, hr2)) > 1.2 and hl >= 0.85 * hl2 and hr >= 0.85 * hr2 \
                and (hl > hr) == (hl2 > hr2) and (best is None or ratio * gap > best[0]):
            best = (ratio * gap, k)
    if best is None:
        return [seg]
    _, k = best
    xs = X0 + (cr[k - 1][1] + cr[k][0]) / 2.0
    return [dict(seg, split_x=xs)]

def apply_height_splits(img, segs):
    """Resolve pending height splits: OCR the left part on its own and cut the text where its reading ends."""
    pend = [s for s in segs if 'split_x' in s]
    if not pend:
        return segs
    lefts = [dict(box=[s['box'][0], s['box'][1], s['split_x'], s['box'][3]]) for s in pend]
    reads = crop_readings(Image.fromarray(img), lefts, OCR_CMD, scales=(1.0,), pad_right=0.03)
    out = []
    for s in segs:
        if 'split_x' not in s:
            out.append(s); continue
        rd = reads[pend.index(s)]
        lt = norm_map(rd[0] if rd else '')[0]
        chars = s['chars']; xs = s.pop('split_x')
        best = None
        for i in range(1, len(chars)):
            pre = norm_map(''.join(c for c, _ in chars[:i]))[0]
            if not pre:
                continue
            sc = difflib.SequenceMatcher(None, pre, lt, autojunk=False).ratio()
            sc += 0.02 if chars[i][0].isspace() or chars[i - 1][0].isspace() or chars[i][0] in '|｜' else 0
            if best is None or sc > best[0]:
                best = (sc, i)
        if not lt or best is None or best[0] < 0.6:
            out.append(s); continue
        idx = best[1]
        while idx < len(chars) - 1 and (chars[idx][0] in '—–-、，。：；！？」』）…·' or chars[idx][0].isspace()):
            idx += 1                                    # trailing punctuation stays with the left part
        parts = []
        for part, bx in ((chars[:idx], (s['box'][0], xs)), (chars[idx:], (xs, s['box'][2]))):
            while part and (part[0][0].isspace() or part[0][0] in '|｜'): part = part[1:]
            while part and (part[-1][0].isspace() or part[-1][0] in '|｜'): part = part[:-1]
            if part:
                parts.append(dict(text=''.join(c for c, _ in part), box=[bx[0], s['box'][1], bx[1], s['box'][3]],
                                  conf=s['conf'], chars=part, split='height', **({'pad_r': 0.03} if not parts else {'pad_l': 0.03})))
        ok = len(parts) == 2 and all(len(norm_map(q['text'])[0]) >= 2 for q in parts)
        out += parts if ok else [s]
    return out

def disputed_positions(text, reads):
    """Indices of text (excluding spaces) where at least one crop reading disagrees (substitution / missing)."""
    idx = [i for i, c in enumerate(text) if not c.isspace()]
    base = ''.join(text[i] for i in idx)
    out = set()
    for r in reads:
        r = re.sub(r'\s', '', r)
        if not r:
            continue
        for tag, a0, a1, b0, b1 in difflib.SequenceMatcher(None, base, r, autojunk=False).get_opcodes():
            if tag in ('replace', 'delete'):
                out.update(idx[a0:a1])
    return out

FUNCTION_CHARS = set('的了之地得')
def filter_corpus(text, corrected, reads):
    """Keep only the corpus edits the page cannot contradict: substitutions / deletions at positions the
    OCR readings disagree on, and insertions of function characters Vision tends to drop (的 …).
    Returns (text, rejected_diffs)."""
    if not reads:
        return corrected, []
    dis = disputed_positions(text, reads)
    out, rejected = [], []
    for tag, a0, a1, b0, b1 in difflib.SequenceMatcher(None, text, corrected, autojunk=False).get_opcodes():
        seg_a, seg_b = text[a0:a1], corrected[b0:b1]
        if tag == 'equal':
            out.append(seg_a); continue
        if tag == 'insert':
            ok = set(seg_b) <= FUNCTION_CHARS and len(seg_b) <= 2
        else:
            ok = all(i in dis for i in range(a0, a1) if not text[i].isspace())
            if tag == 'replace' and len(seg_b) > len(seg_a) and not ok:
                ok = False
        if ok:
            out.append(seg_b)
        else:
            out.append(seg_a)
            rejected.append(dict(page=seg_a, draft=seg_b))
    t = ''.join(out)
    # a function word inserted right after an opening quote belongs before it: 自己「的好运」 -> 自己的「好运」
    t = re.sub(r'([「『“《（])([的了之地得])', r'\2\1', t)
    return t, rejected

def strip_icon_prefix(text, reads):
    """Remove a short leading token (icon read as 'Q', 'A', '苗', '0', ')', 'D）') that both crop readings lack."""
    rs = [re.sub(r'\s', '', r) for r in reads if r and r.strip()]
    if len(rs) < 2:
        return text
    for k in range(1, min(7, len(text))):
        pre, rest = text[:k], text[k:].lstrip()
        pre_ns = pre.replace(' ', '')
        if not pre_ns or len(pre_ns) > 3 or len(rest) < 3:
            continue
        if not (text[k:k + 1] == ' ' or '一' <= text[k:k + 1] <= '鿿' or text[k - 1] in ')）'):
            continue
        key = re.sub(r'\s', '', rest)[:4]
        if all(0 <= r.find(key) <= 1 and not r.startswith(pre_ns) for r in rs):
            return rest
    return text

def strip_icon_suffix(text, reads):
    """Remove a short trailing token (swash, moon, sparkle) that the crop readings do not end with."""
    m = re.search(r'(?<=[一-鿿])\s*[（(][A-Za-z0-9（(\s]{0,4}$', text)
    if m and m.start() > 2:
        return text[:m.start()].rstrip()
    m = re.search(r'\s(\S{1,2})$', text)
    rs = [re.sub(r'\s', '', r) for r in reads if r and r.strip()]
    if m and len(rs) >= 2 and not re.match(r'[一-鿿%]', m.group(1)):
        rest = text[:m.start()]
        key = re.sub(r'\s', '', rest)[-3:]
        if all(r.rfind(key) >= len(r) - len(key) - 1 and not r.endswith(m.group(1)) for r in rs):
            return rest.rstrip()
    return text

CIRCLED = set('⓪①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳❶❷❸❹❺❻❼❽❾❿➀➁➂➃➄➅➆➇➈➉➊➋➌➍➎➏➐➑➒➓')
LEAD_SYMBOLS = set('•·●○◎◉◆◇▪■□★☆✦✧→►▶◀♦❖⊙®©') | CIRCLED

class CorpusSet:
    """corpus.json is either a list of draft segments (reference only: edits limited to disputed characters),
    or {"authoritative": true, "_pages": {pid: [strings]}, "_all": [...]}, built from the whiteboard outline:
    the page's own copy is the intended text and replaces the OCR reading whenever it matches."""
    def __init__(self, data):
        if isinstance(data, list):
            self.all, self.pages, self.auth = Corpus(data), {}, False
        else:
            self.all = Corpus(data.get('_all', [])) if data.get('_all') else None
            self.pages = {k: Corpus(v) for k, v in data.get('_pages', {}).items()}
            self.auth = bool(data.get('authoritative')) or bool(CFG.get('corpus_authoritative'))

    def match(self, pid, text):
        """-> (match tuple or None, authoritative?)"""
        pc = self.pages.get(pid)
        if pc is not None:
            m = pc.match(text, trust_digits=self.auth)
            if m:
                if self.auth:                          # the page copy is exact: take it verbatim, punctuation and spaces included
                    m = (pc.last_span, m[1], m[2], m[3])
                return m, self.auth
        if self.all is not None:
            return self.all.match(text), False
        return None, False

# ─────────────────────────────── per-line fitting
def cdist(img, c):
    return np.sqrt(((img.astype(np.float32) - np.asarray(c, np.float32)) ** 2).sum(-1))

def local_bg(crop, h):
    k = int(max(5, h * 0.9)) | 1
    small = crop
    bg = np.stack([cv2.medianBlur(np.ascontiguousarray(small[..., i]), min(k, 255) if k <= 255 else 255) for i in range(3)], -1)
    return bg

def is_cjk(c):
    return '㐀' <= c <= '鿿' or '　' <= c <= '〿' or '＀' <= c <= '￯' or c in '“”‘’'

def run_integrals(mask, soft, axis):
    """For every run of `mask` along rows (axis=1) or columns (axis=0): integral of `soft` over the run, run length."""
    m = mask if axis == 1 else mask.T; sm = soft if axis == 1 else soft.T
    x = np.diff(np.pad(m.astype(np.int8), ((0, 0), (1, 1))), axis=1)
    cs = np.pad(np.cumsum(sm, axis=1), ((0, 0), (1, 0)))
    r, c = np.where(x == 1); r2, c2 = np.where(x == -1)
    return cs[r2, c2] - cs[r, c], c2 - c

def stem_peak(d, em):
    """Typical full ink contrast: median of the peak value across vertical stems."""
    pos = d[d > 0]
    if not len(pos):
        return 1.0
    b = (d > 0.3 * np.percentile(pos, 99)).astype(np.uint8)
    Vm = cv2.morphologyEx(b, cv2.MORPH_OPEN, np.ones((max(3, int(0.25 * em)), 1), np.uint8)).astype(bool)
    x = np.diff(np.pad(Vm.astype(np.int8), ((0, 0), (1, 1))), axis=1)
    r, c = np.where(x == 1); r2, c2 = np.where(x == -1)
    pk = [d[a, b0:b1].max() for a, b0, b1 in zip(r, c, c2) if b1 - b0 < 0.2 * em]
    return float(np.median(pk)) if len(pk) >= 5 else float(np.percentile(pos, 99))

def stroke_sig(o, em):
    """Blur-invariant stroke signature of a soft ink map o (0..1, 1 = full ink contrast):
    (horizontal-stroke thickness, vertical-stroke thickness), each the median ink integral across the
    stroke. Horizontal bars are isolated with a horizontal opening, vertical stems with a vertical one.
    Serif CJK type: thin horizontals, thick stems (ratio ~0.3-0.5); sans: ratio ~0.85-1."""
    b = (o > 0.3).astype(np.uint8)
    L = max(3, int(0.25 * em))
    Hm = cv2.morphologyEx(b, cv2.MORPH_OPEN, np.ones((1, L), np.uint8)).astype(bool)
    Vm = cv2.morphologyEx(b, cv2.MORPH_OPEN, np.ones((L, 1), np.uint8)).astype(bool)
    ih, lh = run_integrals(Hm, o, 0); iv, lv = run_integrals(Vm, o, 1)
    ih = ih[lh < 0.2 * em]; iv = iv[lv < 0.2 * em]
    if len(ih) < 5 or len(iv) < 5:
        return None
    return float(np.median(ih)), float(np.median(iv))

_ls_cache = {}
def texture_ring(img, box):
    key = id(img)
    if key not in _ls_cache:
        _ls_cache.clear()
        g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(np.float32)
        m = cv2.blur(g, (5, 5)); m2 = cv2.blur(g * g, (5, 5))
        _ls_cache[key] = np.sqrt(np.maximum(0, m2 - m * m))
    ls = _ls_cache[key]
    x0, y0, x1, y1 = [int(v) for v in box]; h = max(8, y1 - y0)
    X0, Y0, X1, Y1 = max(0, x0 - h // 2), max(0, y0 - h // 2), min(ls.shape[1], x1 + h // 2), min(ls.shape[0], y1 + h // 2)
    ring = np.ones((Y1 - Y0, X1 - X0), bool); ring[max(0, y0 - Y0):y1 - Y0, max(0, x0 - X0):x1 - X0] = False
    return float(np.median(ls[Y0:Y1, X0:X1][ring])) if ring.any() else 0.0

def cls(c):
    if '㐀' <= c <= '鿿': return 'C'
    if c.isascii() and (c.isalnum() or c in '%+'): return 'L'
    return 'P'

CLOSE_PUNCT = set('，。、：；！？」』）》〉】”’')
OPEN_PUNCT = set('「『（《〈【“‘')

def punct_slots(text):
    """Gaps (after character i) that shrink when full-width punctuation is set compressed (标点挤压):
    after a closing / middle mark, and before an opening mark. The gap after the last character never counts."""
    n = len(text)
    return [i for i in range(n - 1) if text[i] in CLOSE_PUNCT or text[i + 1] in OPEN_PUNCT]

def spaced_track(text, fam, w, px, wm, extra, pq=0.0):
    """Uniform tracking that makes the line as wide as the ink, given the extra width of each space and the
    (negative) extra of each compressed punctuation gap."""
    rw = render(text, fam, w, px)
    if rw is None:
        return None
    n = len(text); ns = text.count(' ')
    return (wm - (rw['x1'] - rw['x0']) - extra * ns - pq * len(punct_slots(text))) / max(1, n - 1)

def track_list(text, track, extra, pq=0.0):
    slots = set(punct_slots(text)) if pq else ()
    return [track + (extra if c == ' ' else 0.0) + (pq if i in slots else 0.0) for i, c in enumerate(text)]

def fit_spacing(text, fam, w, px, occ, exact=False):
    """Choose which CJK/Latin boundaries carry a space, and how wide spaces are, by comparing the
    column occupancy of the rendered line with the page. Returns (text, track, space_extra)."""
    wm = len(occ)
    def score(t, e, q=0.0):
        tr = spaced_track(t, fam, w, px, wm, e, q)
        if tr is None: return -1, 0
        rt = render(t, fam, w, px, 0, alpha=True, track_runs=track_list(t, tr, e, q))
        cols = (rt['alpha'] > 0.5).any(0)
        xs = np.where(cols)[0]
        if not len(xs): return -1, tr
        cols = cols[xs[0]:xs[0] + wm]
        if len(cols) < wm: cols = np.pad(cols, (0, wm - len(cols)))
        inter = (cols & occ).sum(); uni = (cols | occ).sum()
        return inter / max(1, uni), tr
    grid = [-0.2, -0.1, 0.0, 0.15, 0.3, 0.5, 0.75] if exact else [0.0, 0.15, 0.3, 0.5, 0.75]
    def best_e(t):
        if ' ' not in t:
            sc, tr = score(t, 0.0); return sc, tr, 0.0
        res = [(score(t, g * px), g * px) for g in grid]
        (sc, tr), e = max(res, key=lambda r: r[0][0])
        return sc, tr, e
    def climb(t):
        ts = best_e(t)
        while True:
            opts = []
            for i in range(1, len(t)):
                if t[i] != ' ' and t[i - 1] != ' ' and {cls(t[i - 1]), cls(t[i])} == {'C', 'L'}:
                    opts.append(t[:i] + ' ' + t[i:])
            for i, c in enumerate(t):
                if c == ' ':
                    opts.append(t[:i] + t[i + 1:])
            best = None
            for t2 in opts:
                s2 = best_e(t2)
                if s2[0] > ts[0] + 0.003 and (best is None or s2[0] > best[1][0]):
                    best = (t2, s2)
            if best is None:
                return t, ts
            t, ts = best
    if exact:                                      # known text: keep its spaces, fit only their width
        climb = lambda t: (t, best_e(t))
    starts = [text]
    allsp = ''.join((' ' + c) if i and text[i - 1] != ' ' and c != ' ' and {cls(text[i - 1]), cls(c)} == {'C', 'L'} else c
                    for i, c in enumerate(text))
    if allsp != text and not exact:
        starts.append(allsp)
    cur, cur_s = max((climb(t) for t in starts), key=lambda r: r[1][0])
    sc, tr, e = cur_s
    q = 0.0
    slots = punct_slots(cur)
    if slots:
        # compressed punctuation: when every glyph is a separate ink run on both sides, measure the gap after
        # each punctuation mark directly and move only those gaps (column overlap barely sees them)
        def runs_of(cols):
            r_, st_ = [], None
            for i_, v_ in enumerate(list(cols) + [False]):
                if v_ and st_ is None: st_ = i_
                if not v_ and st_ is not None: r_.append((st_, i_)); st_ = None
            return r_
        vis = [i for i, c in enumerate(cur) if not c.isspace()]
        ri = runs_of(occ)
        while len(ri) > len(vis):                   # glyphs split into several runs (却, 川): merge the tightest pair
            cand_ = [(ri[k + 1][0] - ri[k][1], k) for k in range(len(ri) - 1) if ri[k + 1][1] - ri[k][0] <= 1.15 * px]
            if not cand_:
                break
            _, k = min(cand_)
            ri[k:k + 2] = [(ri[k][0], ri[k + 1][1])]
        glyph = {c: render(c, fam, w, px) for c in set(cur) if not c.isspace()}
        for _ in range(2):
            if len(ri) != len(vis) or any(glyph[cur[i]] is None for i in vis):
                break
            # rendered ink span of every character, from its cell and its own ink box
            rt_ = render(cur, fam, w, px, 0, track_runs=track_list(cur, tr, e, q))
            spans = [(rt_['cells'][i][0] + glyph[cur[i]]['x0'], rt_['cells'][i][0] + glyph[cur[i]]['x1']) for i in vis]
            off = spans[0][0]
            rr = [(a - off, b - off) for a, b in spans]
            pos = {ci: k for k, ci in enumerate(vis)}
            deltas = []
            for i in slots:
                a, b = pos.get(i), pos.get(i + 1)
                if a is None or b is None:
                    continue
                deltas.append((ri[b][0] - ri[a][1]) - (rr[b][0] - rr[a][1]))
            if not deltas:
                break
            q = float(np.clip(q + np.median(deltas), -0.6 * px, 0.0))
            t2 = spaced_track(cur, fam, w, px, wm, e, q)
            if t2 is None:
                break
            tr = t2
        s2, t2 = score(cur, e, q)
        if q and s2 >= sc - 0.03:                   # direct measurement wins unless the overall fit clearly breaks
            sc, tr = s2, t2
        else:
            q = 0.0
            for qq in (-0.15, -0.3, -0.45):            # fallback when glyphs touch: best column overlap
                s2, t2 = score(cur, e, qq * px)
                if s2 > sc + 0.003:
                    sc, tr, q = s2, t2, qq * px
    return cur, tr, e, sc, q

def fit_segment(img, seg, W, H, families):
    x0, y0, x1, y1 = seg['box']
    if seg.get('keep_boxes'):
        kb = seg['keep_boxes']
        x0, x1 = min(b[0] for b in kb), max(b[2] for b in kb)
    h = y1 - y0
    pad = int(0.35 * h) + 4
    X0, Y0, X1, Y1 = max(0, int(x0) - pad), max(0, int(y0) - pad), min(W, int(np.ceil(x1)) + pad), min(H, int(np.ceil(y1)) + pad)
    crop = img[Y0:Y1, X0:X1]
    bg = local_bg(crop, h)
    d = np.sqrt(((crop.astype(np.float32) - bg.astype(np.float32)) ** 2).sum(-1))
    d_loc = d
    # flat panel or banner: the local median is pulled toward the text colour when text fills the panel,
    # so use one background colour for the line when the non-text pixels around it are uniform
    box_m = np.zeros(d.shape, bool)
    box_m[max(0, int(y0) - Y0):int(np.ceil(y1)) - Y0, max(0, int(x0) - X0):int(np.ceil(x1)) - X0] = True
    pre_ink = d > max(14, 0.33 * np.percentile(d[box_m], 99.5))
    bgpix = crop[box_m & ~ndi.binary_dilation(pre_ink, iterations=max(2, int(0.06 * h)))]
    if len(bgpix) > 50:
        c0 = np.median(bgpix, 0)
        mad = float(np.median(np.abs(bgpix.astype(np.float32) - c0).max(-1)))
        if mad < 10:
            d = np.sqrt(((crop.astype(np.float32) - c0.astype(np.float32)) ** 2).sum(-1))
            bg = np.broadcast_to(c0.astype(crop.dtype), crop.shape)
    # restrict to the OCR glyph boxes (+ a little) so neighbouring icons / rules / ornaments are not taken as ink
    lim = np.zeros_like(d, bool)
    mx = int(0.12 * h) + 2; my = int(0.07 * h) + 2
    lim[max(0, int(y0) - Y0 - (0 if seg.get('cut_top') else my)): int(np.ceil(y1)) - Y0 + (0 if seg.get('cut_bottom') else my),
        max(0, int(x0) - X0 - mx): int(np.ceil(x1)) - X0 + mx] = True
    dmax = np.percentile(d[lim], 99.5)
    if dmax < 22:
        return None, 'low-contrast'
    ink = (d > max(14, 0.33 * dmax)) & lim
    rows = ink.any(1)
    runs, st = [], None
    for i, v in enumerate(list(rows) + [False]):
        if v and st is None: st = i
        if not v and st is not None: runs.append((st, i)); st = None
    oy0, oy1 = y0 - Y0, y1 - Y0
    if runs:
        oc = (oy0 + oy1) / 2.0
        best = max(runs, key=lambda ab: (ab[0] <= oc <= ab[1], (ab[1] - ab[0]) * (min(ab[1], oy1) - max(ab[0], oy0) > 0)))
        bh = best[1] - best[0]
        lrows = np.where(lim.any(1))[0]; lo_l, hi_l = lrows[0], lrows[-1] + 1
        keep = [ab for ab in runs if ab == best or ((ab[1] - ab[0]) < 0.3 * bh and min(abs(ab[0] - best[1]), abs(best[0] - ab[1])) < 0.25 * bh
                                                     and ab[0] > lo_l and ab[1] < hi_l)]
        if bh < 0.35 * h:                            # centre fell on a thin run: take all overlapping runs
            keep = [ab for ab in runs if (min(ab[1], oy1) - max(ab[0], oy0)) > 0.5 * (ab[1] - ab[0])]
        lo, hi = min(a for a, b in keep), max(b for a, b in keep)
        ink[:lo] = False; ink[hi:] = False
    ys, xs = np.where(ink.any(1))[0], np.where(ink.any(0))[0]
    if len(ys) < 3 or len(xs) < 3:
        return None, 'no-ink'
    # underline swooshes / rules touching the band: wide, flat components at the top or bottom edge
    hb = ys[-1] + 1 - ys[0]
    lab_, nlab = ndi.label(ink)
    for i_, sl_ in enumerate(ndi.find_objects(lab_), 1):
        ch_, cw_ = sl_[0].stop - sl_[0].start, sl_[1].stop - sl_[1].start
        cy_ = (sl_[0].start + sl_[0].stop) / 2.0
        if cw_ > 1.6 * hb and ch_ < 0.3 * hb and (cy_ > ys[0] + 0.7 * hb or cy_ < ys[0] + 0.3 * hb):
            ink[sl_][lab_[sl_] == i_] = False
    ys, xs = np.where(ink.any(1))[0], np.where(ink.any(0))[0]
    if len(ys) < 3 or len(xs) < 3:
        return None, 'no-ink'
    # CJK lines have no descenders: rows at the band edges whose ink covers only a small part of the line
    # width belong to an underline swoosh / ornament, not to the glyphs
    txt_ = seg['text']
    if sum(1 for c in txt_ if '\u4e00' <= c <= '\u9fff') >= max(4, 0.5 * len(txt_.replace(' ', ''))):
        hb = ys[-1] + 1 - ys[0]; binw = max(4, int(0.6 * hb))
        nb = max(1, (xs[-1] + 1 - xs[0]) // binw)
        if nb >= 5:
            occ_ = np.zeros((ink.shape[0], nb), bool)
            for b_ in range(nb):
                occ_[:, b_] = ink[:, xs[0] + b_ * binw: xs[0] + (b_ + 1) * binw].any(1)
            cov_ = occ_.mean(1)
            top, bot = ys[0], ys[-1] + 1
            while bot - 1 > top and cov_[bot - 1] < 0.35 and (ys[-1] + 1 - (bot - 1)) < 0.35 * hb:
                bot -= 1
            while top + 1 < bot and cov_[top] < 0.35 and (top + 1 - ys[0]) < 0.35 * hb:
                top += 1
            # in the sparse edge zones, drop only wide components (swooshes, rules); narrow ones are stroke
            # tips that reach below / above the others (平, 却) and belong to the glyphs
            changed = False
            for z0, z1 in ((bot, ys[-1] + 1), (ys[0], top)):
                if z1 <= z0:
                    continue
                zone = np.zeros_like(ink); zone[z0:z1] = ink[z0:z1]
                lab_z, nz = ndi.label(zone, structure=np.ones((3, 3)))
                for k_, sl_ in enumerate(ndi.find_objects(lab_z), 1):
                    if sl_ is not None and sl_[1].stop - sl_[1].start > 1.2 * hb:
                        ink[sl_][lab_z[sl_] == k_] = False; changed = True
            if changed:
                ys, xs = np.where(ink.any(1))[0], np.where(ink.any(0))[0]
    iy0, iy1, ix0, ix1 = ys[0], ys[-1] + 1, xs[0], xs[-1] + 1
    cols = ink.any(0); cr, st = [], None
    for i, v in enumerate(list(cols) + [False]):
        if v and st is None: st = i
        if not v and st is not None: cr.append((st, i)); st = None
    bh_ = iy1 - iy0
    if len(cr) > 1 and seg['text'][:1] not in '「『“（(《【':
        a_, b_ = cr[0]
        rows_ = np.where(ink[:, a_:b_].any(1))[0]
        if (b_ - a_) < 0.45 * bh_ and len(rows_) and (rows_[-1] - rows_[0]) < 0.5 * bh_ and cr[1][0] - b_ > 0.15 * bh_ \
                and seg['text'][:1] not in '一二三丶、，。．-—–_~…':
            ink[:, a_:b_] = False
            xs = np.where(ink.any(0))[0]; ix0 = xs[0]
    if len(cr) > 2 and seg['text'][:1] not in '「『“（(《【':
        a_, b_ = cr[0]
        rest = ink[:, cr[1][0]:]
        rr = np.where(rest.any(1))[0]; r0 = np.where(ink[:, a_:b_].any(1))[0]
        if len(rr) and len(r0):
            hr = rr[-1] - rr[0]
            off = max(abs(r0[0] - rr[0]), abs(r0[-1] - rr[-1]))
            c_lead = np.median(crop[:, a_:b_][ink[:, a_:b_]], 0); c_rest = np.median(crop[:, cr[1][0]:][rest], 0)
            gap_ok = cr[1][0] - b_ > 0.12 * hr
            thin_first = seg['text'][:1] in '一二三丶、，。．-—–_~…'
            if gap_ok and ((off > 0.25 * hr and not thin_first) or (np.linalg.norm(c_lead - c_rest) > 80 and (b_ - a_) < 1.3 * hr)):
                ink[:, a_:b_] = False
                ys = np.where(ink.any(1))[0]; xs = np.where(ink.any(0))[0]
                iy0, iy1, ix0 = ys[0], ys[-1] + 1, xs[0]
    # thin vertical rules at either end (label | value dividers) are not glyphs
    for _ in range(2):
        cols = ink.any(0); cr2, st = [], None
        for i, v in enumerate(list(cols) + [False]):
            if v and st is None: st = i
            if not v and st is not None: cr2.append((st, i)); st = None
        if len(cr2) < 2:
            break
        for a_, b_ in (cr2[0], cr2[-1]):
            rr = np.where(ink[:, a_:b_].any(1))[0]
            if len(rr) and (b_ - a_) < 0.12 * h and (rr[-1] - rr[0]) > 0.8 * (iy1 - iy0):
                ink[:, a_:b_] = False
        ys = np.where(ink.any(1))[0]; xs = np.where(ink.any(0))[0]
        if len(ys) < 3 or len(xs) < 3:
            return None, 'no-ink'
        iy0, iy1, ix0, ix1 = ys[0], ys[-1] + 1, xs[0], xs[-1] + 1
    # numbered badge before the label (digit in a filled circle): strip the number, keep the badge in the plate
    mnum = re.match(r'^(\d{1,2})\s*(?=[\u4e00-\u9fff])', seg['text'])
    cols = ink.any(0); cr, st = [], None
    for i, v in enumerate(list(cols) + [False]):
        if v and st is None: st = i
        if not v and st is not None: cr.append((st, i)); st = None
    cr = [c for c in cr if c[0] >= ix0]
    if mnum and ix0 > (x0 - X0) + 0.6 * h:
        seg['text'] = seg['text'][mnum.end():].lstrip()     # badge ink already dropped by the leading-cluster rules
    elif mnum and len(cr) > 1:
        a_, b_ = cr[0]; hh = iy1 - iy0
        if 0.6 * hh <= (b_ - a_) <= 1.8 * hh and cr[1][0] - b_ > 0.2 * hh:
            ink[:, a_:b_] = False
            ys = np.where(ink.any(1))[0]; xs = np.where(ink.any(0))[0]
            iy0, iy1, ix0 = ys[0], ys[-1] + 1, xs[0]
            seg['text'] = seg['text'][mnum.end():].lstrip()
    if iy1 - iy0 > 1.15 * h:                        # swallowed a neighbouring line or a panel edge: clamp to the OCR box
        ink[:max(0, int(y0) - Y0)] = False; ink[int(np.ceil(y1)) - Y0:] = False
        ys = np.where(ink.any(1))[0]
        if len(ys) < 3:
            return None, 'no-ink'
        iy0, iy1 = ys[0], ys[-1] + 1
    hm, wm = iy1 - iy0, ix1 - ix0
    if hm < MIN_INK_H * W / 3840.0:
        return None, 'too-small'
    ring = ~ndi.binary_dilation(ink, iterations=max(3, int(0.15 * h))) & lim
    # texture around the line: median 5x5 local std of the grey image in a ring of half a line height.
    # Panel edges touch only a few ring pixels; photos and screenshots are textured everywhere.
    bgstd = texture_ring(img, seg['box'])
    if bgstd > MAX_BG_STD:
        return None, 'busy-background(%.0f)' % bgstd
    obs = np.clip((d - 0.15 * dmax) / (0.7 * dmax), 0, 1) * ink
    text = seg['text']
    n = len(text)
    cjk = sum(1 for c in text if is_cjk(c)) / max(1, len(text.replace(' ', '')))
    # observed stroke signature (ink integral normalised by full ink contrast)
    C = stem_peak(d[iy0:iy1, ix0:ix1] * ink[iy0:iy1, ix0:ix1], hm / 0.9)
    ob = np.clip(d / C, 0, 1) * ink
    osig = stroke_sig(ob[max(0, iy0 - 2):iy1 + 2, max(0, ix0 - 2):ix1 + 2], hm / 0.9)
    def evaluate(fam, w):
        ref = render(text, fam, w, 100)
        if ref is None:
            return None
        px = 100.0 * hm / max(1, ref['bot'] - ref['top'])
        rw = render(text, fam, w, px)
        if rw is None:
            return None
        track = (wm - (rw['x1'] - rw['x0'])) / max(1, n - 1) if n > 1 else 0.0
        dist, ratio = 0.0, None
        if osig is not None:
            rsig = stroke_sig(render(text, fam, w, px, track, alpha=True)['alpha'], px)
            if rsig is None:
                return None
            dist = abs(np.log(osig[1] / rsig[1])) + 0.5 * abs(np.log(osig[0] / rsig[0]))
            ratio = rsig[0] / rsig[1]
        return (dist, fam, w, px, track, ratio)
    # stage 1: family from stroke contrast, judged at each family's middle weight
    probe = {f: evaluate(f, 'Regular' if 'Regular' in FAMILIES[f]['weights'] else list(FAMILIES[f]['weights'])[0]) for f in families}
    probe = {f: c for f, c in probe.items() if c is not None}
    if not probe:
        return None, 'no-fit'
    # stage 2: every weight of the plausible families (a family is dropped when clearly off in contrast)
    cands = list(probe.values())
    if osig is not None and len(probe) > 1:
        r_o = osig[0] / osig[1]
        sc0 = {f: abs(np.log(r_o / c[5])) for f, c in probe.items()}
        keep_f = [f for f in probe if sc0[f] <= min(sc0.values()) + 0.25]
    else:
        keep_f = list(probe)
    for fam in keep_f:
        for w in FAMILIES[fam]['weights']:
            if w == probe[fam][2]:
                continue
            c = evaluate(fam, w)
            if c is not None:
                cands.append(c)
    if not cands:
        return None, 'no-fit'
    best_by_fam = {}
    for c in sorted(cands, key=lambda c: c[0]):
        best_by_fam.setdefault(c[1], c)
    if osig is not None and len(best_by_fam) > 1:
        r_o = osig[0] / osig[1]
        fam_score = {f: float(abs(np.log(r_o / c[5]))) for f, c in best_by_fam.items()}
        pick = min(fam_score, key=fam_score.get)
    else:
        pick = min(best_by_fam, key=lambda f: best_by_fam[f][0])
        fam_score = {f: 0.0 for f in best_by_fam}
    dist, fam, w, px, track, _ = best_by_fam[pick]
    cands.sort(key=lambda c: c[0])
    # generated CJK faces are often wider than Noto at the same ink height: size from height alone forces
    # negative tracking and leaves full-width punctuation gaping. Blend height- and width-based size.
    px_scale = 1.0
    if sum(1 for c in text if '\u4e00' <= c <= '\u9fff') >= 4:
        def glyph_w(cols, em):
            r_, st_ = [], None
            for i_, v_ in enumerate(list(cols) + [False]):
                if v_ and st_ is None: st_ = i_
                if not v_ and st_ is not None: r_.append(i_ - st_); st_ = None
            ws_ = [x_ for x_ in r_ if 0.6 * em < x_ < 1.25 * em]
            return float(np.median(ws_)) if len(ws_) >= 3 else None
        wi = glyph_w(ink[iy0:iy1, ix0:ix1].any(0), px)
        rr_ = render(text, fam, w, px, 0.08 * px, alpha=True)
        wr = glyph_w((rr_['alpha'] > 0.5).any(0), px)
        if wi and wr and 0.9 < wi / wr < 1.15:
            px_scale = (1.0 + wi / wr) / 2.0
            px *= px_scale
    occ = ink[iy0:iy1, ix0:ix1].any(0)
    text, track, sp_extra, col_iou, pq = fit_spacing(text, fam, w, px, occ, exact=bool(seg.get('exact')))
    n = len(text)
    rt = render(text, fam, w, px, 0, track_runs=track_list(text, track, sp_extra, pq))
    base = ((Y0 + iy0) - rt['top'] + (Y0 + iy1) - rt['bot']) / 2.0
    left = (X0 + ix0) - rt['x0']
    # colour: per glyph, then merge neighbours of similar colour into runs; detect foil gradients
    strong = obs > 0.6
    col = np.median(crop[strong], 0) if strong.sum() > 5 else np.median(crop[ink], 0)
    t3 = max(1, hm // 3)
    top_m, bot_m = strong[iy0:iy0 + t3], strong[iy1 - t3:iy1]
    top_c = np.median(crop[iy0:iy0 + t3][top_m], 0) if top_m.sum() > 5 else col
    bot_c = np.median(crop[iy1 - t3:iy1][bot_m], 0) if bot_m.sum() > 5 else col
    hexc = lambda c: '%02X%02X%02X' % tuple(int(v) for v in np.clip(c, 0, 255))
    ring_c = np.median(crop[ring], 0) if ring.any() else np.median(bg.reshape(-1, 3), 0)
    inkish = lambda c: np.linalg.norm(c - ring_c) > 0.55 * np.linalg.norm(col - ring_c)
    grad = [hexc(top_c), hexc(bot_c)] if (np.linalg.norm(top_c - bot_c) > 38 and inkish(top_c) and inkish(bot_c)) else None
    runs = []
    for k, (cx0, cx1) in enumerate(rt['cells']):
        cw = cx1 - cx0
        a, b = int(round(left + cx0 + 0.2 * cw)) - X0, int(round(left + cx1 - 0.2 * cw)) - X0
        a, b = max(0, a), min(crop.shape[1], max(a + 1, b))
        m = strong[:, a:b]
        runs.append(np.median(crop[:, a:b][m], 0) if m.sum() > 3 else None)
    groups = []
    for k, c in enumerate(runs):
        ch = text[k]
        if c is None or ch.isspace():
            if groups: groups[-1][1] += ch
            else: groups.append([col, ch])
            continue
        if groups and np.linalg.norm(np.asarray(groups[-1][0]) - c) < 60:
            groups[-1][1] += ch
        else:
            groups.append([c, ch])
    res = dict(text=text, family=fam, weight=w, px=px, px_scale=px_scale, track_px=track, space_extra_px=sp_extra, punct_extra_px=pq, col_iou=round(float(col_iou), 3), base=base, left=left,
               ink=[int(X0 + ix0), int(Y0 + iy0), int(X0 + ix1), int(Y0 + iy1)],
               color=hexc(col), gradient=grad, runs=[dict(text=t, color=hexc(c)) for c, t in groups],
               dist=dist, alt=[(round(c[0], 3), c[1], c[2]) for c in cands[:3]], contrast=(round(osig[0] / osig[1], 3) if osig else None),
               cand={'%s|%s' % (c[1], c[2]): round(float(c[0]), 4) for c in cands},
               fam_score={k: round(v, 3) for k, v in fam_score.items()}, bg_std=bgstd, cjk=cjk)
    res['_ink'] = (ink, obs, X0, Y0)
    return res, 'ok'

def refit(f, fam, w, px=None):
    """Re-derive size (from ink height when px is None), tracking, baseline and left for a forced style."""
    text = f['text']
    ix0, iy0, ix1, iy1 = f['ink']
    if px is None:
        ref = render(text, fam, w, 100)
        if ref is None:
            return
        px = 100.0 * (iy1 - iy0) / max(1, ref['bot'] - ref['top']) * f.get('px_scale', 1.0)
    e = f.get('space_extra_px', 0.0) * px / max(1e-3, f['px'])
    q = f.get('punct_extra_px', 0.0) * px / max(1e-3, f['px'])
    track = spaced_track(text, fam, w, px, ix1 - ix0, e, q)
    if track is None:
        return
    rt = render(text, fam, w, px, 0, track_runs=track_list(text, track, e, q))
    f.update(family=fam, weight=w, px=px, track_px=track, space_extra_px=e, punct_extra_px=q,
             base=(iy0 - rt['top'] + iy1 - rt['bot']) / 2.0, left=ix0 - rt['x0'])

def harmonise(fits):
    """Lines that share size and colour on a page are one text style: cluster them (union-find),
    choose the family by character-weighted contrast votes, then the weight with the least total
    stroke distance, and a common size."""
    def rgb(h): return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)])
    n = len(fits); par = list(range(n))
    def find(i):
        while par[i] != i: par[i] = par[par[i]]; i = par[i]
        return i
    for i in range(n):
        for j in range(i + 1, n):
            a, b = fits[i], fits[j]
            if abs(a['px'] - b['px']) < 0.1 * min(a['px'], b['px']) and np.linalg.norm(rgb(a['color']) - rgb(b['color'])) < 50:
                par[find(i)] = find(j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(fits[i])
    ncjk = lambda f: sum(1 for c in f['text'] if '\u4e00' <= c <= '\u9fff')
    cjk_lines = [f for f in fits if ncjk(f) >= 3]
    ordered = sorted(groups.values(), key=lambda g: sum(ncjk(f) for f in g) < 3)   # CJK groups first
    for g in ordered:
        wt = lambda f: len(f['text'].replace(' ', ''))
        if cjk_lines and sum(ncjk(f) for f in g) < 3:
            # digits / Latin only: too few strokes to judge the family; take the family of the CJK line
            # closest in colour and size (a gold serif kicker implies gold serif figures)
            g0_ = g[0]
            ref_ = min(cjk_lines, key=lambda f2: np.linalg.norm(rgb(f2['color']) - rgb(g0_['color'])) + 60 * abs(np.log(f2['px'] / g0_['px'])))
            for f in g:
                f['fam_score'] = {k: (0.0 if k == ref_['family'] else 1.0) for k in (f['fam_score'] or {ref_['family']: 0})}
                f['fam_score'].setdefault(ref_['family'], 0.0)
        fams = {}
        for f in g:
            for fam, sc in f['fam_score'].items():
                fams.setdefault(fam, 0.0)
        if len(fams) > 1:
            fam = min(fams, key=lambda fm: sum(wt(f) * f['fam_score'].get(fm, 1.0) for f in g))
        else:
            fam = g[0]['family']
        ws = {}
        for f in g:
            for k, v in f['cand'].items():
                fm, w = k.split('|')
                if fm == fam:
                    ws.setdefault(w, []).append(wt(f) * v)
        full = [w for w, v in ws.items() if len(v) == len(g)] or list(ws)
        w = min(full, key=lambda w: sum(ws[w])) if full else g[0]['weight']
        if w not in FAMILIES[fam]['weights']:
            w = 'Regular' if 'Regular' in FAMILIES[fam]['weights'] else list(FAMILIES[fam]['weights'])[0]
        for f in g:
            if (fam, w) != (f['family'], f['weight']):
                refit(f, fam, w)
        px = float(np.median([f['px'] for f in g]))
        for f in g:
            if 0.015 * f['px'] < abs(px - f['px']) < 0.06 * f['px']:
                refit(f, fam, w, px)

TAIL_UNITS = set('%‰')

def fit_tail(f):
    """Big figures often carry a smaller unit ('92.3' + small '%'). Refit the figure alone on its own ink and
    set the unit at its measured size, so the figure keeps its true size and tracking."""
    text = f['text']
    if len(text) < 3 or text[-1] not in TAIL_UNITS or not text[-2].isdigit() or '_ink' not in f:
        return
    ink, obs, X0, Y0 = f['_ink']
    ix0, iy0, ix1, iy1 = f['ink']
    sub = ink[iy0 - Y0:iy1 - Y0, ix0 - X0:ix1 - X0]
    cols = sub.any(0); runs, st = [], None
    for i, v in enumerate(list(cols) + [False]):
        if v and st is None: st = i
        if not v and st is not None: runs.append((st, i)); st = None
    if len(runs) < 2:
        return
    ta, tb = runs[-1]
    hr = np.where(sub[:, :runs[-2][1]].any(1))[0]; tr_ = np.where(sub[:, ta:tb].any(1))[0]
    if not len(hr) or not len(tr_):
        return
    hh, th = hr[-1] - hr[0] + 1, tr_[-1] - tr_[0] + 1
    if th > 0.85 * hh:
        return
    head, fam, w = text[:-1], f['family'], f['weight']
    ref = render(head, fam, w, 100)
    if ref is None:
        return
    px = 100.0 * hh / max(1, ref['bot'] - ref['top'])
    rw = render(head, fam, w, px)
    track = (runs[-2][1] - (rw['x1'] - rw['x0'])) / max(1, len(head) - 1)
    rh = render(head, fam, w, px, track)
    left = ix0 - rh['x0']
    base = ((iy0 + hr[0]) - rh['top'] + (iy0 + hr[-1] + 1) - rh['bot']) / 2.0
    ru = render(text[-1], fam, w, 100)
    upx = 100.0 * th / max(1, ru['bot'] - ru['top'])
    rtl = render(text[-1], fam, w, upx)
    gap = (ix0 + ta - rtl['x0']) - (left + rh['adv_total'] - track)
    f.update(px=px, track_px=track, left=left, base=base, space_extra_px=0.0, punct_extra_px=0.0,
             tail=dict(n=1, scale=round(upx / px, 4), gap=gap))

def paragraphs(fits):
    """Stack consecutive lines of one style into a paragraph (one text box with line breaks)."""
    fits = sorted(fits, key=lambda f: (f['base'], f['ink'][0]))
    used = [False] * len(fits)
    paras = []
    for i, f in enumerate(fits):
        if used[i]: continue
        used[i] = True
        cur = [f]
        while True:
            last = cur[-1]
            nxt = None
            for j, g in enumerate(fits):
                if used[j] or g['base'] <= last['base']: continue
                pitch = g['base'] - last['base']
                same = (g['family'], g['weight']) == (last['family'], last['weight']) and abs(g['px'] - last['px']) < 0.06 * last['px']
                ca = np.array([int(last['color'][k:k + 2], 16) for k in (0, 2, 4)]); cb = np.array([int(g['color'][k:k + 2], 16) for k in (0, 2, 4)])
                if not same or np.linalg.norm(ca - cb) > 45 or not (1.05 * last['px'] < pitch < 2.3 * last['px']):
                    continue
                if len(cur) > 1:
                    p0 = cur[1]['base'] - cur[0]['base']
                    if abs(pitch - p0) > 0.12 * p0: continue
                tol = 0.6 * last['px'] + 4
                l_ok = abs(g['ink'][0] - cur[0]['ink'][0]) < tol
                c_ok = abs((g['ink'][0] + g['ink'][2]) / 2 - (cur[0]['ink'][0] + cur[0]['ink'][2]) / 2) < tol
                r_ok = abs(g['ink'][2] - cur[0]['ink'][2]) < tol
                if l_ok or c_ok or r_ok:
                    nxt = j; break
            if nxt is None: break
            used[nxt] = True; cur.append(fits[nxt])
        paras.append(cur)
    out = []
    for ls in paras:
        px = float(np.median([f['px'] for f in ls]))
        pitch = float(np.median(np.diff([f['base'] for f in ls]))) if len(ls) > 1 else 1.2 * px
        lefts = [f['ink'][0] for f in ls]; rights = [f['ink'][2] for f in ls]; cents = [(a + b) / 2 for a, b in zip(lefts, rights)]
        align = 'l'
        if len(ls) > 1:
            sp = lambda v: max(v) - min(v)
            if sp(lefts) > 0.5 * px and sp(cents) < 0.5 * px: align = 'ctr'
            elif sp(lefts) > 0.5 * px and sp(rights) < 0.5 * px: align = 'r'
        out.append(dict(lines=ls, px=px, pitch=pitch, family=ls[0]['family'], weight=ls[0]['weight'], align=align))
    return out

# ─────────────────────────────── plate
_lama = None
def lama():
    global _lama
    if _lama is None:
        import torch
        os.environ.setdefault('LAMA_MODEL', os.path.expanduser('~/.cache/torch/hub/checkpoints/big-lama.pt'))
        from simple_lama_inpainting import SimpleLama
        if os.environ.get('LAMA_CPU'):
            dev = torch.device('cpu')
        elif torch.cuda.is_available():                     # Windows with an NVIDIA GPU and a CUDA build of torch
            dev = torch.device('cuda')
        elif torch.backends.mps.is_available():             # Apple silicon
            dev = torch.device('mps')
        else:
            dev = torch.device('cpu')
        try:
            _lama = SimpleLama(device=dev)
            _lama(Image.new('RGB', (64, 64)), Image.new('L', (64, 64), 255)); print('LaMa device:', dev, flush=True)
        except Exception as e:
            print('LaMa on', dev, 'failed (%s), using CPU' % type(e).__name__)
            _lama = SimpleLama(device=torch.device('cpu'))
    return _lama

def _lama_tile(sub, mk):
    res = np.array(lama()(Image.fromarray(sub), Image.fromarray((mk * 255).astype(np.uint8))).convert('RGB'))[:sub.shape[0], :sub.shape[1]]
    try:
        import torch
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
        elif torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
    return res

def _cuts(profile, length, tile, overlap):
    """Tile start offsets along one axis, each cut moved to the least-masked position near its target."""
    if length <= tile:
        return [0]
    starts, x = [0], 0
    while x + tile < length:
        target = x + tile - overlap
        lo, hi = max(x + tile // 2, target - tile // 4), min(length - overlap, target + tile // 8)
        if hi <= lo:
            nxt = target
        else:
            seg = profile[lo:hi]
            nxt = lo + int(np.argmin(seg))
        starts.append(nxt); x = nxt
    return starts

def make_plate(img, mask, max_pixels=2.2e6, tile=1400, overlap=200):
    """LaMa on crops around each group of masked text (context margin included). A crop is processed in one
    pass when it has at most max_pixels (long title lines included); larger crops are tiled with cuts placed
    where the mask is thinnest, so no glyph is split across a tile edge. Only masked pixels change."""
    H, W, _ = img.shape
    plate = img.copy()
    lab, n = ndi.label(ndi.binary_dilation(mask, iterations=10))
    for idx, sl in enumerate(ndi.find_objects(lab), 1):
        y0, y1, x0, x1 = sl[0].start, sl[0].stop, sl[1].start, sl[1].stop
        m = int(max(48, 0.35 * min(y1 - y0, 400)))
        Y0, Y1, X0, X1 = max(0, y0 - m), min(H, y1 + m), max(0, x0 - m), min(W, x1 + m)
        if (Y1 - Y0) * (X1 - X0) <= max_pixels:
            tiles = [(Y0, Y1, X0, X1)]
        else:
            mk_all = mask[Y0:Y1, X0:X1]
            txs = _cuts(mk_all.sum(0), X1 - X0, tile, overlap)
            tys = _cuts(mk_all.sum(1), Y1 - Y0, tile, overlap)
            tiles = [(Y0 + ty, min(Y1, Y0 + ty + tile), X0 + tx, min(X1, X0 + tx + tile)) for ty in tys for tx in txs]
        for ty, ty1, tx, tx1 in tiles:
            # only this group's pixels: a neighbouring line's mask caught in the context margin sits on the crop
            # edge without context and would be refilled badly (it was already filled by its own group)
            mk = mask[ty:ty1, tx:tx1] & (lab[ty:ty1, tx:tx1] == idx)
            if not mk.any():
                continue
            sub = plate[ty:ty1, tx:tx1]
            res = _lama_tile(sub, mk)
            a = cv2.GaussianBlur(ndi.binary_dilation(mk, iterations=1).astype(np.float32), (0, 0), 1.2)[..., None]
            a = np.maximum(a, mk[..., None].astype(np.float32))
            plate[ty:ty1, tx:tx1] = (sub * (1 - a) + res * a).astype(np.uint8)
    return plate

# ─────────────────────────────── main
def process(page, corpus):
    pid = page['pid']
    path = os.path.join(WORK, page['image'])
    img = np.array(Image.open(path).convert('RGB'))
    H, W, _ = img.shape
    od = os.path.join(WORK, '02_分层', pid); os.makedirs(od, exist_ok=True)
    pcfg = CFG.get('pages', {}).get(pid, {})
    families = pcfg.get('families', CFG.get('families', list(FAMILIES)))
    lines = ocr(path)
    json.dump(lines, open(os.path.join(od, 'ocr.json'), 'w'), ensure_ascii=False)
    segs = []
    for L in lines:
        for sg in split_segments(L):
            segs += split_by_height(img, sg, pcfg.get('split_points', [])) if CFG.get('split_by_height', True) else [sg]
    segs = apply_height_splits(img, segs)
    excl = [tuple(b) for b in pcfg.get('exclude_boxes', [])]
    fits, skipped, fixes, draft_diffs = [], [], [], []
    todo = []
    for s in segs:
        raw = s['text']
        if excl and any(s['box'][0] >= b[0] and s['box'][1] >= b[1] and s['box'][2] <= b[2] and s['box'][3] <= b[3] for b in excl):
            skipped.append(dict(text=raw, box=s['box'], why='excluded')); continue
        nm = norm_map(raw)[0]
        if not nm or (len(nm) == 1 and (s['conf'] < 0.6 or not re.match(r'[一-鿿A-Za-z0-9]', nm))):
            skipped.append(dict(text=raw, box=s['box'], why='symbol')); continue
        nk = len(re.findall(r'[぀-ヿ가-힯]', raw))
        if nk >= 2 or nk > 0.2 * max(1, len(raw)):                  # kana / hangul: garbled UI text in a screenshot
            skipped.append(dict(text=raw, box=s['box'], why='garbled')); continue
        if nk and s.get('chars'):                                     # a single ornament read as kana
            s['chars'] = [(c, b) for c, b in s['chars'] if not re.match(r'[぀-ヿ가-힯]', c)]
            s['text'] = ''.join(c for c, _ in s['chars']).strip(); raw = s['text']
        nword = len(re.findall(r'[一-鿿A-Za-z0-9]', raw)); nall = len(raw.replace(' ', ''))
        moonish = set('()（）[]<>《》〈〉CcDdOo0〇◯|丨')
        if (nword <= 2 and nword < 0.3 * nall) or (nall <= 8 and all(ch in moonish for ch in raw.replace(' ', ''))):   # moon phases, sparkles read as ')))+', 'C('
            skipped.append(dict(text=raw, box=s['box'], why='ornament')); continue
        if s.get('chars'):
            k = 0
            while k < len(s['chars']) and (s['chars'][k][0] in LEAD_SYMBOLS or (k and s['chars'][k][0].isspace())):
                k += 1
            t0 = s['text']
            if k == 0 and t0[:1] in '（(' and not any(c in '）)' for c in t0[1:]):
                k = 1
                while k < len(s['chars']) and s['chars'][k][0].isspace(): k += 1
                s['chars'] = s['chars'][:1] and [('•', s['chars'][0][1])] + s['chars'][1:]
            if s['text'][-1:] in '）)' and not any(c in '（(' for c in s['text'][:-1]) and len(s['chars']) > 2:
                s['chars'] = s['chars'][:-1]
                while s['chars'] and s['chars'][-1][0].isspace(): s['chars'] = s['chars'][:-1]
                s['text'] = ''.join(c for c, _ in s['chars'])
                bs = [b for _, b in s['chars'] if b]
                s['box'] = [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]
            if 0 < k < len(s['chars']) and s['chars'][0][0] in LEAD_SYMBOLS:
                s['chars'] = s['chars'][k:]
                s['text'] = ''.join(c for c, _ in s['chars'])
                bs = [b for _, b in s['chars'] if b]
                s['box'] = [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]
                s['lead_symbol'] = True
        if s.get('chars'):
            ch = s['chars']
            while ch and (ch[-1][0] in '|｜' or ch[-1][0].isspace()): ch = ch[:-1]
            while ch and (ch[0][0] in '|｜' or ch[0][0].isspace()): ch = ch[1:]
            if ch and len(ch) != len(s['chars']):
                s['chars'] = ch; s['text'] = ''.join(c for c, _ in ch)
                bs = [b for _, b in ch if b]
                if bs and s.get('split') != 'height':
                    s['box'] = [min(b[0] for b in bs), s['box'][1], max(b[2] for b in bs), s['box'][3]]
            if not ch:
                continue
        todo.append(s)
    for s in todo:
        x0, y0, x1, y1 = s['box']
        for o in segs:
            if o is s:
                continue
            ox0, oy0, ox1, oy1 = o['box']
            if min(x1, ox1) - max(x0, ox0) < 0.3 * min(x1 - x0, ox1 - ox0):
                continue
            if y0 < oy0 < y1 < oy1:                    # neighbour below overlaps our bottom
                y1 = (oy0 + y1) / 2.0; s['cut_bottom'] = True
            elif oy0 < y0 < oy1 < y1:                  # neighbour above overlaps our top
                y0 = (y0 + oy1) / 2.0; s['cut_top'] = True
        for o in segs:                                 # same-row neighbours: never read or ink across them
            if o is s:
                continue
            ox0, oy0, ox1, oy1 = o['box']; h_ = y1 - y0
            if min(y1, oy1) - max(y0, oy0) < 0.5 * min(h_, oy1 - oy0):
                continue
            if x0 < ox0 < x1 + 0.6 * h_ and ox1 > x1:           # neighbour on the right
                cut = min(x1, ox0) if ox0 >= x1 else (ox0 + x1) / 2.0
                x1 = min(x1, cut) if ox0 < x1 else x1
                s['pad_r'] = min(s.get('pad_r', 0.6), max(0.02, (max(ox0, x1) - x1) / 2.0 / max(1, h_)))
            elif x0 - 0.6 * h_ < ox1 < x1 and ox0 < x0:        # neighbour on the left
                x0 = max(x0, (ox1 + x0) / 2.0) if ox1 > x0 else x0
                s['pad_l'] = min(s.get('pad_l', 0.6), max(0.02, (x0 - min(ox1, x0)) / 2.0 / max(1, h_)))
        s['box'] = [x0, y0, x1, y1]
    reads = crop_readings(Image.fromarray(img), todo, OCR_CMD) if CFG.get('ocr_vote', True) else [[] for _ in todo]
    for s, rd in zip(todo, reads):
        raw = s['text']
        text, voted = vote(raw, rd)
        via = ['vote'] if voted else []
        t2 = strip_ornaments(text)
        t2 = strip_icon_suffix(strip_icon_prefix(t2, rd), rd)
        if t2 != text:
            text = t2; via.append('ornament')
        if corpus is not None:
            m, auth = corpus.match(pid, text)
            if m and m[0] != text:
                if auth:                                 # the whiteboard copy is the intended text
                    text = m[0]; via.append('outline'); s['exact'] = True
                else:
                    t2, rej = filter_corpus(text, m[0], rd)
                    if rej:
                        draft_diffs.append(dict(text=t2, rejected=rej, draft=m[2]))
                    if t2 != text:
                        text = t2; via.append('corpus')
        text = re.sub(r'\s+', ' ', text.replace(GAP, ' ')).strip()
        text = re.sub(r'(?<=[—–])一|一(?=[—–])', '—', text)          # '——' read as '—一'
        text = re.sub(r'—{3,}', '——', text)
        text = re.sub(r'^[。．]\s*(?=[\u4e00-\u9fff])', '', text)            # a bullet read as '。'
        text = re.sub(r'(?<=[\u4e00-\u9fff\d]) ?[xX] ?(?=[\u4e00-\u9fff])', lambda m_: m_.group(0).replace('x', '×').replace('X', '×'), text)
        for a_, b_ in list(CFG.get('replace', {}).items()) + list(pcfg.get('replace', {}).items()):
            if a_.startswith('re:'):
                t2 = re.sub(a_[3:], b_, text)
            else:
                t2 = text.replace(a_, b_)
            if t2 != text:
                text = t2; via.append('replace')
        raw = raw.replace(GAP, ' ')
        if CFG.get('bullets_in_plate', True):
            t2 = re.sub(r'^[•·●◆◇▪■]\s*', '', text)
            if t2 != text and t2:
                text = t2; via.append('bullet')
        if text != raw:
            fixes.append(dict(ocr=raw, text=text, via='+'.join(via), crops=rd))
            if s.get('chars'):
                kept = set()
                for tag, a0, a1, b0, b1 in difflib.SequenceMatcher(None, raw, text, autojunk=False).get_opcodes():
                    if tag in ('equal', 'replace'):
                        kept.update(range(a0, a1))
                kb = [s['chars'][i][1] for i in sorted(kept) if i < len(s['chars']) and s['chars'][i][1]]
                if kb:
                    s['keep_boxes'] = kb
        s['text'] = text
        if not norm_map(text)[0]:
            skipped.append(dict(text=raw, box=s['box'], why='emptied')); continue
        f, why = fit_segment(img, s, W, H, families)
        if f is None:
            skipped.append(dict(text=text, box=s['box'], why=why)); continue
        f['ocr'] = raw
        f['reads'] = rd
        nz = lambda t: re.sub(r'[\s•·。]', '', t.replace(GAP, ''))
        f['agree'] = bool(rd) and all(nz(r) == nz(raw) for r in rd)
        fits.append(f)
    harmonise(fits)
    for f in fits:
        fit_tail(f)
    paras = paragraphs(fits)
    # plate: remove the ink of every converted line (dilated to take the anti-aliased halo and glow)
    mask = np.zeros((H, W), bool)
    for f in fits:
        ink, obs, X0, Y0 = f.pop('_ink')
        r = max(3, int(round(0.16 * f['px'])))
        mk = ndi.binary_dilation(obs > 0.05, iterations=r)
        ix0, iy0, ix1, iy1 = f['ink']
        box = np.zeros_like(mk); m2 = r + 3
        box[max(0, iy0 - Y0 - m2): iy1 - Y0 + m2, max(0, ix0 - X0 - m2): ix1 - X0 + m2] = True
        mask[Y0:Y0 + mk.shape[0], X0:X0 + mk.shape[1]] |= mk & box
    t0 = time.time()
    plate = make_plate(img, mask) if mask.any() else img
    Image.fromarray(plate).save(os.path.join(od, 'plate.jpg'), quality=CFG.get('plate_quality', 92), subsampling=0)
    # debug overlay + local preview (plate + text drawn with the same fonts)
    dbg = Image.fromarray(img).convert('RGB'); dr = ImageDraw.Draw(dbg)
    for f in fits:
        dr.rectangle(f['ink'], outline=(0, 170, 0) if f['family'] == 'serif' else (0, 90, 255), width=3)
    for s in skipped:
        dr.rectangle([int(v) for v in s['box']], outline=(230, 0, 0), width=3)
    dbg.resize((W // 2, H // 2)).save(os.path.join(od, 'debug.jpg'), quality=85)
    prev = Image.fromarray(plate).convert('RGB')
    for f in fits:
        fnt_x = f['left']
        tl, fac = char_layout(f)
        k_ = 0
        for r in f['runs']:
            for c in r['text']:
                fo = font(f['family'], f['weight'], f['px'] * (fac[k_] if k_ < len(fac) else 1.0))
                ImageDraw.Draw(prev).text((fnt_x, f['base']), c, font=fo, fill='#' + r['color'], anchor='ls')
                fnt_x += fo.getlength(c) + (tl[k_] if k_ < len(tl) else f['track_px']); k_ += 1
    prev.save(os.path.join(od, 'preview.jpg'), quality=88)
    out = dict(pid=pid, source=path, size=[W, H],
               paragraphs=[dict(px=p['px'], pitch=p['pitch'], family=p['family'], weight=p['weight'], align=p['align'],
                                lines=[{k: v for k, v in f.items() if k != 'rt'} for f in p['lines']]) for p in paras],
               skipped=skipped, corrections=fixes, draft_diffs=draft_diffs, mask_px=int(mask.sum()), plate_seconds=round(time.time() - t0, 1))
    json.dump(out, open(os.path.join(od, 'layers.json'), 'w'), ensure_ascii=False, indent=1, default=float)
    return out

if __name__ == '__main__':
    man = json.load(open(os.path.join(WORK, 'manifest.json')))
    cp = os.path.join(WORK, 'corpus.json')
    corpus = CorpusSet(json.load(open(cp, encoding='utf-8'))) if os.path.exists(cp) else None
    todo = sys.argv[2:] or [p['pid'] for p in man['pages']]
    for p in man['pages']:
        if p['pid'] not in todo or 'image' not in p:
            continue
        t = time.time()
        o = process(p, corpus)
        nl = sum(len(q['lines']) for q in o['paragraphs'])
        fam = {}
        for q in o['paragraphs']:
            fam[q['family'] + '-' + q['weight']] = fam.get(q['family'] + '-' + q['weight'], 0) + len(q['lines'])
        print('%s lines=%d paras=%d skipped=%d fixes=%d styles=%s  %.0fs (plate %.0fs)' % (
            p['pid'], nl, len(o['paragraphs']), len(o['skipped']), len(o['corrections']), fam, time.time() - t, o['plate_seconds']), flush=True)
