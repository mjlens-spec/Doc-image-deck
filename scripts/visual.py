# -*- coding: utf-8 -*-
"""Stage 1 · Check the per-slide visual plan (视觉规划) and write the table the user reviews.

Usage: visual.py <project>
Every page of outline.json carries a "visual" brief, written from what the page says (schema and method:
references/01_白板稿.md「逐页视觉规划」):
  message    the one thing the audience must get from the slide
  structure  how the ideas relate, one of deckenv.STRUCTURES (flow, loop, funnel, timeline, compare ...)
  form       how this slide draws that structure: shapes, arrows, what is proportional to what, which text sits where
  focal      the single element with the most visual weight
  skeleton   composition, one of deckenv.SKELETONS
  motif      picture or graphic subject (optional, different on every slide)
A block may carry "visual": "<how this block is drawn>", which ties its strings to a part of the drawing.

Errors: a page without message / structure / form / focal / skeleton or with an unknown value; two neighbouring
slides with the same skeleton; one skeleton on more than a quarter of the content slides (at least 2 allowed);
structure "list" on more than a fifth (at least 1 allowed); more pages than project.json "max_pages" (appendix pages
not counted); a section page when project.json has "section_pages": false; a page over the capacity of its skeleton
for the deck mode (deckenv.CAPACITY: body CJK characters and printed strings; tables at most 6 rows x 5 columns); a
title over 30 characters (appendix pages always use the read capacity); in present mode, more than 3 dense content slides in a row, or no light slide in a deck of
8 or more (light = hero / bignum with at most half the body capacity).
In decks of 8+ content slides a skeleton (other than hero) may not come back on the slide after next.
Warnings: neighbouring slides with the same structure; the same form or motif text on two slides; similar motifs; a kicker over 8
characters; a content slide with under 20 body characters that is not a hero / bignum slide (merge candidate).
Writes 00_白板稿/视觉规划.md. build_prompts.py runs the same check and refuses to write prompts while it fails.
"""
import os, sys, math, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deckenv as E
import punct

FIELDS = [('message', '这一页要说清'), ('structure', '信息结构'), ('form', '画法'), ('focal', '视觉焦点'), ('skeleton', '构图骨架')]
KIND = E.KINDS


def label(table, key):
    return table.get(key, (key or '—',))[0]


def density(page, mode):
    """'light' for a hero / bignum slide using at most half of its body capacity, else 'dense'."""
    v = page.get('visual') if isinstance(page.get('visual'), dict) else {}
    sk = v.get('skeleton')
    if sk in ('hero', 'bignum'):
        body = E.page_load(page)[0]
        if body <= E.CAPACITY[sk][mode][0] / 2.0:
            return 'light'
    return 'dense'


def capacity(outline, cfg):
    """Errors and warnings of the per-skeleton text capacity, title length and (present mode) rhythm checks."""
    errs, warns = [], []
    mode = E.deck_mode(cfg)
    pages = outline.get('pages', [])
    ids = E.page_ids(outline)
    for pid, p in zip(ids, pages):
        title = str(p.get('title') or '')
        if punct.visible_len(title) > E.TITLE_MAX:
            errs.append('%s 标题 %d 字，超过 %d 字：改短，或把依据移进正文' % (pid, punct.visible_len(title), E.TITLE_MAX))
        if p.get('kicker') and p.get('kind', 'content') in E.CONTENT_KINDS and punct.visible_len(str(p['kicker'])) > E.KICKER_MAX:
            warns.append('%s 的 kicker「%s」超过 %d 字' % (pid, p['kicker'], E.KICKER_MAX))
        v = p.get('visual') if isinstance(p.get('visual'), dict) else {}
        sk = v.get('skeleton')
        body, n, (rows, cols) = E.page_load(p)
        if rows > E.TABLE_MAX[0] or cols > E.TABLE_MAX[1]:
            errs.append('%s 的表格 %d 行 × %d 列，超过 %d × %d：拆页、改成分栏，或%s' % (
                pid, rows, cols, E.TABLE_MAX[0], E.TABLE_MAX[1], '把明细放进讲稿' if mode == 'present' else '把明细放进附录'))
        if sk in E.CAPACITY:
            cap_body, cap_n = E.CAPACITY[sk]['read' if p.get('kind') == 'appendix' else mode]   # appendix pages are read
            over = []
            if body > cap_body:
                over.append('正文 %d 字（上限 %d）' % (body, cap_body))
            if n > cap_n:
                over.append('%d 条文字（上限 %d）' % (n, cap_n))
            if over:
                errs.append('%s 按「%s」骨架、%s计算：%s。拆成续页、换一种容量更大的骨架，或%s' % (
                    pid, label(E.SKELETONS, sk), E.MODES[mode], '，'.join(over),
                    '把细节移进讲稿' if mode == 'present' else '把明细移进附录'))
            if p.get('kind', 'content') == 'content' and body < 20 and sk not in ('hero', 'bignum'):
                warns.append('%s 正文只有 %d 字：考虑与相邻页合并，或改用大字、大数字骨架' % (pid, body))
    if mode == 'read':
        content = [(pid, p) for pid, p in zip(ids, pages) if p.get('kind', 'content') in ('content', 'summary')]
        if len(content) >= 10:                         # long reading decks: a change of pace at least every six slides
            for i in range(0, len(content) - 5):
                win = content[i:i + 6]
                if all(density(p, mode) == 'dense' and p.get('tone') != 'dark' for _, p in win):
                    warns.append('%s–%s 连续 6 页都是高密度浅色页：长稿里每 6 页至少放一页低密度页（大字论断、大数字）或深色页（tone: dark），'
                                 '否则看久了显得雷同' % (win[0][0], win[-1][0]))
                    break
    if mode == 'present':
        content = [(pid, p) for pid, p in zip(ids, pages) if p.get('kind', 'content') in ('content', 'summary')]
        run = []
        for pid, p in content + [(None, None)]:
            if p is not None and density(p, mode) == 'dense':
                run.append(pid)
                continue
            if len(run) > 3:
                errs.append('演讲稿连续 %d 页高密度内容页（%s）：每 3 页至少插一页大字或大数字的低密度页，或把细节移进讲稿' % (
                    len(run), '、'.join(run)))
            run = []
        if len(pages) >= 8 and content and all(density(p, mode) == 'dense' for _, p in content):
            errs.append('演讲稿 %d 页，没有一页低密度内容页（大字论断或大数字，正文不超过骨架上限的一半）' % len(pages))
    return errs, warns


