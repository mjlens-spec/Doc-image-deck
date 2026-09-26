# -*- coding: utf-8 -*-
"""Stage 2 · Generate slide images in parallel through the Codex built-in image_gen (ChatGPT plan, no API key).

Usage: gen_batch.py <prompts_dir> --out <raw_dir> [--pages p01,p02] [--ref-light img] [--ref-dark img]
                    [--skeleton-refs] [--parallel 4] [--retries 1] [--timeout 900]

Each page is one `codex exec` call (scripts/imagegen.py); about 2 minutes per image, 4 in parallel is stable.
Outputs <raw_dir>/pNN_vK.png (K = next free version), appends to gen_log.json and points selected.json at the
newest successful version of every page generated in this run.
Style references are optional: pages use --ref-dark or --ref-light by their tone in index.json; the note in front of
the prompt limits them to style, so the pages do not copy the sample's composition. When the direction
was built from a user's reference (<prompts_dir>/direction.json "refs"), those images are attached as well, up to
three images per call.
--skeleton-refs: content slides whose composition skeleton (index.json "skeleton") is used on two or more slides get,
as their first reference, an already generated slide of the deck with the same skeleton (its grid, header and type
sizes, not its content). Skeletons without such a slide yet are generated first, one slide each, then the rest.
A layout guide (index.json "guide", from deck prompts --corner-guide) is attached ahead of the references.
"""
import os, sys, json, time, argparse, subprocess, datetime
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
IMAGEGEN = os.path.join(HERE, 'imagegen.py')
REF_NOTE = ('The attached image(s) are STYLE REFERENCES ONLY: match their colour palette, typography and type weights, title '
            'position and size, margins and overall finish. Do NOT copy their panels, bands, frames or decorative shapes (this '
            'slide gets its own, described below), their text, their content, their '
            'composition, their diagram type, their picture subject or their ornaments and decorative details: they are other slides '
            'of the same deck, and this slide '
            'must look different from them. Compose this slide as described below.\n\n')
SKELETON_NOTE = ('The FIRST attached image is another slide of this deck with the same kind of composition: follow its grid, '
                 'margins, header and title treatment, type sizes and the way this kind of layout is built. Do NOT copy its '
                 'text, its content, its diagram shapes or its picture subject: this slide carries different content, drawn '
                 'as described below. Any further attached image is a style reference only (palette, type, finish).\n\n')
GUIDE_NOTE = ('One attached image is a LAYOUT GUIDE, not a style reference: a plain white image with pale-red rectangles. '
              'The pale-red rectangles mark areas of the slide that must stay empty (no text, no numbers, no important '
              'elements). Do not draw the rectangles, do not use the white background or the red colour.\n\n')
MAX_REFS = 3

CONTENT_KINDS = ('content', 'summary', 'agenda', 'appendix')

def plan_skeleton_refs(index, want, existing):
    """({skeleton: image of an existing slide with it}, [slides to generate first]) for --skeleton-refs. existing:
    {pid: image path} of slides already generated. A skeleton used by two or more content slides gets as anchor the
    first such slide that is not being regenerated; when there is none, the first wanted slide with it goes first."""
    order = sorted(index, key=lambda p: index[p].get('n', 0))
    by_sk = {}
    for p in order:
        if index[p].get('skeleton') and index[p].get('kind', 'content') in CONTENT_KINDS:
            by_sk.setdefault(index[p]['skeleton'], []).append(p)
    anchors, first = {}, []
    for sk, ps in by_sk.items():
        if len(ps) < 2:
            continue
        done = [p for p in ps if p not in want and p in existing]
        if done:
            anchors[sk] = existing[done[0]]
        else:
            f = next((p for p in ps if p in want), None)
            if f:
                first.append(f)
    return anchors, first

def next_version(raw, pid):
    k = 1
    while os.path.exists(os.path.join(raw, '%s_v%d.png' % (pid, k))):
        k += 1
    return k

