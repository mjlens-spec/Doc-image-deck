# -*- coding: utf-8 -*-
"""Stage 2 QA · OCR every generated slide and check each verbatim string of its prompt, and that the reserved
logo / page-number corners hold no text. A string may sit on one OCR line, two adjacent lines, or up to four lines
stacked in one column (text wrapped inside a diagram node).

Usage: textcheck.py <project> <prompts_dir> <raw_dir> [--pages p01,p02]
Uses <raw_dir>/selected.json. Writes <raw_dir>/textcheck.json and prints one line per page:
  OK    all strings found
  NEAR  every string found or nearly found (ratio >= 0.8): usually OCR noise, check the image
  MISS  at least one string missing: regenerate the page
  CORNER text found inside a reserved corner: regenerate or move the logo
  PUNCT a line ends with 。 although its string has no full stop (the image model added one): look, then regenerate
"""
import os, sys, json, argparse, subprocess, difflib, tempfile
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deckenv as E

def ocr_many(paths):
    lst = tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False, encoding='utf-8')
    lst.write('\n'.join(paths)); lst.close()
    out = E.hostos.run_ocr(['--batch', lst.name])
    os.remove(lst.name)
    return json.loads(out or '{}')

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
        m = sum(b.size for b in difflib.SequenceMatcher(None, t, c, autojunk=False).get_matching_blocks())
        best = max(best, m / float(len(t)))
    return best

def column_stacks(lines, depth=4):
    """Text of up to `depth` OCR lines stacked in one column (a string wrapped inside a narrow diagram node or card):
    each next line starts just below the previous one and overlaps it horizontally by at least half the narrower width.
    OCR output order interleaves columns, so adjacent entries of the line list miss these."""
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
            if len(chain) >= 3:
                out.append(''.join(M['text'] for M in chain))
    return out

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

def corner_boxes(cfg, W, H):
    boxes = {}
    pn = cfg.get('page_number') or {}
    corners = [lg.get('corner', 'bl') for lg in cfg['logos']] + ([pn['corner']] if pn.get('corner') else [])
    for c in set(corners):
        w = 0.20 * W if c.endswith('l') else 0.12 * W
        x0 = 0 if c.endswith('l') else W - w
        y0 = H * 0.91 if c.startswith('b') else 0
        boxes[c] = (x0, y0, x0 + w, y0 + H * 0.09)
    return boxes

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project'); ap.add_argument('prompts'); ap.add_argument('raw'); ap.add_argument('--pages', default='')
    a = ap.parse_args()
    E.ensure_runtime(need_ocr=True)
    cfg = E.load_project(a.project)
    index = json.load(open(os.path.join(a.prompts, 'index.json'), encoding='utf-8'))
    sel = json.load(open(os.path.join(a.raw, 'selected.json'), encoding='utf-8'))
    want = [p.strip() for p in a.pages.split(',') if p.strip()] or sorted(sel)
    paths = {pid: os.path.abspath(os.path.join(a.raw, sel[pid])) for pid in want if pid in sel}
    res = ocr_many(list(paths.values()))
    report = {}
    for pid, path in paths.items():
        lines = res.get(path, [])
        texts = [L['text'] for L in lines]
        stacks = column_stacks(lines)
        W, H = Image.open(path).size
        miss, near = [], []
        for s in index.get(pid, {}).get('strings', []):
            if len(E.norm(s)) < 2:
                continue
            r = best_ratio(s, texts, stacks)
            if r < 0.8:
                miss.append(s)
            elif r < 1.0:
                near.append(s)
        corner = []
        for c, (x0, y0, x1, y1) in corner_boxes(cfg, W, H).items():
            for L in lines:
                cx, cy = (L['x0'] + L['x1']) / 2, (L['y0'] + L['y1']) / 2
                if x0 <= cx <= x1 and y0 <= cy <= y1 and len(E.norm(L['text'])) >= 2:
                    corner.append('%s:%s' % (c, L['text']))
        stops = extra_stops(index.get(pid, {}).get('strings', []), texts)
        status = 'MISS' if miss else 'CORNER' if corner else 'PUNCT' if stops else 'NEAR' if near else 'OK'
        report[pid] = dict(file=sel[pid], status=status, missing=miss, near=near, corner=corner, extra_stop=stops)
        print('%-6s %s %s%s%s%s' % (status, pid, sel[pid],
              ('  | 缺：' + ' ；'.join(miss)) if miss else '', ('  | 角落：' + ' ；'.join(corner)) if corner else '',
              ('  | 多出句号：' + ' ；'.join(stops)) if stops else ''))
    json.dump(report, open(os.path.join(a.raw, 'textcheck.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    bad = [p for p, r in report.items() if r['status'] in ('MISS', 'CORNER')]
    print('需重生成：%s' % (','.join(bad) if bad else '无'))
    stop = [p for p, r in report.items() if r['status'] == 'PUNCT']
    if stop:
        print('多出句号（看图确认后重生成）：%s' % ','.join(stop))

if __name__ == '__main__':
    main()
