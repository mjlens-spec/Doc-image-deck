# -*- coding: utf-8 -*-
"""Stage 2 · Check the three design directions and write the comparison the user chooses from.

Usage: directions.py <project>
Reads 01_设计方向/*/direction.json (schema: references/02_设计方向与生图.md) and checks:
  - the brand VI research 01_设计方向/品牌调研.md is complete (brand.py);
  - exactly three directions, each with "brand_fit" (how it uses the brand colours, logo and style);
  - required fields, an imagery_mode from deckenv.IMAGERY_MODES, and for source "reference" at least one existing
    image in refs (paths relative to the direction.json folder or absolute);
  - the three directions are entirely different: every dims entry (typeface, palette, layout, imagery, texture,
    diagram) and the imagery_mode differ between every pair; the axes (deckenv.AXES: one fixed option each for typeface,
    layout, texture and diagram language) differ between every pair and color_strategy takes at least two values;
    a shared light or dark background colour is reported;
  - each direction has its own cover {"layout", "motif"}: the three cover layouts and cover motifs differ (the cover
    no longer comes from the outline's layout_hint / image_hint, so the directions do not share one composition);
  - icons (deckenv.ICON_POLICIES, default none), temperature (safe = the category's usual look, distinct = away
    from it; three safe directions fail) and allow (keys of deckenv.BASE_AVOID) take known values.
Writes 01_设计方向/方向说明.md (one column per direction). Exit 1 when a check fails.
--samples: after the samples are generated (01_设计方向/<X>/prompts + samples), OCR-check them (textcheck) and add
a 样张核对 table to 方向说明.md.
"""
import os, re, sys, json, glob, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deckenv as E
import brand

REQUIRED = ['id', 'name', 'summary', 'source', 'brand_fit', 'light', 'dark', 'imagery', 'imagery_mode', 'dims', 'axes',
            'cover', 'temperature', 'tone']


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
        axes = d.get('axes') or {}
        for k, (lab, opts) in E.AXES.items():
            if axes and axes.get(k) not in opts:
                errs.append('方向 %s 的 axes.%s（%s）要从这些值里选：%s' % (tag, k, lab, '、'.join(opts)))
        cover = d.get('cover') or {}
        if d.get('cover') and not (isinstance(cover, dict) and cover.get('layout') and cover.get('motif')):
            errs.append('方向 %s 的 cover 要写 layout（封面构图）和 motif（封面主体）' % tag)
        if d.get('icons') and d['icons'] not in E.ICON_POLICIES:
            errs.append('方向 %s 的 icons 要从这些值里选：%s' % (tag, '、'.join(E.ICON_POLICIES)))
        if d.get('temperature') and d['temperature'] not in E.TEMPERATURES:
            errs.append('方向 %s 的 temperature 要从这些值里选：%s' % (tag, '、'.join(E.TEMPERATURES)))
        bad = [x for x in d.get('allow') or [] if x not in E.BASE_AVOID]
        if bad:
            errs.append('方向 %s 的 allow 只能放开这些项：%s（写了 %s）' % (tag, '、'.join(E.BASE_AVOID), '、'.join(bad)))
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
        for k in E.AXES_DISTINCT:
            va, vb = (a.get('axes') or {}).get(k), (b.get('axes') or {}).get(k)
            if va and va == vb:
                errs.append('%s 的%s相同（%s），三个方向要各选一种' % (pair, E.AXES[k][0], E.AXES[k][1].get(va, va)))
        ca, cb = a.get('cover') or {}, b.get('cover') or {}
        if isinstance(ca, dict) and isinstance(cb, dict):
            for k, lab in (('layout', '封面构图'), ('motif', '封面主体')):
                if ca.get(k) and cb.get(k) and key(ca[k]) == key(cb[k]):
                    errs.append('%s 的%s相同（%s）' % (pair, lab, ca[k]))
        for tone in ('light', 'dark'):
            ha, hb = first_hex(a.get(tone)), first_hex(b.get(tone))
            if ha and ha == hb:
                warns.append('%s 的%s底色相同（%s）' % (pair, '浅色页' if tone == 'light' else '深色页', ha))
    strategies = {(d.get('axes') or {}).get('color_strategy') for d in dirs} - {None}
    if len(dirs) == 3 and all((d.get('axes') or {}).get('color_strategy') for d in dirs) and len(strategies) < 2:
        errs.append('三个方向的配色策略都是「%s」：至少用两种（克制、一色主导、多色、满铺）' % E.AXES['color_strategy'][1].get(
            strategies.pop(), ''))
    if len(dirs) == 3 and all(d.get('temperature') == 'safe' for d in dirs):
        errs.append('三个方向都是行业常见款（temperature: safe）：至少一个方向要与品牌调研里写的「行业常见款」拉开')
    return errs, warns