def run_one(job):
    pid, prompt_file, out, refs, timeout, retries, note = job
    prompt = open(prompt_file, encoding='utf-8').read()
    prompt = note + prompt
    for attempt in range(1, retries + 2):
        cmd = [sys.executable, IMAGEGEN, '-', '-o', out, '--size', '16:9', '--timeout', str(timeout), '--overwrite']
        for r in refs:
            cmd += ['--ref', r]
        t0 = time.time()
        p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding='utf-8', errors='replace',
                           env=dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8'))
        ok = p.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 50000
        print('%s attempt %d rc=%d %s %.0fs' % (os.path.basename(out), attempt, p.returncode, 'OK' if ok else 'FAIL', time.time() - t0), flush=True)
        if ok:
            return dict(page=pid, file=os.path.basename(out), ok=True, seconds=round(time.time() - t0), ref=' | '.join(refs))
        err = (p.stderr or '').strip().splitlines()[-3:]
    return dict(page=pid, file=os.path.basename(out), ok=False, error=' | '.join(err), ref=' | '.join(refs))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('prompts'); ap.add_argument('--out', required=True); ap.add_argument('--pages', default='')
    ap.add_argument('--ref-light', default=''); ap.add_argument('--ref-dark', default='')
    ap.add_argument('--parallel', type=int, default=4); ap.add_argument('--retries', type=int, default=1)
    ap.add_argument('--timeout', type=int, default=900)
    ap.add_argument('--skeleton-refs', action='store_true')
    a = ap.parse_args()
    index = json.load(open(os.path.join(a.prompts, 'index.json'), encoding='utf-8'))
    want = [p.strip() for p in a.pages.split(',') if p.strip()] or sorted(index)
    dp = os.path.join(a.prompts, 'direction.json')
    dir_refs = json.load(open(dp, encoding='utf-8')).get('refs', []) if os.path.exists(dp) else []
    missing = [r for r in dir_refs if not os.path.exists(r)]
    if missing:
        raise SystemExit('方向参考图不存在：%s' % '，'.join(missing))
    os.makedirs(a.out, exist_ok=True)
    sel_p = os.path.join(a.out, 'selected.json')
    sel = json.load(open(sel_p, encoding='utf-8')) if os.path.exists(sel_p) else {}
    anchors, wave1 = plan_skeleton_refs(index, want, {p: os.path.join(a.out, f) for p, f in sel.items()
                                                      if os.path.exists(os.path.join(a.out, f))}) if a.skeleton_refs else ({}, [])

    def job(pid, anchor=None):
        tone = index[pid]['tone']
        ref = a.ref_dark if tone == 'dark' and a.ref_dark else a.ref_light
        refs = ([os.path.abspath(anchor)] if anchor else []) + ([os.path.abspath(ref)] if ref else []) + dir_refs
        refs = refs[:MAX_REFS]
        note = (SKELETON_NOTE if anchor else REF_NOTE) if refs else ''
        g = index[pid].get('guide')
        if g and os.path.exists(os.path.join(a.prompts, g)):
            refs = [os.path.abspath(os.path.join(a.prompts, g))] + refs
            note = GUIDE_NOTE + note
        out = os.path.join(a.out, '%s_v%d.png' % (pid, next_version(a.out, pid)))
        open(out, 'wb').close()                       # reserve the version number for parallel jobs
        return (pid, os.path.join(a.prompts, index[pid]['file']), out, refs, a.timeout, a.retries, note)

    def batch(pids, anchor_of):
        jobs = [job(p, anchor_of(p)) for p in pids]
        with ThreadPoolExecutor(max(1, a.parallel)) as ex:
            res = list(ex.map(run_one, jobs))
        for r, j in zip(res, jobs):
            if not r['ok'] and os.path.exists(j[2]) and os.path.getsize(j[2]) == 0:
                os.remove(j[2])
        return res, jobs

    res, jobs = [], []
    if wave1:
        print('先生成每种骨架的第一页：%s' % ','.join(wave1), flush=True)
        r1, j1 = batch(wave1, lambda p: None)
        res += r1; jobs += j1
        for r, j in zip(r1, j1):
            if r['ok']:
                anchors[index[r['page']]['skeleton']] = j[2]
    rest = [p for p in want if p not in wave1]
    r2, j2 = batch(rest, lambda p: anchors.get(index[p].get('skeleton')) if index[p].get('kind', 'content') in CONTENT_KINDS else None)
    res += r2; jobs += j2
    log_p = os.path.join(a.out, 'gen_log.json')
    log = json.load(open(log_p, encoding='utf-8')) if os.path.exists(log_p) else []
    stamp = datetime.datetime.now().isoformat(timespec='seconds')
    log += [dict(r, time=stamp) for r in res]
    json.dump(log, open(log_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for r in res:
        if r['ok']:
            sel[r['page']] = r['file']
    json.dump(dict(sorted(sel.items())), open(sel_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    bad = [r['page'] for r in res if not r['ok']]
    print('done: %d ok, %d failed %s' % (len(res) - len(bad), len(bad), bad))
    sys.exit(1 if bad else 0)

if __name__ == '__main__':
    main()
