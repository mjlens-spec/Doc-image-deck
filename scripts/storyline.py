# -*- coding: utf-8 -*-
"""Stage 1 · Check the storyline (故事线) of outline.json and write the page the user reads first at confirmation 1.

Usage: storyline.py <project>
Step 1a of stage 1 writes, before any body text: outline "storyline" {"thesis": one-sentence answer of the deck,
"mode": scqa | chronological | report, "dropped": [{"source": heading, "reason": why it is left out}]} and, per page,
kind, chapter, title, visual.message and source (headings, table / figure numbers or file names of the source
document it comes from; "补充：<出处>" for material the source document does not have). Step 1b then writes the
body. Schema and method: references/01_白板稿.md「故事线」.

Errors:
  - no storyline.thesis; a content or appendix page without chapter; one chapter split into non-adjacent runs;
  - project.json "source" is readable (Markdown or .docx) and a content page has no source, a source value that is not a
    heading, a phrase of the document or a file next to it, or a level-1/2 heading that no page uses and
    storyline.dropped does not list; a dropped entry without a reason;
  - appendix pages not together after the closing page, or body text naming 附录 A<n> that does not exist;
  - a closing page titled 谢谢 / Thank you / Q&A; a title that talks about the deck (本页、本章、我们将、接下来 …);
  - an agenda page that does not list every chapter; a summary page whose "covers" is not the chapter order;
  - the same KPI label with two different values on two pages.
Warnings: fewer than 3 or more than 7 chapters (6+ content pages); no executive summary in a read deck of 8+ pages;
present mode with duration_min and a content page count outside duration / 2 … duration / 1.5; one source heading
spread over 4+ pages; two neighbouring pages with the same source (merge candidate); a title equal to a source heading
or ending in 概述 / 介绍 / 现状 / 分析 (topic, not a finding); body text that talks about the deck; the same KPI on
two pages outside the summary.
Writes 00_白板稿/故事线.md: thesis, chapters with titles, the titles read in one run, source map and coverage.
"""
import os, re, sys, json, glob, zipfile, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deckenv as E

THANKS = re.compile(r'^\s*(谢谢|感谢(聆听|观看|您的?(聆听|观看|时间))?|thank\s*you|thanks|q\s*&\s*a|问答|the\s*end)[!！。.\s]*$', re.I)
META = re.compile(r'本页|本章|本部分|本节|我们将|接下来(将|我们|介绍|看)|下面(将|我们|来看|介绍)|以下(是|为|将|几页)|如下所示')
TOPIC_END = re.compile(r'(概述|概况|介绍|简介|现状|分析|情况|说明|总结|一览)$')
APPX_REF = re.compile(r'附录\s*(A\s*\d+)', re.I)
STRUCTURE = ('cover', 'agenda', 'section', 'closing')


def sources_of(page):
    s = page.get('source')
    if isinstance(s, str):
        s = [s]
    return [str(x).strip() for x in (s or []) if str(x).strip()]


# ───────────────────────────── source document
def md_headings(text):
    out = []
    for line in text.splitlines():
        m = re.match(r'^(#{1,6})\s+(.+?)\s*#*\s*$', line)
        if m:
            out.append((len(m.group(1)), m.group(2).strip()))
    return out


def docx_read(path):
    """(headings [(level, text)], plain text) of a .docx, standard library only."""
    z = zipfile.ZipFile(path)
    names = {}
    try:
        st = z.read('word/styles.xml').decode('utf-8', 'ignore')
        for m in re.finditer(r'<w:style\b[^>]*w:styleId="([^"]+)"[^>]*>(.*?)</w:style>', st, re.S):
            nm = re.search(r'<w:name w:val="([^"]+)"', m.group(2))
            lvl = re.search(r'<w:outlineLvl w:val="(\d)"', m.group(2))
            name = nm.group(1) if nm else ''
            h = re.match(r'(?i)(heading|标题)\s*(\d)$', name)
            if h:
                names[m.group(1)] = int(h.group(2))
            elif lvl:
                names[m.group(1)] = int(lvl.group(1)) + 1
    except KeyError:
        pass
    doc = z.read('word/document.xml').decode('utf-8', 'ignore')
    heads, texts = [], []
    for p in re.findall(r'<w:p\b.*?</w:p>', doc, re.S):
        t = ''.join(re.findall(r'<w:t(?:\s[^>]*)?>([^<]*)</w:t>', p)).strip()
        if not t:
            continue
        texts.append(t)
        sid = re.search(r'<w:pStyle w:val="([^"]+)"', p)
        lvl = re.search(r'<w:outlineLvl w:val="(\d)"', p)
        level = names.get(sid.group(1)) if sid else None
        if level is None and lvl:
            level = int(lvl.group(1)) + 1
        if level:
            heads.append((level, t))
    return heads, '\n'.join(texts)


