# -*- coding: utf-8 -*-
"""Stage 2 · Generate slide images in parallel through the Codex built-in image_gen (ChatGPT plan, no API key).

Usage: gen_batch.py <prompts_dir> --out <raw_dir> [--pages p01,p02] [--ref-light img] [--ref-dark img]
                    [--parallel 4] [--retries 1] [--timeout 900]

Each page is one `codex exec` call (scripts/imagegen.py); about 2 minutes per image, 4 in parallel is stable.
Outputs <raw_dir>/pNN_vK.png (K = next free version), appends to gen_log.json and points selected.json at the
newest successful version of every page generated in this run.
Style references are optional: pages use --ref-dark or --ref-light by their tone in index.json. When the direction
was built from a user's reference (<prompts_dir>/direction.json "refs"), those images are attached as well, up to
three images per call.
"""
import os, sys, json, time, argparse, subprocess, datetime
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
IMAGEGEN = os.path.join(HERE, 'imagegen.py')
REF_NOTE = ('The attached image(s) are STYLE REFERENCES ONLY: match their colour palette, typography and type weights, header '
            'treatment, margins, rules, imagery treatment and overall finish. Do NOT copy their text, their content or their '
            'exact layout; compose this slide as described below.\n\n')
MAX_REFS = 3

def next_version(raw, pid):
    k = 1
    while os.path.exists(os.path.join(raw, '%s_v%d.png' % (pid, k))):
        k += 1
    return k

def run_one(job):
    pid, prompt_file, out, refs, timeout, retries = job
    prompt = open(prompt_file, encoding='utf-8').read()
    if refs:
        prompt = REF_NOTE + prompt
    for attempt in range(1, retries + 2):
        cmd = [sys.executable, IMAGEGEN, '-', '-o', out, '--size', '16:9', '--timeout', str(timeout), '--overwrite']
        for r in refs:
            cmd += ['--ref', r]
        t0 = time.time()
        p = subprocess.run(cmd, input=prompt, capture_output=True, text=True)
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
    a = ap.parse_args()
    index = json.load(open(os.path.join(a.prompts, 'index.json'), encoding='utf-8'))
    want = [p.strip() for p in a.pages.split(',') if p.strip()] or sorted(index)
    dp = os.path.join(a.prompts, 'direction.json')
    dir_refs = json.load(open(dp, encoding='utf-8')).get('refs', []) if os.path.exists(dp) else []
    missing = [r for r in dir_refs if not os.path.exists(r)]
    if missing:
        raise SystemExit('方向参考图不存在：%s' % '，'.join(missing))
    os.makedirs(a.out, exist_ok=True)
    jobs = []
    for pid in want:
        tone = index[pid]['tone']
        ref = a.ref_dark if tone == 'dark' and a.ref_dark else a.ref_light
        refs = ([os.path.abspath(ref)] if ref else []) + dir_refs
        out = os.path.join(a.out, '%s_v%d.png' % (pid, next_version(a.out, pid)))
        open(out, 'wb').close()                       # reserve the version number for parallel jobs
        jobs.append((pid, os.path.join(a.prompts, index[pid]['file']), out, refs[:MAX_REFS], a.timeout, a.retries))
    with ThreadPoolExecutor(max(1, a.parallel)) as ex:
        res = list(ex.map(run_one, jobs))
    for r, j in zip(res, jobs):
        if not r['ok'] and os.path.exists(j[2]) and os.path.getsize(j[2]) == 0:
            os.remove(j[2])
    log_p = os.path.join(a.out, 'gen_log.json')
    log = json.load(open(log_p, encoding='utf-8')) if os.path.exists(log_p) else []
    stamp = datetime.datetime.now().isoformat(timespec='seconds')
    log += [dict(r, time=stamp) for r in res]
    json.dump(log, open(log_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    sel_p = os.path.join(a.out, 'selected.json')
    sel = json.load(open(sel_p, encoding='utf-8')) if os.path.exists(sel_p) else {}
    for r in res:
        if r['ok']:
            sel[r['page']] = r['file']
    json.dump(dict(sorted(sel.items())), open(sel_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    bad = [r['page'] for r in res if not r['ok']]
    print('done: %d ok, %d failed %s' % (len(res) - len(bad), len(bad), bad))
    sys.exit(1 if bad else 0)

if __name__ == '__main__':
    main()
