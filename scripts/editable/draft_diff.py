# -*- coding: utf-8 -*-
"""List where the final page text differs in wording from the draft copy (corpus), after all corrections.
Usage: draft_diff.py <workdir>   -> Markdown bullet list on stdout"""
import os, sys, json, re, difflib
sys.argv = [sys.argv[0], os.path.abspath(sys.argv[1])]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import layers as L
work = L.WORK
corpus = L.CorpusSet(json.load(open(os.path.join(work, 'corpus.json'), encoding='utf-8')))
W = lambda x: re.sub(r'[^一-鿿A-Za-z0-9]', '', x)
man = json.load(open(os.path.join(work, 'manifest.json')))
for pg in man['pages']:
    d = json.load(open(os.path.join(work, '02_分层', pg['pid'], 'layers.json')))
    for p in d['paragraphs']:
        for l in p['lines']:
            m, _ = corpus.match(pg['pid'], l['text'])
            if not m:
                continue
            a, b = W(l['text']), W(m[0])
            if a == b:
                continue
            ops = [(t, a[a0:a1], b[b0:b1]) for t, a0, a1, b0, b1 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if t != 'equal']
            print('- %s「%s」：%s' % (pg['pid'].upper(), l['text'], '；'.join('页面「%s」/ 旧稿「%s」' % (x or '无', y or '无') for _, x, y in ops)))