def load_source(proj, cfg):
    """{'files': [...], 'headings': [(level, text)], 'text': str, 'names': [file stems next to the source],
    'unread': [files that could not be parsed]}"""
    src = cfg.get('source')
    src = [src] if isinstance(src, str) else (src or [])
    out = dict(files=[], headings=[], text='', names=[], unread=[])
    dirs = set()
    for s in src:
        p = s if os.path.isabs(s) else os.path.normpath(os.path.join(proj, s))
        if not os.path.exists(p):
            out['unread'].append(p)
            continue
        dirs.add(os.path.dirname(p))
        low = p.lower()
        try:
            if low.endswith(('.md', '.markdown', '.txt')):
                t = open(p, encoding='utf-8', errors='ignore').read()
                out['headings'] += md_headings(t) if not low.endswith('.txt') else []
                out['text'] += '\n' + t
            elif low.endswith('.docx'):
                h, t = docx_read(p)
                out['headings'] += h
                out['text'] += '\n' + t
            else:
                out['unread'].append(p)
                continue
            out['files'].append(p)
        except Exception:
            out['unread'].append(p)
    for d in dirs | {proj}:
        for f in glob.glob(os.path.join(d, '*')) + glob.glob(os.path.join(d, '*', '*')):
            if os.path.isfile(f):
                out['names'].append(os.path.splitext(os.path.basename(f))[0])
    for m in cfg.get('brand_materials', []):
        out['names'].append(os.path.splitext(os.path.basename(m))[0])
    return out


def match_heading(value, heading):
    v, h = E.norm(value), E.norm(heading)
    return len(v) >= 2 and len(h) >= 2 and (v == h or v in h or h in v)


def source_ok(value, src):
    if value.startswith(('补充', '用户补充')):
        return True
    v = E.norm(value)
    if len(v) < 2:
        return False
    if any(match_heading(value, h) for _, h in src['headings']):
        return True
    if v in E.norm(src['text']):
        return True
    return any(E.norm(n).startswith(v) or v.startswith(E.norm(n)) and len(E.norm(n)) >= 2 for n in src['names'])


def heading_tree(headings, max_level=2):
    """[(index, level, text, parent index or None)] for headings down to max_level (levels normalised to the top one)."""
    if not headings:
        return []
    top = min(l for l, _ in headings)
    out, stack = [], []
    for i, (l, t) in enumerate(headings):
        rel = l - top + 1
        if rel > max_level:
            continue
        while stack and stack[-1][1] >= rel:
            stack.pop()
        out.append((i, rel, t, stack[-1][0] if stack else None))
        stack.append((i, rel))
    return out


