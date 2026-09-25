# -*- coding: utf-8 -*-
"""Run layers.py over pages with parallel workers.

usage: run_pages.py <workdir> [pid ...]        (no pids = every page in manifest.json)
Workers: DOC_IMAGE_DECK_WORKERS, default 2. LaMa takes about 1.5 GB per worker: on a 16 GB Mac (Apple GPU) more than
2 exhausts memory; on Windows without an NVIDIA GPU LaMa runs on the CPU and 2 workers keep most cores busy.
Logs: <workdir>/tmp/run_<k>.log. Prints one summary line per page and the first errors.
"""
import os, re, sys, json, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    work = os.path.abspath(sys.argv[1])
    pids = sys.argv[2:] or [p['pid'] for p in json.load(open(os.path.join(work, 'manifest.json'), encoding='utf-8'))['pages']]
    n = max(1, min(int(os.environ.get('DOC_IMAGE_DECK_WORKERS', '2')), len(pids)))
    os.makedirs(os.path.join(work, 'tmp'), exist_ok=True)
    groups = [pids[k::n] for k in range(n)]
    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
    procs, logs = [], []
    for k, g in enumerate(groups):
        log = os.path.join(work, 'tmp', 'run_%d.log' % k)
        logs.append(log)
        procs.append(subprocess.Popen([sys.executable, os.path.join(HERE, 'layers.py'), work] + g,
                                      stdout=open(log, 'w', encoding='utf-8'), stderr=subprocess.STDOUT, env=env))
    codes = [p.wait() for p in procs]
    lines, errs = [], []
    for log in logs:
        text = open(log, encoding='utf-8', errors='replace').read().splitlines()
        lines += [l for l in text if re.match(r'^p\d', l)]
        for i, l in enumerate(text):
            if re.search(r'traceback|error', l, re.I) and 'warn' not in l.lower():
                errs += text[i:i + 5]
    for l in sorted(lines):
        print(l)
    for l in errs[:20]:
        print(l)
    sys.exit(max(codes) if codes else 0)


if __name__ == '__main__':
    main()
