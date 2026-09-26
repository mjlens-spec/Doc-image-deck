# -*- coding: utf-8 -*-
"""Stage 4 · Image deck -> editable deck, first pass (before the human review steps).

usage: run_editable.py <workdir> <image_deck.pptx|pdf> <out_editable.pptx> [--outline outline.json]
                       [--draft <copy files...>] [--ref <reference.pdf>]
  --outline : per-page copy from the whiteboard deck (authoritative text)
  --draft   : older copy (prompts, md) used only to settle OCR disagreements
  --ref     : PDF of the image deck, used as the comparison reference (else the page images)
Steps: extract pages -> corpus -> layers (parallel) -> build PPTX -> PowerPoint PDF + comparison -> proof and QA sheets.
"""
import os, sys, json, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')


def run(script, *args, keep=None):
    """Run a step with this Python; stop on failure. keep='first' / 'last' prints only that line of the output."""
    cmd = [sys.executable, os.path.join(HERE, script)] + [str(a) for a in args]
    if keep is None:
        r = subprocess.run(cmd, env=ENV)
    else:
        r = subprocess.run(cmd, env=ENV, capture_output=True, text=True, encoding='utf-8', errors='replace')
        out = r.stdout.strip().splitlines()
        if out:
            print(out[0] if keep == 'first' else out[-1])
        if r.returncode:
            print(r.stderr[-2000:], file=sys.stderr)
    if r.returncode:
        raise SystemExit('%s 失败（退出码 %d）' % (script, r.returncode))


def main():
    a = sys.argv[1:]
    if len(a) < 3:
        raise SystemExit(__doc__)
    work, src, out = (os.path.abspath(x) for x in a[:3])
    outline, ref, draft, rest = '', '', [], a[3:]
    i = 0
    while i < len(rest):
        if rest[i] == '--outline':
            outline = os.path.abspath(rest[i + 1]); i += 2
        elif rest[i] == '--ref':
            ref = os.path.abspath(rest[i + 1]); i += 2
        elif rest[i] == '--draft':
            i += 1
            while i < len(rest) and not rest[i].startswith('--'):
                draft.append(os.path.abspath(rest[i])); i += 1
        else:
            raise SystemExit('unknown option %s' % rest[i])
    os.makedirs(work, exist_ok=True)
    if pages_stale(work, src):
        run('extract_pages.py', src, work)
    if outline:
        run('corpus.py', work, '--outline', outline)
    elif draft:
        run('corpus.py', work, *draft)
    cfg = os.path.join(work, 'config.json')
    if not os.path.exists(cfg):
        c = {'pages': {}, 'replace': {}}
        fams = direction_families(outline)
        if fams:
            c['families'] = fams
            print('按设计方向的字体大类只拟合：%s' % '、'.join(fams), flush=True)
        json.dump(c, open(cfg, 'w', encoding='utf-8'))
    run('run_pages.py', work)
    run('build_pptx.py', work, out)
    pdf = out[:-5] + '.pdf'
    run('verify.py', work, out, pdf, *(['--ref', ref] if ref else []))
    run('proof_sheet.py', work, os.path.join(work, '03_QA', '校对表'), keep='first')
    run('qa_sheet.py', work, pdf, os.path.join(work, '03_QA', '全稿对照'), 8, keep='last')


def direction_families(outline):
    """Font families to fit when the chosen direction declares its type classes (02_生图/prompts/direction.json next to
    the outline's project): only 黑体 / 圆体 -> sans, only 宋体 -> serif; mixed or undeclared -> both (fit decides)."""
    if not outline:
        return None
    dp = os.path.join(os.path.dirname(os.path.dirname(outline)), '02_生图', 'prompts', 'direction.json')
    if not os.path.exists(dp):
        return None
    sys.path.insert(0, os.path.dirname(HERE))
    import deckenv as E
    tc = json.load(open(dp, encoding='utf-8')).get('type_classes') or {}
    fams = {E.TYPE_CLASSES[k][2] for k in tc.values() if k in E.TYPE_CLASSES}
    if None in fams or not fams:
        return None
    return sorted(fams)


def pages_stale(work, src):
    """Extract again when there is no manifest, the image deck is another file or has changed since the extraction
    (a page was regenerated and the deck recomposed), or a page image is gone (deck cleanup deletes them)."""
    mp = os.path.join(work, 'manifest.json')
    if not os.path.exists(mp):
        return True
    m = json.load(open(mp, encoding='utf-8'))
    st = os.stat(src)
    if m.get('source') != os.path.abspath(src) or m.get('source_stat') != [st.st_size, int(st.st_mtime)]:
        return True
    return any('image' in p and not os.path.exists(os.path.join(work, p['image'])) for p in m.get('pages', []))


if __name__ == '__main__':
    main()