# ───────────────────────────── checks
def check(outline, cfg=None, src=None):
    cfg = cfg or {}
    src = src or dict(files=[], headings=[], text='', names=[], unread=[])
    errs, warns = [], []
    pages = outline.get('pages', [])
    ids = E.page_ids(outline)
    st = outline.get('storyline') if isinstance(outline.get('storyline'), dict) else {}
    mode = E.deck_mode(cfg)
    if not str(st.get('thesis') or '').strip():
        errs.append('outline.json 缺少 storyline.thesis：先用一句话写出全稿的结论')
    body = [(pid, p) for pid, p in zip(ids, pages) if p.get('kind', 'content') in ('content', 'appendix')]
    for pid, p in body:
        if not str(p.get('chapter') or '').strip():
            errs.append('%s 没有写 chapter（所属章节）' % pid)
    # chapters: contiguous runs over the main (non-appendix) content pages
    runs = []
    for pid, p in zip(ids, pages):
        if p.get('kind', 'content') != 'content' or not p.get('chapter'):
            continue
        if runs and runs[-1][0] == p['chapter']:
            runs[-1][1].append(pid)
        else:
            runs.append((p['chapter'], [pid]))
    seen = collections.Counter(c for c, _ in runs)
    for c, n in seen.items():
        if n > 1:
            errs.append('章节「%s」分成了不相邻的 %d 段（%s）：同一章的页要连续' % (
                c, n, '；'.join('、'.join(ps) for cc, ps in runs if cc == c)))
    chapters = list(dict.fromkeys(c for c, _ in runs))
    n_content = sum(1 for p in pages if p.get('kind', 'content') == 'content')
    if n_content >= 6 and not (3 <= len(chapters) <= 7):
        warns.append('全稿 %d 章（%s）：6 页以上的稿子一般分 3–7 章' % (len(chapters), '、'.join(chapters) or '无'))
    # structure pages
    kinds = [p.get('kind', 'content') for p in pages]
    if 'appendix' in kinds:
        first = kinds.index('appendix')
        if 'closing' in kinds and kinds.index('closing') > first:
            errs.append('附录页要放在封底之后')
        if any(k != 'appendix' for k in kinds[first:]):
            errs.append('附录页要连续放在最后（%s 之后出现了非附录页）' % ids[first])
    labels = E.page_labels({'page_number': {'corner': 'br', 'skip_first': False, 'skip_last': False}}, pages)
    appx = {E.norm(l) for l, p in zip(labels, pages) if p.get('kind') == 'appendix'}
    for pid, p in zip(ids, pages):
        for role, s in E.page_strings(p):
            for ref in APPX_REF.findall(s):
                if E.norm(ref) not in appx:
                    errs.append('%s 写了「附录 %s」，但没有这一页附录' % (pid, ref))
    for pid, p in zip(ids, pages):
        title = str(p.get('title') or '')
        if p.get('kind') == 'closing' and THANKS.match(title):
            errs.append('%s 封底标题是「%s」：封底写结论、下一步或待确认事项' % (pid, title))
        if META.search(title):
            errs.append('%s 标题「%s」在描述这份稿子本身（本页、我们将、接下来……）：标题直接写判断' % (pid, title))
        elif p.get('kind', 'content') == 'content' and TOPIC_END.search(title):
            warns.append('%s 标题「%s」像栏目名：写出这一页的判断' % (pid, title))
        for role, s in E.page_strings(p):
            if role != 'title' and META.search(s):
                warns.append('%s 的%s「%s」在描述这份稿子本身，删掉这类过渡语' % (pid, role, s[:24]))
                break
        if p.get('kind', 'content') == 'content' and any(E.norm(title) == E.norm(h) for _, h in src['headings']):
            warns.append('%s 标题与原文小标题「%s」相同：写出这一页的判断，不照搬栏目名' % (pid, title))
    for pid, p in zip(ids, pages):
        if p.get('kind') == 'agenda':
            got = E.norm(''.join(s for _, s in E.page_strings(p)))
            lack = [c for c in chapters if E.norm(c) not in got]
            if lack:
                errs.append('%s 目录没有列出章节：%s（目录条目与 chapter 逐字一致）' % (pid, '、'.join(lack)))
        if p.get('kind') == 'summary':
            cov = [str(c) for c in (p.get('covers') or [])]
            if cov and cov != [c for c in chapters if c in cov]:
                errs.append('%s 执行摘要的 covers 顺序与章节顺序不一致' % pid)
            elif cov and set(cov) != set(chapters):
                errs.append('%s 执行摘要的 covers 没有覆盖全部章节：缺 %s' % (pid, '、'.join(c for c in chapters if c not in cov)))
        if p.get('kind') == 'section' and p.get('title'):
            nxt = next((q for q in pages[ids.index(pid) + 1:] if q.get('kind', 'content') == 'content'), None)
            if nxt and nxt.get('chapter') and E.norm(nxt['chapter']) != E.norm(p['title']):
                warns.append('%s 章节页标题「%s」与下一章 chapter「%s」不一致' % (pid, p['title'], nxt['chapter']))
    if mode == 'read' and len(pages) >= 8 and 'summary' not in kinds:
        warns.append('阅读稿 %d 页，没有执行摘要页（kind: summary）：封面之后放一页，要点按章节顺序对应后文' % len(pages))
    if mode == 'present' and cfg.get('duration_min'):
        d = float(cfg['duration_min'])
        lo, hi = int(d / 2), int(round(d / 1.5))
        if not lo <= n_content <= max(lo, hi):
            warns.append('演讲 %g 分钟，内容页 %d 页，常见范围 %d–%d 页（约 1.5–2 分钟一页）' % (d, n_content, lo, hi))
    # KPIs across pages
    kpi = collections.defaultdict(list)
    for pid, p in zip(ids, pages):
        for b in p.get('blocks', []):
            if b.get('type') == 'kpis':
                for it in b.get('items', []):
                    if it.get('label') and it.get('value'):
                        kpi[E.norm(it['label'])].append((pid, it['value'], it['label'], p.get('kind', 'content')))
    for k, rows in kpi.items():
        vals = {E.norm(v) for _, v, _, _ in rows}
        if len(vals) > 1:
            errs.append('「%s」在 %s 的数值不一致：%s' % (rows[0][2], '、'.join(r[0] for r in rows), '、'.join(r[1] for r in rows)))
        elif len([r for r in rows if r[3] not in ('summary', 'cover')]) > 1:
            warns.append('「%s %s」在 %s 重复出现：同一事实只放一页（执行摘要除外）' % (
                rows[0][1], rows[0][2], '、'.join(r[0] for r in rows if r[3] not in ('summary', 'cover'))))
    # sources
    have_doc = bool(src['files'])
    use = collections.defaultdict(list)
    for pid, p in zip(ids, pages):
        vals = sources_of(p)
        if p.get('kind', 'content') not in ('content', 'appendix', 'summary') and not vals:
            continue
        if have_doc and not vals and p.get('kind', 'content') in ('content', 'appendix'):
            errs.append('%s 没有写 source（来自原文哪一节、哪张表图；原文没有的写「补充：出处」）' % pid)
        for v in vals:
            if have_doc and not source_ok(v, src):
                errs.append('%s 的 source「%s」在原文的标题、正文和同目录文件里都找不到' % (pid, v))
            for i, lvl, h, _ in heading_tree(src['headings'], 3):
                if match_heading(v, h):
                    use[i].append(pid)
    for (pa, a), (pb, b) in zip(zip(ids, pages), list(zip(ids, pages))[1:]):
        sa, sb = sources_of(a), sources_of(b)
        if not (sa and sa == sb and a.get('kind', 'content') == b.get('kind', 'content') == 'content'):
            continue
        if not (a.get('blocks') and b.get('blocks')):
            continue                                   # step 1a: no body text yet, nothing to compare
        sk = (a.get('visual') or {}).get('skeleton') if isinstance(a.get('visual'), dict) else None
        cap = E.CAPACITY.get(sk, E.CAPACITY['diagram'])[mode][0]
        if E.page_load(a)[0] + E.page_load(b)[0] <= cap:
            warns.append('%s 与 %s 来源相同（%s），两页正文合计不超过一页的容量：确认是两个判断，否则合并' % (pa, pb, '、'.join(sa)))
    tree = heading_tree(src['headings'], 2)
    dropped = st.get('dropped') or []
    drop_names = []
    for d in dropped:
        name = d.get('source') if isinstance(d, dict) else str(d).split('：')[0]
        reason = d.get('reason') if isinstance(d, dict) else (str(d).split('：', 1)[1] if '：' in str(d) else '')
        drop_names.append(name or '')
        if not str(reason or '').strip():
            errs.append('storyline.dropped 的「%s」没有写不上屏的理由' % name)
    if have_doc:
        kids = collections.defaultdict(list)
        for i, lvl, h, parent in tree:
            if parent is not None:
                kids[parent].append(i)
        full = heading_tree(src['headings'], 3)
        parent_of = {i: par for i, _, _, par in full}
        def used(i):
            if use.get(i):
                return True
            j = parent_of.get(i)
            while j is not None:                      # a page citing the parent covers the child
                if use.get(j):
                    return True
                j = parent_of.get(j)
            return any(used(k) for k in kids.get(i, []))
        for i, lvl, h, _ in tree:
            if not used(i) and not any(match_heading(n, h) for n in drop_names if n):
                errs.append('原文「%s」没有对应的页：补进大纲，或写进 storyline.dropped 并说明理由' % h)
        leaves = {i for i, _, _, _ in full} - set(parent_of.values())
        for i, lvl, h, _ in full:
            if i in leaves and len(set(use.get(i, []))) >= 4:
                warns.append('原文「%s」展开成了 %d 页（%s）：确认每页各有一个判断' % (h, len(set(use[i])), '、'.join(sorted(set(use[i])))))
    elif cfg.get('source') and src['unread']:
        warns.append('读不了原文标题（%s）：只支持 Markdown 和 .docx，来源与覆盖检查已跳过' % '、'.join(
            os.path.basename(u) for u in src['unread']))
    return errs, warns


