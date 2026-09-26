# -*- coding: utf-8 -*-
"""Stage 2 · Fix one or two wrong strings on a generated slide without regenerating the whole slide.

Usage: fix.py <project> <prompts_dir> <raw_dir> --pages p05[,p09] [--margin 0.5] [--timeout 600]

For each page, textcheck.json (deck textcheck) must list the missing strings with their "boxes": where OCR found the
wrong rendering. The page image goes to Codex image_gen as the edit target with the instruction to change only the
text in those regions; the result is scaled to the original size and ONLY the regions (plus a margin of `--margin`
line heights, feathered) are copied back onto the original, so the rest of the slide stays pixel-identical.
The patched image is saved as the next version pNN_vK.png and textcheck runs again: the new version stays selected
only when the page has fewer missing strings than before and no new extra text; otherwise the previous version is
selected again and the page needs a full regeneration (deck gen --pages). Log: <raw_dir>/fix_log.json.
Composition problems (wrong diagram, text in a reserved corner, style drift) are not for this command.
"""
import os, sys, json, argparse, subprocess, tempfile, datetime
import numpy as np
from PIL import Image, ImageFilter, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deckenv as E
import textcheck

IMAGEGEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'imagegen.py')


def edit_prompt(items, W, H):
    parts = []
    for s, (x0, y0, x1, y1) in items:
        parts.append('- the text in the region from %.0f%% to %.0f%% of the width and from %.0f%% to %.0f%% of the height '
                     '(measured from the top-left corner) must read exactly: "%s"' % (
                         x0 / W * 100, x1 / W * 100, y0 / H * 100, y1 / H * 100, s.replace('"', '”')))
    return ('Edit the attached image, a finished presentation slide. It is the edit target. Change ONLY this text:\n'
            + '\n'.join(parts) +
            '\nKeep the font, size, weight, colour, line breaks, alignment and position of the text that is there now; correct '
            'the characters only. Simplified Chinese, exactly as quoted, no added punctuation. Everything else in the image '
            'stays exactly as it is: the layout, all other text, shapes, lines, colours, background and pictures. Output the '
            'whole slide at the same aspect ratio.\n')


def paste_regions(orig, edited, boxes, margin_px):
    """Copy the boxes (grown by margin_px, feathered) from edited onto orig; returns (image, outside difference)."""
    W, H = orig.size
    ed = edited.convert('RGB').resize((W, H), Image.LANCZOS)
    mask = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(mask)
    for x0, y0, x1, y1 in boxes:
        d.rectangle([max(0, x0 - margin_px), max(0, y0 - margin_px), min(W - 1, x1 + margin_px), min(H - 1, y1 + margin_px)], fill=255)
    soft = mask.filter(ImageFilter.GaussianBlur(max(2, margin_px / 3)))
    a = np.asarray(orig.convert('RGB')).astype(np.int16)
    b = np.asarray(ed).astype(np.int16)
    outside = np.asarray(mask) == 0
    diff = float(np.abs(a - b).mean(axis=2)[outside].mean()) if outside.any() else 0.0
    return Image.composite(ed, orig.convert('RGB'), soft), diff


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project'); ap.add_argument('prompts'); ap.add_argument('raw')
    ap.add_argument('--pages', required=True); ap.add_argument('--margin', type=float, default=0.5)
    ap.add_argument('--timeout', type=int, default=600)
    a = ap.parse_args()
    raw = os.path.abspath(a.raw)
    rep_p = os.path.join(raw, 'textcheck.json')
    if not os.path.exists(rep_p):
        raise SystemExit('先运行 deck textcheck，textcheck.json 里要有错字的位置')
    report = json.load(open(rep_p, encoding='utf-8'))
    sel_p = os.path.join(raw, 'selected.json')
    sel = json.load(open(sel_p, encoding='utf-8'))
    log_p = os.path.join(raw, 'fix_log.json')
    log = json.load(open(log_p, encoding='utf-8')) if os.path.exists(log_p) else []
    for pid in [p.strip() for p in a.pages.split(',') if p.strip()]:
        r = report.get(pid)
        if not r or r.get('file') != sel.get(pid):
            print('%s：textcheck.json 不是当前选定版本的结果，先重跑 deck textcheck' % pid)
            continue
        items = [(s, r['boxes'][s]) for s in r.get('missing', []) if s in r.get('boxes', {})]
        if not items:
            print('%s：没有可定位的错字（整条缺失或没有 MISS），用 deck gen --pages %s 重生成' % (pid, pid))
            continue
        before = sel[pid]
        src = os.path.join(raw, before)
        orig = Image.open(src)
        W, H = orig.size
        tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False).name
        p = subprocess.run([sys.executable, IMAGEGEN, '-', '-o', tmp, '--size', '16:9', '--timeout', str(a.timeout),
                            '--overwrite', '--ref', src], input=edit_prompt(items, W, H), capture_output=True, text=True,
                           encoding='utf-8', errors='replace', env=dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8'))
        if p.returncode != 0 or not os.path.exists(tmp) or os.path.getsize(tmp) < 50000:
            print('%s：改图调用失败：%s' % (pid, ' | '.join((p.stderr or '').strip().splitlines()[-2:])))
            continue
        edited = Image.open(tmp)
        lh = np.median([b[3] - b[1] for _, b in items])
        img, diff = paste_regions(orig, edited, [b for _, b in items], a.margin * lh)
        k = next(i for i in range(1, 999) if not os.path.exists(os.path.join(raw, '%s_v%d.png' % (pid, i))))
        new = '%s_v%d.png' % (pid, k)
        img.save(os.path.join(raw, new))
        os.remove(tmp)
        sel[pid] = new
        json.dump(dict(sorted(sel.items())), open(sel_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        after = textcheck.run(a.project, a.prompts, raw, [pid], quiet=True)[pid]
        better = len(after['missing']) < len(r['missing']) and len(after.get('extra', [])) <= len(r.get('extra', []))
        if not better:
            sel[pid] = before
            json.dump(dict(sorted(sel.items())), open(sel_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            textcheck.run(a.project, a.prompts, raw, [pid], quiet=True)
        log.append(dict(page=pid, time=datetime.datetime.now().isoformat(timespec='seconds'), before=before, after=new,
                        strings=[s for s, _ in items], outside_diff=round(diff, 2), missing_after=after['missing'],
                        kept=better))
        print('%s：%s → %s，改图区域外的像素差 %.1f（0–255），核对后%s' % (
            pid, before, new, diff, '仍缺：' + '、'.join(after['missing']) if after['missing'] else '文字齐全',)
              + ('' if better else '；没有改善，恢复选用 %s，改用 deck gen --pages %s 重生成' % (before, pid)))
    json.dump(log, open(log_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
