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
structure "list" on more than a fifth (at least 1 allowed); more pages than project.json "max_pages"; a section
page when project.json has "section_pages": false.
Warnings: neighbouring slides with the same structure; the same form or motif text on two slides.
Writes 00_白板稿/视觉规划.md. build_prompts.py runs the same check and refuses to write prompts while it fails.
"""
import os, sys, math, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deckenv as E

FIELDS = [('message', '这一页要说清'), ('structure', '信息结构'), ('form', '画法'), ('focal', '视觉焦点'), ('skeleton', '构图骨架')]
KIND = {'cover': '封面', 'section': '章节页', 'content': '内容页', 'closing': '封底'}


def label(table, key):
    return table.get(key, (key or '—',))[0]


def check(outline, cfg=None):
    cfg = cfg or {}
    errs, warns = [], []
    pages = outline.get('pages', [])
    ids = E.page_ids(outline)
    if cfg.get('max_pages') and len(pages) > cfg['max_pages']:
        errs.append('共 %d 页，超过 project.json 的 max_pages（%d 页）' % (len(pages), cfg['max_pages']))
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
    content = [(pid, v) for pid, p, v in vis if p.get('kind', 'content') == 'content']
    cap = max(2, int(math.ceil(len(content) / 4.0)))
    use = collections.OrderedDict()
    for pid, v in content:
        if v.get('skeleton'):
            use.setdefault(v['skeleton'], []).append(pid)
    for sk, pids in use.items():
        if len(pids) > cap:
            errs.append('构图骨架「%s」用了 %d 页（%s），内容页 %d 页时每种最多 %d 页' % (
                label(E.SKELETONS, sk), len(pids), '、'.join(pids), len(content), cap))
    lists = [pid for pid, v in content if v.get('structure') == 'list']
    if len(lists) > max(1, len(content) // 5):
        errs.append('「并列要点」用了 %d 页（%s）：先看这些页的要点之间有没有先后、因果、包含或对比关系，换成对应的结构' % (
            len(lists), '、'.join(lists)))
    for key, lab in (('form', '画法'), ('motif', '配图母题')):
        seen = {}
        for pid, _, v in vis:
            t = E.norm(str(v.get(key) or ''))
            if not t or (key == 'motif' and t.startswith(('无照片', '无', 'NONE'))):      # "no picture" is not a subject
                continue
            if t in seen:
                warns.append('%s 与 %s 的%s相同' % (seen[t], pid, lab))
            else:
                seen[t] = pid
    return errs, warns


def plan_md(outline, errs, warns):
    pages = outline.get('pages', [])
    ids = E.page_ids(outline)
    vis = [p.get('visual') if isinstance(p.get('visual'), dict) else {} for p in pages]
    kinds = collections.Counter(KIND.get(p.get('kind', 'content'), p.get('kind')) for p in pages)
    out = ['# 视觉规划', '',
           '全稿 %d 页（%s）。' % (len(pages), '、'.join('%s %d' % kv for kv in kinds.items())), '',
           '构图节奏：' + ' → '.join('%s %s' % (pid.upper(), label(E.SKELETONS, v.get('skeleton'))) for pid, v in zip(ids, vis)), '',
           '| 页 | 标题 | 这一页要说清 | 信息结构 | 画法 | 视觉焦点 | 构图骨架 | 配图母题 |', '|---|---|---|---|---|---|---|---|']
    cell = lambda s: str(s or '—').replace('|', '｜').replace('\n', ' ')
    for pid, p, v in zip(ids, pages, vis):
        out.append('| %s | %s | %s | %s | %s | %s | %s | %s |' % (
            pid.upper(), cell(p.get('title')), cell(v.get('message')), cell(label(E.STRUCTURES, v.get('structure'))),
            cell(v.get('form')), cell(v.get('focal')), cell(label(E.SKELETONS, v.get('skeleton'))), cell(v.get('motif'))))
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
    errs, warns = check(outline, E.load_project(proj))
    path = os.path.join(proj, E.D_WHITE, '视觉规划.md')
    open(path, 'w', encoding='utf-8').write(plan_md(outline, errs, warns))
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
