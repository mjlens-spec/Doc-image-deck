# -*- coding: utf-8 -*-
"""Stage 1 · 标点整理：标题和短句去掉句号，只有详细描述和成段文字保留句号。

Usage: punct.py <project> [--check]
Runs automatically inside `deck whiteboard` before the deck is rendered. Run alone, it re-renders the whiteboard
deck when it changed anything.

Rules (references/01_白板稿.md「标点整理」):
  1. Short-form slots (deck title, kicker, title, subtitle, heading, table caption / header / cell, big number and its
     label, item title, column title, source): a trailing 。 is removed, unless the string holds several sentences.
  2. Body slots (bullet, step, item text, column item, text, quote, callout, takeaway, footnote): the trailing 。 is
     removed when the string is a single sentence shorter than the description threshold (project.json
     punct.long_chars, default 40 visible characters; 30 for text / quote / callout / item text, punct.desc_chars).
     Longer descriptions and multi-sentence paragraphs keep it.
  3. List items (bullet, step, item text, column item) treat a trailing ； like the full stop, so a list written as
     「A；B；C。」 ends consistently once the full stops go.
  4. Speaker notes, layout_hint and image_hint are not touched. Strings listed in project.json punct.keep stay as they are.
Writes outline.json in place and appends every change to 00_白板稿/标点整理.md, together with lists whose items still
end differently (some with 。, some without) for a manual look.
--check changes nothing and exits 1 when a string that should lose its 。 still has it.
"""
import os, re, sys, json, argparse, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deckenv as E

SHORT = {'deck title', 'kicker', 'title', 'subtitle', 'heading', 'table caption', 'table header', 'table cell',
         'big number', 'number label', 'number', 'item title', 'column title', 'source'}
DESC = {'text', 'quote', 'callout', 'item text'}           # description slots: shorter threshold
LIST = {'bullet', 'step', 'column item', 'item text'}      # list items: trailing ； goes with the 。
SENT_END = re.compile(r'[。！？!?]')


def slots(outline):
    """(page id, role, container, key, group) for every printed string; container[key] is the string."""
    yield ('deck', 'deck title', outline, 'title', None)
    for pid, page in zip(E.page_ids(outline), outline['pages']):
        for k in ('kicker', 'title', 'subtitle'):
            yield (pid, k, page, k, None)
        for bi, b in enumerate(page.get('blocks', [])):
            t, g = b.get('type'), '%s/b%d' % (pid, bi + 1)
            if t in ('bullets', 'steps'):
                for i, it in enumerate(b.get('items', [])):
                    role = 'bullet' if t == 'bullets' else 'step'
                    if isinstance(it, str):
                        yield (pid, role, b['items'], i, g)
                    else:
                        yield (pid, role, it, 'text', g)
            elif t == 'numbered':
                for it in b.get('items', []):
                    yield (pid, 'number', it, 'label', None)
                    yield (pid, 'item title', it, 'title', None)
                    yield (pid, 'item text', it, 'text', g)
            elif t == 'kpis':
                for it in b.get('items', []):
                    yield (pid, 'big number', it, 'value', None)
                    yield (pid, 'number label', it, 'label', None)
            elif t == 'table':
                yield (pid, 'table caption', b, 'caption', None)
                for i in range(len(b.get('header', []))):
                    yield (pid, 'table header', b['header'], i, None)
                for row in b.get('rows', []):
                    for i in range(len(row)):
                        yield (pid, 'table cell', row, i, None)
            elif t == 'columns':
                for ci, col in enumerate(b.get('columns', [])):
                    yield (pid, 'column title', col, 'title', None)
                    for i in range(len(col.get('items', []))):
                        yield (pid, 'column item', col['items'], i, '%s/c%d' % (g, ci + 1))
            elif t in ('quote', 'text', 'callout'):
                yield (pid, t, b, 'text', None)
                yield (pid, 'source', b, 'source', None)
            elif t == 'heading':
                yield (pid, 'heading', b, 'text', None)
        yield (pid, 'takeaway', page, 'takeaway', None)
        yield (pid, 'footnote', page, 'footnote', None)


