# -*- coding: utf-8 -*-
"""Stage 2 QA · OCR every generated slide and check each verbatim string of its prompt, and that the reserved
logo / page-number corners hold no text (the page-number corner only on slides that get a page number). A string
may sit on one OCR line, two adjacent lines, or two to four lines stacked in one column (text wrapped inside a
diagram node, a label above its date in a timeline).

Usage: textcheck.py <project> <prompts_dir> <raw_dir> [--pages p01,p02]
Uses <raw_dir>/selected.json. Writes <raw_dir>/textcheck.json (pages checked earlier keep their entries, so a
re-check of two pages still compares titles across the whole deck) and prints one line per page:
  OK     all strings found
  NEAR   every string found or nearly found (ratio >= 0.8): usually OCR noise, check the image
  MISS   at least one string missing: regenerate the page, or `deck fix` when it is one or two strings
  CORNER text found inside a reserved corner: regenerate or move the logo
  EXTRA  text on the slide that is in none of its strings (a label taken from the drawing directions, a percentage
         the model worked out, English decoration): look, then regenerate
  DRIFT  the title sits higher / lower / further left or is bigger / smaller than on the other slides of the same
         tone (style drift; hero and asym slides are left out): look, then regenerate with the style references
  PUNCT  a line ends with 。 although its string has no full stop (the image model added one): look, then regenerate
"""
import os, re, sys, json, argparse, difflib, tempfile, statistics
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deckenv as E

def ocr_many(paths):
    lst = tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False, encoding='utf-8')
    lst.write('\n'.join(paths)); lst.close()
    out = E.hostos.run_ocr(['--batch', lst.name])
    os.remove(lst.name)
    return json.loads(out or '{}')

def matched(t, c):
    return sum(b.size for b in difflib.SequenceMatcher(None, t, c, autojunk=False).get_matching_blocks())

def best_ratio(s, lines, stacks=()):
    """Share of the characters of s found, in order, inside one OCR line, two adjacent lines or one column stack."""
    t = E.norm(s)
    if not t:
        return 1.0
    cands = [E.norm(x) for x in lines]
    cands += [cands[i] + cands[i + 1] for i in range(len(cands) - 1)]
    cands += [E.norm(x) for x in stacks]
    best = 0.0
    for c in cands:
        if t in c:
            return 1.0
        best = max(best, matched(t, c) / float(len(t)))
    return best

def column_chains(lines, depth=4):
    """Chains of two to `depth` OCR lines stacked in one column (a string wrapped inside a narrow diagram node or
    card): each next line starts just below the previous one and overlaps it horizontally by at least half the
    narrower width. OCR output order interleaves columns, so adjacent entries of the line list miss these."""
    rows = sorted(lines, key=lambda L: L['y0'])
    out = []
    for i, L in enumerate(rows):
        chain, last = [L], L
        for _ in range(depth - 1):
            h = last['y1'] - last['y0']
            nxt = [M for M in rows[i + 1:] if M not in chain and 0 <= M['y0'] - last['y1'] + h * 0.3 <= h * 1.2 and
                   min(M['x1'], last['x1']) - max(M['x0'], last['x0']) >= 0.5 * min(M['x1'] - M['x0'], last['x1'] - last['x0'])]
            if not nxt:
                break
            last = min(nxt, key=lambda M: M['y0'])
            chain.append(last)
            out.append(list(chain))
    return out

def column_stacks(lines, depth=4):
    return [''.join(M['text'] for M in ch) for ch in column_chains(lines, depth)]

def union(ls):
    return [min(L['x0'] for L in ls), min(L['y0'] for L in ls), max(L['x1'] for L in ls), max(L['y1'] for L in ls)]