def check(outline, cfg=None):
    cfg = cfg or {}
    errs, warns = [], []
    pages = outline.get('pages', [])
    ids = E.page_ids(outline)
    main_pages = [p for p in pages if p.get('kind') != 'appendix']
    if cfg.get('max_pages') and len(main_pages) > cfg['max_pages']:
        errs.append('正文共 %d 页，超过 project.json 的 max_pages（%d 页，附录不计）' % (len(main_pages), cfg['max_pages']))
    if cfg.get('section_pages') is False:
        sec = [pid for pid, p in zip(ids, pages) if p.get('kind') == 'section']
        if sec:
            errs.append('project.json 设为不用章节页（section_pages: false），但 %s 是章节页；章节名写进内容页的 kicker' % '、'.join(sec))
    for pid, p in zip(ids, pages):
        v = p.get('visual')
        if not isinstance(v, dict):
            errs.append('%s 没有视觉规划（visual）' % pid)
            continue
        miss = [lab for k, lab in FIELDS if not str(v.get(k) or '').strip()]
        if miss:
            errs.append('%s 的视觉规划缺少：%s' % (pid, '、'.join(miss)))
        if v.get('structure') and v['structure'] not in E.STRUCTURES:
            errs.append('%s 的 structure「%s」不在可选值内：%s' % (pid, v['structure'], '、'.join(E.STRUCTURES)))
        if v.get('skeleton') and v['skeleton'] not in E.SKELETONS:
            errs.append('%s 的 skeleton「%s」不在可选值内：%s' % (pid, v['skeleton'], '、'.join(E.SKELETONS)))
    vis = [(pid, p, p.get('visual') if isinstance(p.get('visual'), dict) else {}) for pid, p in zip(ids, pages)]
    for (pa, _, va), (pb, _, vb) in zip(vis, vis[1:]):
        if va.get('skeleton') and va.get('skeleton') == vb.get('skeleton'):
            errs.append('%s 与 %s 相邻，构图骨架相同（%s），换一种' % (pa, pb, label(E.SKELETONS, va['skeleton'])))
        elif va.get('structure') and va.get('structure') == vb.get('structure'):
            warns.append('%s 与 %s 相邻，信息结构相同（%s），确认画法有明显区别' % (pa, pb, label(E.STRUCTURES, va['structure'])))
    content = [(pid, v) for pid, p, v in vis if p.get('kind', 'content') in E.CONTENT_KINDS]
    cap = max(2, int(math.ceil(len(content) / 4.0)))
    use = collections.OrderedDict()
    for pid, v in content:
        if v.get('skeleton'):
            use.setdefault(v['skeleton'], []).append(pid)
    for sk, pids in use.items():
        if len(pids) > cap:
            errs.append('构图骨架「%s」用了 %d 页（%s），内容页 %d 页时每种最多 %d 页' % (
                label(E.SKELETONS, sk), len(pids), '、'.join(pids), len(content), cap))
    if len(content) >= 8:                              # long decks: a skeleton comes back no sooner than the third slide
        for (pa, va), (pb, vb) in zip(content, content[2:]):
            if va.get('skeleton') and va.get('skeleton') == vb.get('skeleton') and va['skeleton'] != 'hero':
                errs.append('%s 与 %s 只隔一页，构图骨架相同（%s）：长稿里同一骨架至少隔两页' % (pa, pb, label(E.SKELETONS, va['skeleton'])))
    lists = [pid for pid, v in content if v.get('structure') == 'list']
    if len(lists) > max(1, len(content) // 5):
        errs.append('「并列要点」用了 %d 页（%s）：先看这些页的要点之间有没有先后、因果、包含或对比关系，换成对应的结构' % (
            len(lists), '、'.join(lists)))
    import difflib
    for key, lab in (('form', '画法'), ('motif', '配图母题')):
        seen = {}
        for pid, _, v in vis:
            t = E.norm(str(v.get(key) or ''))
            if not t or (key == 'motif' and t.startswith(('无照片', '无', 'NONE'))):      # "no picture" is not a subject
                continue
            if t in seen:
                warns.append('%s 与 %s 的%s相同' % (seen[t], pid, lab))
            elif key == 'motif' and any(difflib.SequenceMatcher(None, t, u).ratio() >= 0.6 for u in seen):
                other = next(seen[u] for u in seen if difflib.SequenceMatcher(None, t, u).ratio() >= 0.6)
                warns.append('%s 与 %s 的配图母题相近：换一个题材或景别，长稿里同类配图反复出现会显得雷同' % (other, pid))
                seen[t] = pid
            else:
                seen[t] = pid
    ce, cw = capacity(outline, cfg)
    return errs + ce, warns + cw


def plan_md(outline, errs, warns, cfg=None):
    pages = outline.get('pages', [])
    ids = E.page_ids(outline)
    mode = E.deck_mode(cfg)
    vis = [p.get('visual') if isinstance(p.get('visual'), dict) else {} for p in pages]
    kinds = collections.Counter(KIND.get(p.get('kind', 'content'), p.get('kind')) for p in pages)
    mark = lambda p: '·' if density(p, mode) == 'light' else '■'
    out = ['# 视觉规划', '',
           '全稿 %d 页（%s）；读法：%s。' % (len(pages), '、'.join('%s %d' % kv for kv in kinds.items()), E.MODES[mode]), '',
           '构图节奏：' + ' → '.join('%s %s' % (pid.upper(), label(E.SKELETONS, v.get('skeleton'))) for pid, v in zip(ids, vis)), '',
           '密度节奏（■ 高密度，· 低密度）：' + ' '.join('%s%s' % (pid.upper(), mark(p)) for pid, p in zip(ids, pages)), '',
           '| 页 | 标题 | 这一页要说清 | 信息结构 | 画法 | 视觉焦点 | 构图骨架 | 字数 / 条数（上限） | 配图母题 |',
           '|---|---|---|---|---|---|---|---|---|']
    cell = lambda s: str(s or '—').replace('|', '｜').replace('\n', ' ')
    for pid, p, v in zip(ids, pages, vis):
        body, n, _ = E.page_load(p)
        cap = E.CAPACITY.get(v.get('skeleton'), {}).get(mode)
        load = '%d / %d' % (body, n) + ('（%d / %s）' % (cap[0], cap[1] if cap[1] < 99 else '—') if cap else '')
        out.append('| %s | %s | %s | %s | %s | %s | %s | %s | %s |' % (
            pid.upper(), cell(p.get('title')), cell(v.get('message')), cell(label(E.STRUCTURES, v.get('structure'))),
            cell(v.get('form')), cell(v.get('focal')), cell(label(E.SKELETONS, v.get('skeleton'))), load, cell(v.get('motif'))))
    use = collections.OrderedDict()
    for pid, p, v in zip(ids, pages, vis):
        if v.get('skeleton'):
            use.setdefault(v['skeleton'], []).append(pid.upper())
    out += ['', '## 构图骨架使用情况', '', '| 骨架 | 页数 | 页 |', '|---|---|---|']
    out += ['| %s | %d | %s |' % (label(E.SKELETONS, k), len(v), '、'.join(v)) for k, v in use.items()]
    out += ['', '## 检查结果', '']
    out += ['- ✗ ' + e for e in errs] + ['- 提示：' + w for w in warns]
    if not errs and not warns:
        out.append('- 通过')
    return '\n'.join(out) + '\n'


def run(proj):
    """Check the plan, write 视觉规划.md; returns (errors, warnings, path)."""
    outline = E.load_outline(proj)
    cfg = E.load_project(proj)
    errs, warns = check(outline, cfg)
    path = os.path.join(proj, E.D_WHITE, '视觉规划.md')
    open(path, 'w', encoding='utf-8').write(plan_md(outline, errs, warns, cfg))
    return errs, warns, path


def main():
    proj = os.path.abspath(sys.argv[1])
    errs, warns, path = run(proj)
    for w in warns:
        print('提示：' + w)
    for e in errs:
        print('✗ ' + e)
    print(path)
    if errs:
        sys.exit(1)
    print('视觉规划检查通过')


if __name__ == '__main__':
    main()
