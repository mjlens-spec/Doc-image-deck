# -*- coding: utf-8 -*-
"""Stage 2 QA · Slide review against the visual plan (审图), done by a fresh sub-agent that did not write the prompts.

Usage: slidereview.py <project> init  [--prompts 02_生图/prompts] [--raw 02_生图/raw] [--pages p02,p05]
       slidereview.py <project> check [--raw 02_生图/raw]

init writes <raw>/../审图/审图.json (one entry per selected slide: the image, what the plan expects, the text-check
status, empty answers) and 审图说明.md (instructions for the reviewer). The reviewer opens every image, fills in
"answers" (true / false for each question) and "problems" ([{"type": one of TYPES, "note": "..."}]), and sets "verdict"
to pass / regen / fix (fix = one or two wrong characters, for deck fix). Pages checked earlier keep their answers
when their image has not changed.
check refuses while entries are unanswered, lists the pages to regenerate or fix, and reports a problem type found on
3 or more slides as deck-wide: change the direction or the prompts (build_prompts.py) once instead of regenerating
slide by slide. Writes 审图汇总.md.
"""
import os, sys, json, argparse, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deckenv as E

QUESTIONS = [
    ('skeleton', '构图骨架按规划落地（expected.skeleton）'),
    ('focal', '全页最醒目的元素就是规划的视觉焦点（expected.focal）'),
    ('relations', '箭头方向、回流、分组、比例与文字之间的关系一致（expected.form）'),
    ('no_extra_labels', '图上没有引号文案以外的标签、数字、英文装饰词'),
    ('icons_ok', '图标符合方向的图标策略（expected.icons），没有规划外的图标'),
    ('style_ok', '底色、字体、标题位置与字号、边距与其他页一致，没有风格漂移'),
]
TYPES = {'skeleton': '构图没按规划', 'focal': '焦点不对', 'relations': '图示关系画错', 'extra_labels': '多出文字',
         'icons': '规划外的图标', 'style': '风格漂移', 'text': '错字漏字', 'corner': '压到预留角', 'other': '其他'}
VERDICTS = ('pass', 'regen', 'fix')


def paths(proj, raw):
    raw = os.path.abspath(raw or os.path.join(proj, E.D_GEN, 'raw'))
    d = os.path.join(os.path.dirname(raw), '审图')
    return raw, d, os.path.join(d, '审图.json')


