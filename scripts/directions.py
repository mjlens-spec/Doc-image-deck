# -*- coding: utf-8 -*-
"""Stage 2 · Check the three design directions and write the comparison the user chooses from.

Usage: directions.py <project>
Reads 01_设计方向/*/direction.json (schema: references/02_设计方向与生图.md) and checks:
  - exactly three directions;
  - required fields, an imagery_mode from deckenv.IMAGERY_MODES, and for source "reference" at least one existing
    image in refs (paths relative to the direction.json folder or absolute);
  - the three directions are entirely different: every dims entry (typeface, palette, layout, imagery, texture)
    and the imagery_mode differ between every pair; a shared light or dark background colour is reported.
Writes 01_设计方向/方向说明.md (one column per direction). Exit 1 when a check fails.
"""
import os, re, sys, json, glob, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deckenv as E

REQUIRED = ['id', 'name', 'summary', 'source', 'light', 'dark', 'imagery', 'imagery_mode', 'dims', 'tone']


def key(s):
    return re.sub(r'[\s·・,，、/／+＋()（）-]', '', str(s)).lower()


def first_hex(s):
    m = re.search(r'background[^#\n]*(#[0-9a-fA-F]{6})', s or '', re.I)
    return m.group(1).upper() if m else None


def load(proj):
    out = []
    for p in sorted(glob.glob(os.path.join(proj, E.D_DIRS, '*', 'direction.json'))):
        d = json.load(open(p, encoding='utf-8'))
        d['_path'] = p
        out.append(d)
    return out


def ref_paths(d):
    base = os.path.dirname(d['_path'])
    return [r if os.path.isabs(r) else os.path.normpath(os.path.join(base, r)) for r in d.get('refs', [])]


def check(dirs):
    errs, warns = [], []
    if len(dirs) != 3:
        errs.append('需要 3 个方向，现在有 %d 个（01_设计方向/<A|B|C>/direction.json）' % len(dirs))
    for d in dirs:
        tag = d.get('id') or os.path.basename(os.path.dirname(d['_path']))
        miss = [k for k in REQUIRED if not d.get(k)]
        if miss:
            errs.append('方向 %s 缺少字段：%s' % (tag, '、'.join(miss)))
        if d.get('imagery_mode') and d['imagery_mode'] not in E.IMAGERY_MODES:
            errs.append('方向 %s 的 imagery_mode「%s」不在可选值内：%s' % (tag, d['imagery_mode'], '、'.join(E.IMAGERY_MODES)))
        dims = d.get('dims') or {}
        lack = [lab for k, lab in E.DIMS if not dims.get(k)]
        if lack:
            errs.append('方向 %s 的 dims 缺少：%s' % (tag, '、'.join(lack)))
        if d.get('source') and d['source'] not in ('reference', 'original'):
            errs.append('方向 %s 的 source 应为 reference（来自参考）或 original（自行设计）' % tag)
        if d.get('source') == 'reference':
            refs = ref_paths(d)
            if not refs:
                errs.append('方向 %s 来自参考，但 refs 为空' % tag)
            for r in refs:
                if not os.path.exists(r):
                    errs.append('方向 %s 的参考图不存在：%s' % (tag, r))
    for a, b in itertools.combinations(dirs, 2):
        pair = '%s 与 %s' % (a.get('id'), b.get('id'))
        if a.get('imagery_mode') and a.get('imagery_mode') == b.get('imagery_mode'):
            errs.append('%s 的配图方式相同（%s），三个方向要各用一种' % (pair, E.IMAGERY_MODES.get(a['imagery_mode'], ('?',))[0]))
        for k, lab in E.DIMS:
            va, vb = (a.get('dims') or {}).get(k), (b.get('dims') or {}).get(k)
            if va and vb and key(va) == key(vb):
                errs.append('%s 的%s相同（%s），三个方向在五个维度上都要不同' % (pair, lab, va))
        for tone in ('light', 'dark'):
            ha, hb = first_hex(a.get(tone)), first_hex(b.get(tone))
            if ha and ha == hb:
                warns.append('%s 的%s底色相同（%s）' % (pair, '浅色页' if tone == 'light' else '深色页', ha))
    return errs, warns


def comparison(dirs):
    cols = [d.get('id', '?') + ' · ' + d.get('name', '') for d in dirs]
    rows = [('一句话', [d.get('summary', '') for d in dirs]),
            ('来源', ['用户参考（%s）' % '、'.join(os.path.basename(r) for r in ref_paths(d)) if d.get('source') == 'reference'
                    else '自行设计' for d in dirs])]
    rows += [(lab, [(d.get('dims') or {}).get(k, '') for d in dirs]) for k, lab in E.DIMS]
    rows.append(('配图方式', [E.IMAGERY_MODES.get(d.get('imagery_mode'), ('',))[0] for d in dirs]))
    rows.append(('明暗', ['、'.join('%s %s' % ({'cover': '封面', 'section': '章节', 'content': '内容', 'closing': '封底'}.get(k, k),
                                              {'light': '浅', 'dark': '深'}.get(v, v)) for k, v in (d.get('tone') or {}).items())
                        for d in dirs]))
    out = ['# 设计方向说明', '', '| | %s |' % ' | '.join(cols), '|---|' + '---|' * len(cols)]
    for lab, vals in rows:
        out.append('| %s | %s |' % (lab, ' | '.join(str(v).replace('|', '｜').replace('\n', ' ') for v in vals)))
    return '\n'.join(out) + '\n'


def main():
    proj = os.path.abspath(sys.argv[1])
    dirs = load(proj)
    errs, warns = check(dirs)
    for w in warns:
        print('提示：' + w)
    for e in errs:
        print('✗ ' + e)
    if dirs:
        p = os.path.join(proj, E.D_DIRS, '方向说明.md')
        open(p, 'w', encoding='utf-8').write(comparison(dirs))
        print(p)
    if errs:
        sys.exit(1)
    print('三个方向检查通过')


if __name__ == '__main__':
    main()