def comparison(dirs):
    cols = [d.get('id', '?') + ' · ' + d.get('name', '') for d in dirs]
    rows = [('一句话', [d.get('summary', '') for d in dirs]),
            ('来源', ['用户参考（%s）' % '、'.join(os.path.basename(r) for r in ref_paths(d)) if d.get('source') == 'reference'
                    else '自行设计' for d in dirs])]
    rows.append(('品牌呼应', [d.get('brand_fit', '') for d in dirs]))
    rows += [(lab, [(d.get('dims') or {}).get(k, '') for d in dirs]) for k, lab in E.DIMS]
    rows.append(('配色策略', [E.AXES['color_strategy'][1].get((d.get('axes') or {}).get('color_strategy'), '') for d in dirs]))
    rows.append(('配图方式', [E.IMAGERY_MODES.get(d.get('imagery_mode'), ('',))[0] for d in dirs]))
    rows.append(('封面', ['%s；%s' % ((d.get('cover') or {}).get('layout', ''), (d.get('cover') or {}).get('motif', ''))
                         if isinstance(d.get('cover'), dict) else '' for d in dirs]))
    rows.append(('图标', [E.ICON_POLICIES.get(d.get('icons') or 'none', ('',))[0] for d in dirs]))
    rows.append(('与行业常见款', [E.TEMPERATURES.get(d.get('temperature'), '') for d in dirs]))
    rows.append(('明暗', ['、'.join('%s %s' % ({'cover': '封面', 'section': '章节', 'content': '内容', 'closing': '封底'}.get(k, k),
                                              {'light': '浅', 'dark': '深'}.get(v, v)) for k, v in (d.get('tone') or {}).items())
                        for d in dirs]))
    out = ['# 设计方向说明', '', '| | %s |' % ' | '.join(cols), '|---|' + '---|' * len(cols)]
    for lab, vals in rows:
        out.append('| %s | %s |' % (lab, ' | '.join(str(v).replace('|', '｜').replace('\n', ' ') for v in vals)))
    return '\n'.join(out) + '\n'


def sample_check(proj, dirs):
    """OCR-check each direction's samples; returns markdown lines of a 样张核对 table."""
    import textcheck
    out = ['', '## 样张核对', '', '| 方向 | 页 | 结果 | 说明 |', '|---|---|---|---|']
    for d in dirs:
        base = os.path.dirname(d['_path'])
        prompts, raw = os.path.join(base, 'prompts'), os.path.join(base, 'samples')
        if not os.path.exists(os.path.join(raw, 'selected.json')):
            out.append('| %s | — | 没有样张 | |' % d.get('id'))
            continue
        rep = textcheck.run(proj, prompts, raw, quiet=True)
        for pid, r in sorted(rep.items()):
            note = '；'.join(x for x in ('缺：' + '、'.join(r['missing']) if r['missing'] else '',
                                         '多出：' + '、'.join(r.get('extra', [])) if r.get('extra') else '',
                                         '角落：' + '、'.join(r['corner']) if r['corner'] else '') if x)
            out.append('| %s | %s | %s | %s |' % (d.get('id'), pid.upper(), r['status'], note.replace('|', '｜')))
    return out


def main():
    proj = os.path.abspath([x for x in sys.argv[1:] if not x.startswith('--')][0])
    dirs = load(proj)
    errs, warns = check(dirs)
    errs = brand.check(proj) + errs
    for w in warns:
        print('提示：' + w)
    for e in errs:
        print('✗ ' + e)
    if dirs:
        p = os.path.join(proj, E.D_DIRS, '方向说明.md')
        text = comparison(dirs)
        if '--samples' in sys.argv:
            text += '\n'.join(sample_check(proj, dirs)) + '\n'
        open(p, 'w', encoding='utf-8').write(text)
        print(p)
    if errs:
        sys.exit(1)
    print('三个方向检查通过')


if __name__ == '__main__':
    main()
