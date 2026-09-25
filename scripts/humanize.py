# -*- coding: utf-8 -*-
"""Stage 1 · 去 AI 味：把白板稿文案（上屏文字与讲稿）交给 humanizer-zh 处理，再生成白板稿。

Usage:
  humanize.py <project> export [--changed]   write 00_白板稿/文案_原稿.md, print where humanizer-zh is
  humanize.py <project> import [--force]     read 00_白板稿/文案_改后.md back into outline.json after the checks
  humanize.py <project> accept [--note 说明]  mark the current wording as done without editing (wording the user dictated)
  humanize.py <project> status               list strings that have not been through this step; exit 1 if any

Every printed string that contains Chinese and every page's speaker notes are exported, one ⟦id role⟧ marker each.
The agent edits a copy by the rules in humanizer-zh's SKILL.md and saves it as 文案_改后.md. Import checks that
every marker is still there, that numbers, Latin words (brands, product names, units) and quoted text are unchanged
in every string, and warns when a printed string grows by more than a quarter; then writes outline.json, appends the
changes to 00_白板稿/去AI味记录.md and records the processed wording in 00_白板稿/去AI味_已处理.json.
`deck whiteboard` refuses to render while any string is still pending. --changed exports only the pending strings
(after an edit at confirmation point 1).
"""
import os, re, sys, json, argparse, datetime
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deckenv as E
import punct

SRC_MD, OUT_MD = '文案_原稿.md', '文案_改后.md'
DONE_JSON, LOG_MD = '去AI味_已处理.json', '去AI味记录.md'
CJK = re.compile(r'[㐀-鿿]')
MARK = re.compile(r'^⟦((?:p\d+|deck)\.\d+)(?:\s[^⟧]*)?⟧\s?(.*)$')
ROLE_ZH = {'deck title': '全稿标题', 'kicker': '眉题', 'title': '标题', 'subtitle': '副标题', 'bullet': '要点', 'step': '步骤',
           'number': '编号', 'item title': '条目标题', 'item text': '条目说明', 'big number': '大数字', 'number label': '数字说明',
           'table caption': '表格标题', 'table header': '表头', 'table cell': '单元格', 'column title': '分栏标题',
           'column item': '分栏条目', 'text': '正文', 'quote': '引语', 'callout': '强调', 'source': '出处', 'heading': '小标题',
           'takeaway': '结论', 'footnote': '脚注', 'notes': '讲稿'}
FACT = re.compile(r'\d+(?:[.,:：/]\d+)*\s*(?:%|‰|％)?|[A-Za-z][A-Za-z0-9&+.\'’\-]*|「[^」]*」|“[^”]*”|《[^》]*》')

HEADER = '''# 白板稿文案 · 去 AI 味

给执行 humanizer-zh 的 agent：

1. 按 humanizer-zh 的 SKILL.md 编辑本文件中 ⟦ ⟧ 标记后面的文字，结果另存为同目录的「文案_改后.md」。
2. 标记整行开头的 ⟦编号 位置⟧ 不改、不删、不挪动，也不新增；一条讲稿可以占多行，一直到下一个标记为止。
3. 数字、百分比、英文、品牌与产品名、引号和书名号里的文字保持原样，导入时逐条核对。
4. 这是演示稿文案：标题、要点、表格文字保持简短，不扩写、不补充原文没有的信息；没有问题的条目原样保留。
5. 「## p01」这类行只是分页，不用处理。
'''


def copy_slots(outline):
    """(id, pid, role, container, key) for every string that goes through the step, in a stable order."""
    counter, out = Counter(), []
    rows = list(punct.slots(outline))
    for pid, page in zip(E.page_ids(outline), outline['pages']):
        rows.append((pid, 'notes', page, 'notes', None))
    order = {pid: i for i, pid in enumerate(['deck'] + E.page_ids(outline))}
    rows.sort(key=lambda r: order.get(r[0], 0))                 # notes after the page's printed strings (stable sort)
    for pid, role, c, k, _ in rows:
        s = punct.get(c, k)
        if not s or not CJK.search(s):
            continue
        counter[pid] += 1
        out.append(('%s.%02d' % (pid, counter[pid]), pid, role, c, k))
    return out


def settled(proj, role, s):
    """The text after the punctuation rules, so wording is compared the way deck whiteboard will leave it."""
    pc = E.load_project(proj).get('punct') or {}
    if role != 'notes' and s.strip() not in set(pc.get('keep', [])) and \
            punct.should_strip(role, s, int(pc.get('long_chars', 40)), int(pc.get('desc_chars', 30))):
        return punct.strip_stop(role, s)
    return s.strip()


