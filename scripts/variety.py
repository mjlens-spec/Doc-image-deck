# -*- coding: utf-8 -*-
"""Stage 2 QA · How alike the generated slides look (同质化检查).

Usage: variety.py <project> [<raw_dir>] [--threshold 0.62]
Reads <raw_dir>/selected.json (default 02_生图/raw). Every slide becomes a layout signature (edge map of a 96 x 54 grey
thumbnail, compared by correlation) and a colour signature (hue x saturation histogram, compared by intersection).
Slides of one design system share their colours (0.9+), so the layout similarity is the measure; colour is reported
only. Writes <raw_dir>/../同质化检查.md: the mean layout similarity (initial reading from four 13–15 slide decks: 0.33–0.42
for decks that read as varied, 0.47–0.49 for decks that read as samey; above 0.45 = leaning uniform), the most similar
pairs and the slides whose layout is close (>= threshold) to another slide. Regenerate those with another variant
(visual.variant) or skeleton. Cover, section and closing slides are left out.
"""
import os, sys, json, argparse, itertools
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deckenv as E


def signature(path):
    im = Image.open(path).convert('RGB').resize((96, 54), Image.LANCZOS)
    g = np.asarray(im.convert('L'), np.float32) / 255.0
    gx = np.abs(np.diff(g, axis=1))[:-1, :]
    gy = np.abs(np.diff(g, axis=0))[:, :-1]
    edges = np.sqrt(gx ** 2 + gy ** 2)
    lay = np.asarray(Image.fromarray((edges * 255).astype(np.uint8)).resize((48, 27), Image.BILINEAR), np.float32).ravel()
    lay = lay - lay.mean()
    lay /= (np.linalg.norm(lay) + 1e-6)
    hsv = np.asarray(im.convert('HSV'), np.float32).reshape(-1, 3)
    h = (hsv[:, 0] / 256.0 * 12).astype(int)
    sat = np.clip((hsv[:, 1] / 256.0 * 3).astype(int), 0, 2)
    val = np.clip((hsv[:, 2] / 256.0 * 3).astype(int), 0, 2)
    hist = np.bincount(np.where(sat == 0, 36 + val, h * 3 + sat), minlength=39).astype(np.float32)
    return lay, hist / hist.sum()


def similarity(a, b):
    lay = float(np.dot(a[0], b[0]))
    col = float(np.minimum(a[1], b[1]).sum())
    return 0.6 * max(0.0, lay) + 0.4 * col, lay, col


def run(proj, raw=None, threshold=0.62):
    raw = os.path.abspath(raw or os.path.join(proj, E.D_GEN, 'raw'))
    sel = json.load(open(os.path.join(raw, 'selected.json'), encoding='utf-8'))
    outline = E.load_outline(proj)
    kinds = {pid: p.get('kind', 'content') for pid, p in zip(E.page_ids(outline), outline['pages'])}
    pids = [p for p in sorted(sel) if kinds.get(p, 'content') not in ('cover', 'closing', 'section')]
    sig = {p: signature(os.path.join(raw, sel[p])) for p in pids}
    pairs = []
    for a, b in itertools.combinations(pids, 2):
        _, lay, col = similarity(sig[a], sig[b])
        pairs.append((lay, a, b, lay, col))
    pairs.sort(reverse=True)
    mean = float(np.mean([p[0] for p in pairs])) if pairs else 0.0
    close = {}
    for s, a, b, _, _ in pairs:
        if s >= threshold:
            close.setdefault(a, []).append(b); close.setdefault(b, []).append(a)
    flagged = sorted(close)
    out = ['# 同质化检查', '', '%d 页内容页（不含封面、封底、章节页）；版面相似度两两均值 %.3f（%s）；单对阈值 %.2f。' % (
               len(pids), mean, '偏同质，考虑换骨架或变化项' if mean > 0.45 else '正常', threshold), '',
           '版面相似度按缩略图的边缘分布计算，0–1。同一套风格的页面颜色本来接近（颜色一栏通常在 0.9 以上），只作参考。'
           '均值的参考值来自 4 套 13–15 页的测试稿：看起来有变化的 0.33–0.42，看起来雷同的 0.47–0.49。', '',
           '## 最相似的 8 对', '', '| 页 | 页 | 版面 | 颜色 |', '|---|---|---|---|']
    out += ['| %s | %s | %.3f | %.3f |' % (a.upper(), b.upper(), lay, col) for s, a, b, lay, col in pairs[:8]]
    out += ['', '## 版面相近的页（重生成时换变化项或骨架）', '']
    out += ['- %s：与 %s 相似' % (p.upper(), '、'.join(x.upper() for x in sorted(close[p]))) for p in flagged] or ['- 无']
    path = os.path.join(os.path.dirname(raw), '同质化检查.md')
    open(path, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    return mean, pairs, flagged, path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project'); ap.add_argument('raw', nargs='?'); ap.add_argument('--threshold', type=float, default=0.62)
    a = ap.parse_args()
    mean, pairs, flagged, path = run(os.path.abspath(a.project), a.raw, a.threshold)
    print('版面相似度均值 %.3f%s' % (mean, '（偏同质）' if mean > 0.45 else ''))
    for s, x, y, lay, col in pairs[:5]:
        print('  %s–%s 版面 %.3f，颜色 %.3f' % (x, y, lay, col))
    print('版面相近的页：%s' % (','.join(flagged) or '无'))
    print(path)


if __name__ == '__main__':
    main()