def story_md(outline, cfg, src, errs, warns):
    pages = outline.get('pages', [])
    ids = E.page_ids(outline)
    st = outline.get('storyline') if isinstance(outline.get('storyline'), dict) else {}
    mode = E.deck_mode(cfg)
    main_pages = [p for p in pages if p.get('kind') != 'appendix']
    n_struct = sum(1 for p in main_pages if p.get('kind') in STRUCTURE)
    out = ['# 故事线', '', '**全稿结论**：%s' % (st.get('thesis') or '（未写）'), '',
           '读法：%s；论证方式：%s；正文 %d 页（结构页 %d、内容页 %d）%s%s。' % (
               E.MODES[mode], {'scqa': '情境—冲突—问题—答案', 'chronological': '按时间推进', 'report': '汇报'}.get(st.get('mode'), st.get('mode') or '未写'),
               len(main_pages), n_struct, len(main_pages) - n_struct,
               ('；上限 %d 页' % cfg['max_pages']) if cfg.get('max_pages') else '',
               ('；附录 %d 页' % (len(pages) - len(main_pages))) if len(pages) > len(main_pages) else ''), '',
           '## 标题串读', '']
    group, prev = [], None
    for pid, p in zip(ids, pages):
        ch = p.get('chapter') or E.KINDS.get(p.get('kind', 'content'), '')
        if ch != prev:
            out.append('**%s**' % ch)
            prev = ch
        out.append('- %s %s' % (pid.upper(), p.get('title', '')))
    out += ['', '连起来读：' + '；'.join(str(p.get('title', '')).rstrip('。') for p in main_pages
                                   if p.get('kind', 'content') in ('content', 'summary', 'closing')) + '。', '',
            '## 原文来源', '', '| 页 | 章节 | 标题 | 来源 |', '|---|---|---|---|']
    cell = lambda s: str(s or '—').replace('|', '｜')
    for pid, p in zip(ids, pages):
        if p.get('kind', 'content') in STRUCTURE:
            continue
        out.append('| %s | %s | %s | %s |' % (pid.upper(), cell(p.get('chapter')), cell(p.get('title')), cell('、'.join(sources_of(p)))))
    extra = [(pid, v) for pid, p in zip(ids, pages) for v in sources_of(p) if v.startswith(('补充', '用户补充'))]
    if extra:
        out += ['', '原文以外的补充：' + '；'.join('%s %s' % (pid.upper(), v) for pid, v in extra)]
    if src['files']:
        out += ['', '## 原文覆盖', '', '原文：' + '、'.join('`%s`' % os.path.basename(f) for f in src['files']), '',
                '| 原文标题 | 用在 |', '|---|---|']
        used = {}
        for i, lvl, h, parent in heading_tree(src['headings'], 2):
            pids = [pid.upper() for pid, p in zip(ids, pages) if any(match_heading(v, h) for v in sources_of(p))]
            used[i] = pids
            shown = '、'.join(pids) or ('随上级（%s）' % '、'.join(used[parent]) if parent is not None and used.get(parent) else '—')
            out.append('| %s%s | %s |' % ('　' * (lvl - 1), cell(h), shown))
    dropped = st.get('dropped') or []
    if dropped:
        out += ['', '## 不上屏的原文', '']
        for d in dropped:
            out.append('- %s' % ('%s：%s' % (d.get('source'), d.get('reason')) if isinstance(d, dict) else d))
    out += ['', '## 检查结果', ''] + ['- ✗ ' + e for e in errs] + ['- 提示：' + w for w in warns]
    if not errs and not warns:
        out.append('- 通过')
    return '\n'.join(out) + '\n'


def run(proj):
    outline = E.load_outline(proj)
    cfg = E.load_project(proj)
    src = load_source(proj, cfg)
    errs, warns = check(outline, cfg, src)
    path = os.path.join(proj, E.D_WHITE, '故事线.md')
    open(path, 'w', encoding='utf-8').write(story_md(outline, cfg, src, errs, warns))
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
    print('故事线检查通过')


if __name__ == '__main__':
    main()