def locate(s, lines):
    """Pixel box [x0, y0, x1, y1] of the OCR line(s) that best match s (a wrong rendering of s), or None."""
    t = E.norm(s)
    if len(t) < 2:
        return None
    groups = [[L] for L in lines]
    groups += [[lines[i], lines[i + 1]] for i in range(len(lines) - 1)
               if abs(lines[i]['y0'] - lines[i + 1]['y0']) < (lines[i]['y1'] - lines[i]['y0'])]
    groups += column_chains(lines)
    best, box = 0.0, None
    for g in groups:
        c = E.norm(''.join(L['text'] for L in g))
        if not c:
            continue
        r = matched(t, c) / float(len(t)) * min(1.0, len(t) / float(max(len(c), 1)) + 0.3)
        if r > best:
            best, box = r, union(g)
    return box if best >= 0.45 else None

def extra_stops(strings, texts):
    """Strings whose rendered last line ends with 。 although the approved text has no full stop."""
    out = []
    for t in texts:
        t = t.strip()
        n = E.norm(t)
        if not t.endswith(('。', '．')) or len(n) < 2:
            continue
        tail = n[-min(len(n), 6):]
        for s in strings:
            if E.norm(s).endswith(tail) and not s.rstrip().endswith(('。', '．')) and s not in out:
                out.append(s)
                break
    return out

PCT = re.compile(r'\d+(?:\.\d+)?%')

def covered(t, pool):
    """Per character of t: True when it belongs to a run of 2+ characters found in one of the strings, or it is a
    single character between two such neighbours that one string has with exactly one character between them
    (an OCR slip such as 滯 for 滞)."""
    cov = [False] * len(t)
    i = 0
    while i < len(t):
        k = next((k for k in range(len(t) - i, 1, -1) if any(t[i:i + k] in s for s in pool)), 0)
        if k:
            cov[i:i + k] = [True] * k
            i += k
        else:
            i += 1
    for i in range(1, len(t) - 1):
        if not cov[i] and cov[i - 1] and any(re.search(re.escape(t[i - 1]) + '.' + re.escape(t[i + 1]), s) for s in pool):
            cov[i] = cov[i + 1] = True
    return cov

def extra_text(strings, lines, skip=()):
    """OCR lines carrying text that is in none of the strings: two or more uncovered CJK characters in a row, a
    short line that is mostly uncovered (a label such as 内容端), a percentage, or a Latin word of 4+ letters
    (shorter Latin runs and single characters are usually icons read as letters)."""
    pool = [E.norm(s) for s in strings]
    out = []
    for L in lines:
        if id(L) in skip:
            continue
        t = E.norm(L['text'])
        if len(t) < 2:
            continue
        cov = covered(t, pool)
        runs, run = [], ''
        for ch, c in zip(t, cov + [True]):
            if c:
                if run:
                    runs.append(run)
                run = ''
            else:
                run += ch
        if run:
            runs.append(run)
        miss = sum(1 for c in cov if not c)
        if any(E.cjk_len(r) >= 2 or PCT.search(r) or re.search(r'[A-Z]{4,}', r) for r in runs) or \
                (len(t) >= 3 and E.cjk_len(t) >= 2 and E.cjk_len(''.join(runs)) >= 1 and miss >= 0.3 * len(t)):
            out.append(L['text'].strip())
    return out

def corner_boxes(cfg, W, H, number=True):
    """Reserved corners: the logo corners, plus the page-number corner when the slide gets a page number."""
    boxes = {}
    pn = cfg.get('page_number') or {}
    corners = [lg.get('corner', 'bl') for lg in cfg['logos']] + ([pn['corner']] if pn.get('corner') and number else [])
    for c in set(corners):
        w = 0.20 * W if c.endswith('l') else 0.12 * W
        x0 = 0 if c.endswith('l') else W - w
        y0 = H * 0.91 if c.startswith('b') else 0
        boxes[c] = (x0, y0, x0 + w, y0 + H * 0.09)
    return boxes

