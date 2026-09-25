# -*- coding: utf-8 -*-
"""Step 2 (optional) · Build a reference-copy corpus used to correct OCR (dropped / misread characters).

Usage: corpus.py <workdir> <file-or-folder> [...]
       corpus.py <workdir> --outline <outline.json>   (per-page copy from the whiteboard deck; authoritative)
Reads every .txt / .md / .json under the given paths and keeps short text segments (lines, table
cells, quoted strings). Output: <workdir>/corpus.json
"""
import os, re, sys, json
work = sys.argv[1]
if len(sys.argv) > 3 and sys.argv[2] == '--outline':
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    import deckenv as E
    outline = json.load(open(sys.argv[3], encoding='utf-8'))
    pages = {pid: [t for _, t in E.page_strings(pg)] for pid, pg in zip(E.page_ids(outline), outline['pages'])}
    json.dump({'authoritative': True, '_pages': pages, '_all': []}, open(os.path.join(work, 'corpus.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=0)
    print('pages:', len(pages), 'strings:', sum(len(v) for v in pages.values()))
    sys.exit(0)
segs = set()
def add(s):
    s = re.sub(r'\*\*|__|`|^#+\s*|^\s*[-*+]\s+|^\s*\d+[.、)]\s+', '', s.strip()).strip()
    s = s.strip('"“”\'')
    if 2 <= len(s) <= 160 and re.search(r'[一-鿿A-Za-z0-9]', s):
        segs.add(s)
for root in sys.argv[2:]:
    files = [root] if os.path.isfile(root) else [os.path.join(d, f) for d, _, fs in os.walk(root) for f in fs]
    for f in files:
        if not f.lower().endswith(('.txt', '.md', '.json')):
            continue
        try:
            t = open(f, encoding='utf-8').read()
        except Exception:
            continue
        if f.endswith('.json'):
            t = t.encode().decode('unicode_escape', 'ignore') if '\\u' in t else t
            t = t.replace('\\n', '\n')
        for line in t.splitlines():
            if '|' in line:
                for cell in line.split('|'):
                    add(cell)
            add(line)
            for q in re.findall(r'[“"「]([^”"」]{2,80})[”"」]', line):
                add(q)
            for part in re.split(r'[；;]', line):
                add(part)
segs = sorted(segs)
json.dump(segs, open(os.path.join(work, 'corpus.json'), 'w'), ensure_ascii=False, indent=0)
print('segments:', len(segs))