def init(proj, prompts, raw, pages=None):
    raw, d, jp = paths(proj, raw)
    prompts = os.path.abspath(prompts or os.path.join(proj, E.D_GEN, 'prompts'))
    outline = E.load_outline(proj)
    by_id = dict(zip(E.page_ids(outline), outline['pages']))
    sel = json.load(open(os.path.join(raw, 'selected.json'), encoding='utf-8'))
    tc_p = os.path.join(raw, 'textcheck.json')
    tc = json.load(open(tc_p, encoding='utf-8')) if os.path.exists(tc_p) else {}
    dp = os.path.join(prompts, 'direction.json')
    icons = (json.load(open(dp, encoding='utf-8')).get('icons') if os.path.exists(dp) else None) or 'none'
    old = {e['page']: e for e in json.load(open(jp, encoding='utf-8'))} if os.path.exists(jp) else {}
    out = []
    for pid in sorted(sel):
        if pid not in by_id:
            continue
        p = by_id[pid]
        v = p.get('visual') if isinstance(p.get('visual'), dict) else {}
        prev = old.get(pid)
        if prev and prev.get('file') == sel[pid] and (not pages or pid not in pages):
            out.append(prev)
            continue
        out.append(dict(
            page=pid, file=sel[pid], image=os.path.join(raw, sel[pid]),
            expected=dict(kind=E.KINDS.get(p.get('kind', 'content'), p.get('kind')), title=p.get('title', ''),
                          message=v.get('message', ''),
                          structure=E.STRUCTURES.get(v.get('structure'), (v.get('structure', ''),))[0],
                          form=v.get('form', ''), focal=v.get('focal', ''),
                          skeleton=E.SKELETONS.get(v.get('skeleton'), (v.get('skeleton', ''),))[0],
                          icons=E.ICON_POLICIES.get(icons, ('',))[0],
                          strings=[s for _, s in E.page_strings(p)]),
            textcheck=(tc.get(pid) or {}).get('status', '未核对'),
            answers={k: None for k, _ in QUESTIONS}, problems=[], verdict=None))
    os.makedirs(d, exist_ok=True)
    json.dump(out, open(jp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    guide = ['# 审图说明', '',
             '给审图的 agent：你没有参与写提示词，按规划逐页看图。不要改 `审图.json` 以外的文件。', '',
             '1. 逐页打开 `image`，对照 `expected`（这一页的视觉规划和允许上屏的文字）。',
             '2. 在 `answers` 里逐项填 true / false：'] + ['   - `%s`：%s' % (k, lab) for k, lab in QUESTIONS] + [
             '3. 有问题时在 `problems` 里逐条写 `{"type": 类型, "note": "具体在哪、是什么"}`，类型从下表选：'] + [
             '   - `%s`：%s' % (k, lab) for k, lab in TYPES.items()] + [
             '4. `verdict`：`pass` 可用；`fix` 只错一两个字（交给 deck fix）；`regen` 要整页重生成。',
             '5. 只看图，不猜提示词。`textcheck` 一栏是 OCR 结果，MISS 的页要确认文字是否真的缺。', '',
             '填完后由主 agent 运行 `deck audit <项目> check`。']
    open(os.path.join(d, '审图说明.md'), 'w', encoding='utf-8').write('\n'.join(guide) + '\n')
    print(jp)
    print('%d 页待审（%d 页沿用上次结果）。交给新开的子 agent，按 %s 填写。' % (
        sum(1 for e in out if e['verdict'] is None), sum(1 for e in out if e['verdict'] is not None),
        os.path.join(d, '审图说明.md')))
    return jp


def check(proj, raw):
    raw, d, jp = paths(proj, raw)
    if not os.path.exists(jp):
        raise SystemExit('还没有审图清单：先运行 deck audit <项目> init')
    entries = json.load(open(jp, encoding='utf-8'))
    errs = []
    for e in entries:
        blank = [k for k, _ in QUESTIONS if e['answers'].get(k) is None]
        if blank or e.get('verdict') not in VERDICTS:
            errs.append('%s 还没审完（%s）' % (e['page'], '、'.join(blank) or 'verdict'))
        for pr in e.get('problems', []):
            if pr.get('type') not in TYPES:
                errs.append('%s 的问题类型「%s」不在可选值内：%s' % (e['page'], pr.get('type'), '、'.join(TYPES)))
    if errs:
        for x in errs:
            print('✗ ' + x)
        sys.exit(1)
    kinds = collections.defaultdict(list)
    for e in entries:
        for pr in e.get('problems', []):
            kinds[pr['type']].append(e['page'])
    wide = {k: sorted(set(v)) for k, v in kinds.items() if len(set(v)) >= 3}
    regen = [e['page'] for e in entries if e['verdict'] == 'regen']
    fix = [e['page'] for e in entries if e['verdict'] == 'fix']
    out = ['# 审图汇总', '', '共 %d 页：可用 %d，局部改字 %d，整页重生成 %d。' % (
        len(entries), len(entries) - len(regen) - len(fix), len(fix), len(regen)), '']
    if wide:
        out += ['## 全稿问题（3 页及以上）', '', '先改方向或提示词，再重生成这些页，不逐页修：', '']
        out += ['- %s：%s' % (TYPES[k], '、'.join(v)) for k, v in wide.items()] + ['']
    out += ['## 逐页', '', '| 页 | 结论 | 问题 |', '|---|---|---|']
    for e in entries:
        out.append('| %s | %s | %s |' % (e['page'].upper(), {'pass': '可用', 'fix': '局部改字', 'regen': '重生成'}[e['verdict']],
                                         '；'.join('%s：%s' % (TYPES[p['type']], p.get('note', '')) for p in e.get('problems', []))
                                         .replace('|', '｜') or '—'))
    sp = os.path.join(d, '审图汇总.md')
    open(sp, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    for k, v in wide.items():
        print('全稿问题：%s（%s）——改方向或提示词后再重生成' % (TYPES[k], '、'.join(v)))
    print('局部改字：%s' % (','.join(fix) or '无'))
    print('整页重生成：%s' % (','.join(regen) or '无'))
    print(sp)
    return entries, wide


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project'); ap.add_argument('action', choices=['init', 'check'])
    ap.add_argument('--prompts', default=''); ap.add_argument('--raw', default=''); ap.add_argument('--pages', default='')
    a = ap.parse_args()
    proj = os.path.abspath(a.project)
    if a.action == 'init':
        init(proj, a.prompts, a.raw, [p.strip() for p in a.pages.split(',') if p.strip()] or None)
    else:
        check(proj, a.raw)


if __name__ == '__main__':
    main()
