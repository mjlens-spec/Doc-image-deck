# -*- coding: utf-8 -*-
"""CI helper: `deck check` on a runner without PowerPoint and Codex must fail only on those two items."""
import os, sys, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
r = subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'deck.py'), 'check'], capture_output=True, text=True,
                   encoding='utf-8', errors='replace', env=dict(os.environ, PYTHONUTF8='1'))
print(r.stdout)
bad = [l for l in r.stdout.splitlines() if l.startswith('✗')]
unexpected = [l for l in bad if not any(k in l for k in ('Codex', 'PowerPoint', '标定'))]
if unexpected:
    raise SystemExit('unexpected failures:\n' + '\n'.join(unexpected))
print('check report OK: only PowerPoint / Codex missing' if bad else 'check report OK')