def ink_height(img, box):
    """Median height in pixels of the text rows inside box: rows whose ink (pixels far from the background grey)
    covers more than 1.5% of the width, grouped into bands; OCR box heights vary too much to compare type sizes."""
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    g = img.convert('L').crop((max(0, x0), max(0, y0), min(img.width, x1), min(img.height, y1)))
    w, h = g.size
    if w < 10 or h < 6:
        return None
    px = g.load()
    border = sorted([px[i, 0] for i in range(w)] + [px[i, h - 1] for i in range(w)])
    bg = border[len(border) // 2]
    rows = [sum(1 for i in range(0, w, 2) if abs(px[i, j] - bg) > 60) for j in range(h)]
    on = [c > 0.015 * w / 2 for c in rows]
    bands, run = [], 0
    for v in on + [False]:
        if v:
            run += 1
        elif run:
            bands.append(run)
            run = 0
    bands = [b for b in bands if b >= 0.35 * max(bands)] if bands else []
    return statistics.median(bands) if bands else None

def title_box(title, lines, W, H, img=None):
    """[x0, y0, x1, y1, glyph height] of the title as a share of the slide size, or None."""
    t = E.norm(title or '')
    if len(t) < 4:
        return None
    hits = [L for L in lines if len(E.norm(L['text'])) >= min(4, len(t)) and E.norm(L['text']) in t]
    if not hits:
        return None
    top = max(hits, key=lambda L: (L['y1'] - L['y0'], len(L['text'])))       # the title is the largest text
    th = top['y1'] - top['y0']
    hits = [L for L in hits if L['y1'] - L['y0'] >= 0.8 * th and abs((L['y0'] + L['y1']) / 2 - (top['y0'] + top['y1']) / 2) <= 2.6 * th]
    if sum(len(E.norm(L['text'])) for L in hits) < 0.6 * len(t):
        return None
    x0, y0, x1, y1 = union(hits)
    h = ink_height(img, (x0, y0, x1, y1)) if img is not None else None
    h = h or statistics.median(L['y1'] - L['y0'] for L in hits)
    return [round(x0 / W, 4), round(y0 / H, 4), round(x1 / W, 4), round(y1 / H, 4), round(h / H, 4)]

def drift(report, index):
    """{pid: reason} for content slides whose title position or size is off from the other slides of the same tone."""
    out = {}
    groups = {}
    for pid, r in report.items():
        meta = index.get(pid, {})
        if r.get('title_box') and meta.get('kind', 'content') in E.CONTENT_KINDS and meta.get('skeleton') not in ('hero', 'asym'):
            # hero slides enlarge the title on purpose; asym slides may put it in a side column
            groups.setdefault(meta.get('tone', 'light'), []).append(pid)
    for tone, pids in groups.items():
        if len(pids) < 4:
            continue
        bx = {p: report[p]['title_box'] for p in pids}
        my = statistics.median(b[1] for b in bx.values())
        mx = statistics.median(b[0] for b in bx.values())
        mh = statistics.median(b[4] for b in bx.values())
        left = statistics.median(abs(b[0] - mx) for b in bx.values()) < 0.01        # titles are left-aligned
        for p, b in bx.items():
            why = []
            if abs(b[1] - my) > 0.03:
                why.append('标题%s %.0f%% 页高' % ('偏低' if b[1] > my else '偏高', abs(b[1] - my) * 100))
            if left and abs(b[0] - mx) > 0.03:
                why.append('标题左边距%s %.0f%% 页宽' % ('偏大' if b[0] > mx else '偏小', abs(b[0] - mx) * 100))
            if mh and not 0.85 <= b[4] / mh <= 1.18:
                why.append('标题字高为其他页的 %.0f%%' % (b[4] / mh * 100))
            if why:
                out[p] = '，'.join(why)
    return out

def run(project, prompts, raw, pages=None, quiet=False):
    E.ensure_runtime(need_ocr=True)
    cfg = E.load_project(project)
    index = json.load(open(os.path.join(prompts, 'index.json'), encoding='utf-8'))
    sel = json.load(open(os.path.join(raw, 'selected.json'), encoding='utf-8'))
    want = pages or sorted(sel)
    paths = {pid: os.path.abspath(os.path.join(raw, sel[pid])) for pid in want if pid in sel}
    res = ocr_many(list(paths.values()))
    try:
        outline_pages = E.load_outline(project)['pages']
    except Exception:
        outline_pages = None
    total = len(outline_pages) if outline_pages else len(index)
    rp = os.path.join(raw, 'textcheck.json')
    report = json.load(open(rp, encoding='utf-8')) if os.path.exists(rp) else {}
    report = {p: r for p, r in report.items() if p in sel and r.get('file') == sel[p]}          # drop stale entries
    for pid, path in paths.items():
        lines = res.get(path, [])
        texts = [L['text'] for L in lines]
        stacks = column_stacks(lines)
        im = Image.open(path)
        W, H = im.size
        meta = index.get(pid, {})
        strings = meta.get('strings', [])
        miss, near, boxes = [], [], {}
        for s in strings:
            if len(E.norm(s)) < 2:
                continue
            r = best_ratio(s, texts, stacks)
            if r < 0.8:
                miss.append(s)
                b = locate(s, lines)
                if b:
                    boxes[s] = b
            elif r < 1.0:
                near.append(s)
                b = locate(s, lines)
                if b:
                    boxes[s] = b
        corner, in_corner = [], set()
        n = meta.get('n')
        for c, (x0, y0, x1, y1) in corner_boxes(cfg, W, H, n is None or E.page_number_on(cfg, n, total, outline_pages)).items():
            for L in lines:
                cx, cy = (L['x0'] + L['x1']) / 2, (L['y0'] + L['y1']) / 2
                if x0 <= cx <= x1 and y0 <= cy <= y1 and len(E.norm(L['text'])) >= 2:
                    corner.append('%s:%s' % (c, L['text']))
                    in_corner.add(id(L))
        extra = extra_text(strings, lines, in_corner) if strings else []
        stops = extra_stops(strings, texts)
        report[pid] = dict(file=sel[pid], missing=miss, near=near, corner=corner, extra=extra, extra_stop=stops,
                           boxes=boxes, size=[W, H], title_box=title_box(meta.get('title'), lines, W, H, im))
    drifts = drift(report, index)
    for pid, r in report.items():
        r['drift'] = drifts.get(pid, '')
        r['status'] = ('MISS' if r['missing'] else 'CORNER' if r['corner'] else 'EXTRA' if r.get('extra') else
                       'DRIFT' if r['drift'] else 'PUNCT' if r['extra_stop'] else 'NEAR' if r['near'] else 'OK')
    json.dump(dict(sorted(report.items())), open(rp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if not quiet:
        for pid in sorted(report):
            r = report[pid]
            if pid not in paths and not r['drift']:
                continue
            print('%-6s %s %s%s%s%s%s%s' % (r['status'], pid, r['file'],
                  ('  | 缺：' + ' ；'.join(r['missing'])) if r['missing'] else '',
                  ('  | 角落：' + ' ；'.join(r['corner'])) if r['corner'] else '',
                  ('  | 多出：' + ' ；'.join(r['extra'])) if r.get('extra') else '',
                  ('  | 漂移：' + r['drift']) if r['drift'] else '',
                  ('  | 多出句号：' + ' ；'.join(r['extra_stop'])) if r['extra_stop'] else ''))
        bad = [p for p, r in sorted(report.items()) if r['status'] in ('MISS', 'CORNER')]
        print('需重生成：%s' % (','.join(bad) if bad else '无'))
        fixable = [p for p in bad if report[p]['status'] == 'MISS' and not report[p]['corner'] and
                   len(report[p]['missing']) <= 2 and len(report[p]['boxes']) == len(report[p]['missing'])]
        if fixable:
            print('只错一两处字、可先试局部改字（deck fix）：%s' % ','.join(fixable))
        look = [p for p, r in sorted(report.items()) if r['status'] in ('EXTRA', 'DRIFT', 'PUNCT')]
        if look:
            print('看图确认后重生成（多出文字、标题漂移或多出句号）：%s' % ','.join(look))
    return report

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project'); ap.add_argument('prompts'); ap.add_argument('raw'); ap.add_argument('--pages', default='')
    a = ap.parse_args()
    run(a.project, a.prompts, a.raw, [p.strip() for p in a.pages.split(',') if p.strip()] or None)

if __name__ == '__main__':
    main()