def get(c, k):
    try:
        v = c[k]
    except (KeyError, IndexError, TypeError):
        return None
    return v if isinstance(v, str) else None


def visible_len(s):
    return len(re.sub(r'\s', '', s))


def ends_with_stop(s):
    t = s.rstrip()
    if t.endswith(('。', '．')):
        return True
    return t.endswith('.') and len(t) >= 2 and '㐀' <= t[-2] <= '鿿'


def ends_with_mark(role, s):
    return ends_with_stop(s) or (role in LIST and s.rstrip().endswith(('；', ';')))


def should_strip(role, s, long_chars, desc_chars):
    """True when the trailing full stop (or a list item's ；) of s has to go."""
    if not ends_with_mark(role, s):
        return False
    body = s.rstrip()[:-1]
    if SENT_END.search(body):                   # several sentences: a paragraph, keep the full stop
        return False
    if role in SHORT:
        return True
    return visible_len(s) < (desc_chars if role in DESC else long_chars)


def strip_stop(role, s):
    return s.rstrip()[:-1].rstrip()


def run(proj, check=False):
    """Returns (changes, leftovers, mixed). Writes outline.json and the log unless check is set."""
    cfg = E.load_project(proj)
    pc = cfg.get('punct') or {}
    long_chars, desc_chars = int(pc.get('long_chars', 40)), int(pc.get('desc_chars', 30))
    keep = set(pc.get('keep', []))
    path = os.path.join(proj, E.D_WHITE, 'outline.json')
    outline = json.load(open(path, encoding='utf-8'))
    changes, leftovers, groups = [], [], {}
    for pid, role, c, k, g in slots(outline):
        s = get(c, k)
        if not s or s.strip() in keep:
            continue
        if should_strip(role, s, long_chars, desc_chars):
            new = strip_stop(role, s)
            if check:
                leftovers.append((pid, role, s))
            else:
                c[k] = new
                changes.append((pid, role, s, new))
            s = new
        if g:
            groups.setdefault(g, []).append(ends_with_stop(s))
    mixed = [g for g, ends in groups.items() if len(ends) > 1 and any(ends) and not all(ends)]
    if not check and changes:
        json.dump(outline, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if not check and (changes or mixed):
        log = os.path.join(proj, E.D_WHITE, '标点整理.md')
        new_file = not os.path.exists(log)
        with open(log, 'a', encoding='utf-8') as f:
            if new_file:
                f.write('# 标点整理记录\n\n规则：标题和短句去掉句号；详细描述（单句不少于 %d 字，说明类文字不少于 %d 字）和多句段落保留句号。\n'
                        % (long_chars, desc_chars))
            f.write('\n## %s\n\n' % datetime.datetime.now().strftime('%Y-%m-%d %H:%M'))
            if changes:
                f.write('| 页 | 位置 | 原文 | 改后 |\n|---|---|---|---|\n')
                for pid, role, a, b in changes:
                    f.write('| %s | %s | %s | %s |\n' % (pid, role, a.replace('|', '｜'), b.replace('|', '｜')))
            if mixed:
                f.write('\n列表内句号不统一，需要看一下（改写为同一长度层级，或在 project.json 的 punct.keep 中列出要保留的句子）：%s\n'
                        % '、'.join(mixed))
    return changes, leftovers, mixed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project'); ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    proj = os.path.abspath(a.project)
    changes, leftovers, mixed = run(proj, check=a.check)
    if a.check:
        for pid, role, s in leftovers:
            print('%s %s：%s' % (pid, role, s))
        print('标点检查：%s' % ('%d 处标题或短句仍以句号结尾，运行 deck punct 处理' % len(leftovers) if leftovers else '通过'))
        sys.exit(1 if leftovers else 0)
    print('标点整理：去掉 %d 处句号%s' % (len(changes), '；%d 个列表句号不统一，见 标点整理.md' % len(mixed) if mixed else ''))
    if changes:
        import whiteboard
        print(whiteboard.render(proj))


if __name__ == '__main__':
    main()