def done_path(proj):
    return os.path.join(proj, E.D_WHITE, DONE_JSON)


def load_done(proj):
    p = done_path(proj)
    return set(json.load(open(p, encoding='utf-8')).get('texts', [])) if os.path.exists(p) else set()


def save_done(proj, texts, tool):
    json.dump(dict(tool=tool, time=datetime.datetime.now().isoformat(timespec='seconds'), texts=sorted(texts)),
              open(done_path(proj), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def pending(proj, outline=None):
    outline = outline or E.load_outline(proj)
    done = load_done(proj)
    return [(i, pid, role, punct.get(c, k)) for i, pid, role, c, k in copy_slots(outline)
            if settled(proj, role, punct.get(c, k)) not in done]


def humanizer_path(proj):
    """SKILL.md of the humanizer named in project.json "humanizer" (default humanizer-zh), or None."""
    name = E.load_project(proj).get('humanizer', 'humanizer-zh')
    env = os.environ.get('DOC_IMAGE_DECK_HUMANIZER')
    cands = [env, os.path.join(env, 'SKILL.md')] if env else []
    for root in ('~/.agents/skills', '~/.claude/skills', '~/.codex/skills'):
        cands.append(os.path.join(os.path.expanduser(root), name, 'SKILL.md'))
    for c in cands:
        if c and os.path.isfile(c) and c.endswith('.md'):
            return os.path.realpath(c)
    return None


def parse(md):
    """{id: text} from a marked file; continuation lines belong to the marker above them."""
    out, cur, buf = {}, None, []
    def flush():
        if cur:
            out[cur] = '\n'.join(buf).strip()
    for line in md.splitlines():
        m = MARK.match(line)
        if m:
            flush(); cur, buf = m.group(1), [m.group(2)]
        elif line.startswith('## ') or line.startswith('# '):
            flush(); cur, buf = None, []
        elif cur:
            buf.append(line)
    flush()
    return out


def facts(s):
    return Counter(re.sub(r'\s+', '', t).replace('％', '%') for t in FACT.findall(s))


def cmd_export(proj, changed):
    outline = E.load_outline(proj)
    todo = {i for i, *_ in pending(proj, outline)} if changed else None
    lines, n_print, n_notes, last = [HEADER], 0, 0, None
    for i, pid, role, c, k in copy_slots(outline):
        if todo is not None and i not in todo:
            continue
        if pid != last:
            lines.append('\n## %s' % pid); last = pid
        lines.append('⟦%s %s⟧ %s' % (i, ROLE_ZH.get(role, role), punct.get(c, k).strip()))
        n_notes += role == 'notes'; n_print += role != 'notes'
    p = os.path.join(proj, E.D_WHITE, SRC_MD)
    open(p, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    out = os.path.join(proj, E.D_WHITE, OUT_MD)
    if os.path.exists(out):
        os.remove(out)                                          # a stale edited copy must not be imported by mistake
    hz = humanizer_path(proj)
    print('已写出 %s：%d 条（上屏文字 %d 条，讲稿 %d 条）' % (p, n_print + n_notes, n_print, n_notes))
    if hz:
        print('下一步：按 %s 的规则编辑这份文件，另存为 %s，再运行 deck humanize <项目> import。' % (hz, out))
    else:
        print('未找到 humanizer-zh：运行 deck setup 安装（或 git clone https://github.com/op7418/Humanizer-zh.git ~/.agents/skills/humanizer-zh），'
              '然后按它的 SKILL.md 编辑这份文件，另存为 %s。' % out)


def cmd_import(proj, force):
    wd = os.path.join(proj, E.D_WHITE)
    src_p, out_p = os.path.join(wd, SRC_MD), os.path.join(wd, OUT_MD)
    if not os.path.exists(out_p):
        raise SystemExit('没有 %s：先按 humanizer-zh 处理 %s 并另存。' % (out_p, SRC_MD))
    before = parse(open(src_p, encoding='utf-8').read())
    after = parse(open(out_p, encoding='utf-8').read())
    missing, extra = sorted(set(before) - set(after)), sorted(set(after) - set(before))
    if missing or extra:
        raise SystemExit('标记不一致：缺少 %s；多出 %s。改后文件要保留原稿的全部标记，不能增删。' % (missing or '无', extra or '无'))
    outline = E.load_outline(proj)
    slots = {i: (pid, role, c, k) for i, pid, role, c, k in copy_slots(outline)}
    stale = [i for i in before if i not in slots or punct.get(slots[i][2], slots[i][3]).strip() != before[i]]
    if stale:
        raise SystemExit('outline.json 在导出之后改过（%s）：重新运行 deck humanize <项目> export。' % '、'.join(stale[:8]))
    errors, warns, changes = [], [], []
    for i, new in after.items():
        pid, role, c, k = slots[i]
        old = before[i]
        if not new:
            errors.append('%s 被清空' % i); continue
        if facts(old) != facts(new):
            lost, added = facts(old) - facts(new), facts(new) - facts(old)
            errors.append('%s 的数字 / 英文 / 引文有变化：少了 %s，多了 %s' % (i, list(lost.elements()) or '无', list(added.elements()) or '无'))
        if role != 'notes' and len(new) > len(old) * 1.25 and len(new) > len(old) + 5:
            warns.append('%s 变长：%d → %d 字' % (i, len(old), len(new)))
        if role != 'notes' and '\n' in new:
            errors.append('%s 是上屏文字，不能换行' % i)
        if new != old:
            changes.append((i, role, old, new))
    if errors and not force:
        for e in errors:
            print('✗ ' + e)
        raise SystemExit('有 %d 处不符合要求：按提示改 %s 后重新导入；确认改动无误时加 --force。' % (len(errors), OUT_MD))
    for i, role, old, new in changes:
        pid, role, c, k = slots[i]
        c[k] = new
    json.dump(outline, open(os.path.join(wd, 'outline.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    done = load_done(proj) | {settled(proj, slots[i][1], after[i]) for i in after}
    tool = E.load_project(proj).get('humanizer', 'humanizer-zh')
    save_done(proj, done, tool)
    with open(os.path.join(wd, LOG_MD), 'a', encoding='utf-8') as f:
        if f.tell() == 0:
            f.write('# 去 AI 味记录\n\n工具：%s。只列出改动过的条目。\n' % tool)
        f.write('\n## %s 导入 %d 条，改动 %d 条%s\n\n' % (datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), len(after), len(changes),
                                                   '（--force，%d 处未通过核对）' % len(errors) if errors else ''))
        if changes:
            f.write('| 编号 | 位置 | 原文 | 改后 |\n|---|---|---|---|\n')
            for i, role, old, new in changes:
                cell = lambda s: s.replace('|', '｜').replace('\n', '<br>')
                f.write('| %s | %s | %s | %s |\n' % (i, ROLE_ZH.get(role, role), cell(old), cell(new)))
    for w in warns:
        print('提示：' + w)
    print('已写回 outline.json：%d 条中改动 %d 条，记录见 %s。' % (len(after), len(changes), LOG_MD))


def cmd_accept(proj, note):
    todo = pending(proj)
    done = load_done(proj) | {settled(proj, role, s) for _, _, role, s in todo}
    save_done(proj, done, E.load_project(proj).get('humanizer', 'humanizer-zh'))
    with open(os.path.join(proj, E.D_WHITE, LOG_MD), 'a', encoding='utf-8') as f:
        if f.tell() == 0:
            f.write('# 去 AI 味记录\n')
        f.write('\n## %s 未经处理直接确认 %d 条%s\n\n' % (datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), len(todo),
                                                  '：' + note if note else ''))
        for i, _, role, s in todo:
            f.write('- %s %s：%s\n' % (i, ROLE_ZH.get(role, role), s.replace('\n', ' ')))
    print('已确认 %d 条文案不做去 AI 味处理%s。' % (len(todo), '（%s）' % note if note else ''))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project'); ap.add_argument('action', choices=['export', 'import', 'accept', 'status'])
    ap.add_argument('--changed', action='store_true'); ap.add_argument('--force', action='store_true'); ap.add_argument('--note', default='')
    a = ap.parse_args()
    proj = os.path.abspath(a.project)
    if a.action == 'export':
        cmd_export(proj, a.changed)
    elif a.action == 'import':
        cmd_import(proj, a.force)
    elif a.action == 'accept':
        cmd_accept(proj, a.note)
    else:
        todo = pending(proj)
        for i, pid, role, s in todo[:30]:
            print('%s %s：%s' % (i, ROLE_ZH.get(role, role), s.replace('\n', ' ')[:60]))
        print('去 AI 味：%s' % ('%d 条未处理' % len(todo) if todo else '全部已处理'))
        sys.exit(1 if todo else 0)


if __name__ == '__main__':
    main()
