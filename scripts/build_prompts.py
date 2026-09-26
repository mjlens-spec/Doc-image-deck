# -*- coding: utf-8 -*-
"""Stage 2 · Assemble one image-generation prompt per slide.

Usage: build_prompts.py <project> --direction <direction.json> --out <prompts_dir> [--pages p01,p05]

prompt = slide spec + direction style block (light or dark) + what stays fixed across the deck + this slide's
visual brief (message, information structure, how to draw it, focal point, composition skeleton, and the skeletons of
the neighbouring slides so this one differs from them) + layout and imagery hints + verbatim text, grouped by the part
of the drawing it belongs to + diagram and text rules (only the listed text, no logo, no page number, reserved corners
for the logo and page number that compose.py adds later).
Writes <out>/pNN.txt, <out>/index.json ({pid: {tone, file, n, kind, title, skeleton, strings[, guide]}}) and
<out>/direction.json (the direction used, with reference-image paths made absolute; gen_batch.py attaches those images).
--corner-guide (or project.json "corner_guide": true) also writes guide_*.png: a white layout guide with the reserved
corners as pale-red rectangles, which gen_batch.py attaches ahead of the style references.
Refuses to run until the user has approved the whiteboard text (deck approve), see deckenv.whiteboard_approval, and
while the visual plan fails its check (visual.py).
"""
import os, sys, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deckenv as E
import visual
import storyline

CORNER_NAME = {'bl': 'bottom-left', 'br': 'bottom-right', 'tl': 'top-left', 'tr': 'top-right'}

def reserved_corners(cfg, n=None, total=None, pages=None):
    """Corners compose.py will use on slide n, sized from the logo aspect ratio and page-number box
    (no page-number corner on slides that get no page number, such as the cover)."""
    zones = {}
    m = cfg['margin_in']
    for lg in cfg['logos']:
        src = lg.get('light') or lg.get('dark')
        try:
            from PIL import Image
            w, h = Image.open(src).size
            aspect = w / float(h)
        except Exception:
            aspect = 3.0
        wi = m + lg.get('height_in', 0.26) * aspect + 0.45
        zones[lg.get('corner', 'bl')] = max(zones.get(lg.get('corner', 'bl'), 0), wi)
    pn = cfg.get('page_number') or {}
    if pn.get('corner') and (n is None or E.page_number_on(cfg, n, total, pages)):
        zones[pn['corner']] = max(zones.get(pn['corner'], 0), m + 1.0)
    out = []
    for c, wi in zones.items():
        pw = min(40, int(round(wi / 13.333 * 100)) + 2)
        out.append('the %s corner (%s %d%% of the width, %s 9%% of the height)' % (
            CORNER_NAME[c], 'left' if c.endswith('l') else 'right', pw, 'bottom' if c.startswith('b') else 'top'))
    return out

def page_tone(page, direction):
    if page.get('tone') in ('light', 'dark'):
        return page['tone']
    return direction.get('tone', {}).get(page.get('kind', 'content'), 'light')

def brief(page):
    return page.get('visual') if isinstance(page.get('visual'), dict) else {}

def neighbour_line(outline, n):
    """Tell the model which compositions the slides before and after this one use, so it composes this one differently."""
    pages, parts = outline['pages'], []
    for k, where in ((n - 1, 'previous'), (n + 1, 'next')):
        if 1 <= k <= len(pages):
            v = brief(pages[k - 1])
            if v.get('skeleton') in E.SKELETONS:
                parts.append('the %s slide (%d) is %s%s' % (where, k, E.SKELETONS[v['skeleton']][1],
                             (', showing ' + E.STRUCTURES[v['structure']][1].split(':')[0]) if v.get('structure') in E.STRUCTURES else ''))
    if not parts:
        return ''
    return ('Neighbouring slides: %s. This slide must look clearly different from them in composition and in the kind of '
            'visual, while keeping the same design system.' % '; '.join(parts))

def text_lines(page):
    """Verbatim strings in reading order; the strings of a block with a "visual" note are grouped under that note."""
    head = {k: page.get(k) for k in ('kicker', 'title', 'subtitle')}
    tail = {k: page.get(k) for k in ('takeaway', 'footnote')}
    q = lambda role, s: '- %s: "%s"' % (role, s.replace('"', '”'))
    out = [q(r, s) for r, s in E.page_strings(head)]
    for i, b in enumerate(page.get('blocks', []), 1):
        strs = E.page_strings({'blocks': [b]})
        if strs and b.get('visual'):
            out.append('Group %d — draw as: %s' % (i, b['visual']))
            out += ['  ' + q(r, s) for r, s in strs]
        else:
            out += [q(r, s) for r, s in strs]
    return out + [q(r, s) for r, s in E.page_strings(tail)]

ROLE = {'cover': 'cover page', 'section': 'section divider', 'closing': 'closing page', 'agenda': 'agenda page listing the chapters',
        'summary': 'executive summary page: the whole answer on one slide', 'appendix': 'appendix page with supporting detail'}
NO_ICON_HINT = 'no photograph and no icons; typography, rules, numbers and the diagram carry the page'


def page_hints(page, direction):
    """(layout hint, imagery hint, motif) for the page: the cover (and section pages) take the direction's own
    composition and subject when it defines them, so the three directions do not share one cover."""
    v = brief(page)
    layout, img, motif = page.get('layout_hint'), page.get('image_hint'), str(v.get('motif') or '').strip()
    own = direction.get(page.get('kind')) if page.get('kind') in ('cover', 'section') else None
    if isinstance(own, dict):
        layout = own.get('layout') or layout
        if own.get('motif'):
            img, motif = own['motif'], ''
    if motif.startswith('无') or motif.lower().startswith('none'):              # "no picture" is already in the imagery hint
        motif = ''
    return layout, img or NO_ICON_HINT, motif


def avoid_list(cfg, direction):
    allow = set(direction.get('allow') or [])
    if direction.get('imagery_mode') == '3d':
        allow.add('3d')
    avoid = ['any company logo or brand mark%s' % ((' (including %s)' % '、'.join(cfg['brands'])) if cfg.get('brands') else ''),
             'any page number', 'watermark', 'QR code', 'fake phone screenshots or fake app UI', 'gibberish text']
    avoid += [t for k, t in E.BASE_AVOID.items() if k not in allow]
    if direction.get('avoid'):
        avoid.append(direction['avoid'].strip().rstrip('.'))
    return avoid


def build(cfg, outline, page, n, total, direction):
    tone = page_tone(page, direction)
    style = direction.get(tone) or direction.get('light') or ''
    v = brief(page)
    lines = []
    lines.append('Image spec: ONE complete, finished 16:9 landscape presentation slide for a %s, delivered as a single flat image. '
                 'Slide %d of %d. It must read as a designed, print-quality slide, not a mock-up or a photo of a screen.'
                 % (cfg.get('audience', 'Chinese business proposal'), n, total))
    lines.append('')
    lines.append('Design direction "%s" (%s tone):' % (direction.get('name', direction.get('id', '')), tone))
    lines.append(style.strip())
    if direction.get('imagery'):
        lines.append(direction['imagery'].strip())
    mode = E.IMAGERY_MODES.get(direction.get('imagery_mode'))
    if mode:
        lines.append('Imagery mode of this direction: %s. Render the slide imagery below in this mode; when the imagery '
                     'note names a subject that does not suit the mode, keep the subject and translate it into this mode; when it asks '
                     'for no photograph, follow the note.' % mode[1])
    lines.append('Deck system: this is one slide of a %d-slide deck. Keep the design system identical on every slide: background, '
                 'palette, typefaces and weights, title position and size, margins, rules, icon line weight and image grading. '
                 'What changes from slide to slide is the composition and the kind of visual, chosen from this slide\'s content below; '
                 'do not fall back on a generic title-plus-cards template.' % total)
    lines.append('')
    lines.append('Slide role: %s' % ROLE.get(page.get('kind'), 'content page'))
    if v.get('message'):
        lines.append('What the audience must get from this slide: ' + v['message'])
    if v.get('structure') in E.STRUCTURES:
        lines.append('Information structure: ' + E.STRUCTURES[v['structure']][1] + '.')
    own_cover = page.get('kind') in ('cover', 'section') and isinstance(direction.get(page.get('kind')), dict)
    if v.get('form') and not own_cover:                     # the direction's own cover composition replaces the outline's
        lines.append('Draw it as: ' + v['form'])
    if v.get('focal'):
        lines.append('Focal point (the one element with the most visual weight and the accent colour): ' + v['focal'])
    if v.get('skeleton') in E.SKELETONS:
        lines.append('Composition skeleton: ' + E.SKELETONS[v['skeleton']][1] + '.')
    nb = neighbour_line(outline, n)
    if nb:
        lines.append(nb)
    layout, img, motif = page_hints(page, direction)
    if layout:
        lines.append('Composition: ' + layout)
    lines.append('Imagery for this slide: ' + img + (('; motif: ' + motif) if motif else ''))
    lines.append(E.ICON_POLICIES.get(direction.get('icons') or 'none', E.ICON_POLICIES['none'])[1])
    if v.get('structure') and v['structure'] != 'claim':
        lines.append('Diagram logic: every arrow, connector, grouping, size and colour difference must express a relationship '
                     'stated in the text; each label sits on or right next to the shape it names; no decorative arrows, icons '
                     'without meaning or fake charts; shapes that stand for numbers (bars, rings, blocks, band widths) are '
                     'drawn in proportion to those numbers. Label the drawing only with the quoted strings below: no extra '
                     'numbers, percentages, axis values, names or tags, not even ones worked out from the text; words used '
                     'in the drawing directions name shapes and are never written on the slide.')
    lines.append('')
    lines.append('Text (verbatim) — render exactly these strings, in this reading order, with this hierarchy:')
    lines += text_lines(page)
    lines.append('')
    lines.append('Text rules: render ONLY the quoted strings listed above, character by character; "Group … draw as" lines and every '
                 'other instruction in this prompt are directions, never text to show. Simplified Chinese must be exact: no missing, '
                 'extra or substituted characters, no traditional forms. Numbers, units and punctuation exactly as written; never add a '
                 'full stop (。) or any other mark at the end of a string that does not have one above. '
                 'No invented labels, captions, English decoration words, placeholder text or gibberish; paper, notebooks, sticky notes, '
                 'screens and signs inside pictures carry no readable writing (leave them blank or blurred). The title is the largest text; '
                 'body text stays comfortably readable on a meeting-room screen.')
    zones = reserved_corners(cfg, n, total, outline['pages'])
    if zones and page.get('footnote') and any(z.startswith('the bottom') for z in zones):
        lines.append('Footnote placement: the footnote sits just above the reserved bottom corners, never inside them.')
    if zones:
        lines.append('Reserved corners: %s must stay free of text and important elements (plain background or a calm, low-detail '
                     'part of an image is fine; do not draw boxes, tabs or notches there). A logo and a page number are added '
                     'there later.' % ' and '.join(zones))
    lines.append('Avoid: ' + '; '.join(avoid_list(cfg, direction)) + '.')
    return tone, '\n'.join(lines) + '\n'

GUIDE_SIZE = (1672, 941)          # size of the image_gen output


def corner_guide(cfg, pages, n, out_dir):
    """A layout-guide image for slide n: white, with the reserved corners as pale-red rectangles; attached ahead of the
    style references so the model sees where to keep clear. Returns the file name (one file per corner set)."""
    from PIL import Image, ImageDraw
    W, H = GUIDE_SIZE
    zones = []
    m = cfg['margin_in']
    for lg in cfg['logos']:
        src = lg.get('light') or lg.get('dark')
        try:
            w, h = Image.open(src).size
            aspect = w / float(h)
        except Exception:
            aspect = 3.0
        zones.append((lg.get('corner', 'bl'), m + lg.get('height_in', 0.26) * aspect + 0.45))
    pn = cfg.get('page_number') or {}
    if pn.get('corner') and E.page_number_on(cfg, n, len(pages), pages):
        zones.append((pn['corner'], m + 1.0))
    if not zones:
        return None
    name = 'guide_%s.png' % '_'.join(sorted('%s%d' % (c, round(w * 10)) for c, w in zones))
    path = os.path.join(out_dir, name)
    if not os.path.exists(path):
        im = Image.new('RGB', (W, H), 'white')
        d = ImageDraw.Draw(im)
        for c, wi in zones:
            w = int(W * min(0.4, wi / 13.333 + 0.02)); h = int(H * 0.09)
            x0 = 0 if c.endswith('l') else W - w
            y0 = H - h if c.startswith('b') else 0
            d.rectangle([x0, y0, x0 + w - 1, y0 + h - 1], fill=(255, 214, 214), outline=(220, 40, 40), width=3)
        im.save(path)
    return name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project'); ap.add_argument('--direction', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--pages', default='')
    ap.add_argument('--corner-guide', action='store_true',
                    help='attach a layout-guide image that marks the reserved corners (project.json "corner_guide": true does the same)')
    a = ap.parse_args()
    proj = os.path.abspath(a.project)
    cfg = E.load_project(proj)
    outline = E.load_outline(proj)
    ok, msg = E.whiteboard_approval(proj, outline)
    if not ok:
        raise SystemExit(msg)
    serrs, _, spath = storyline.run(proj)
    if serrs:
        raise SystemExit('故事线未通过（%s）：\n  %s' % (spath, '\n  '.join(serrs)))
    errs, warns, plan = visual.run(proj)
    for w in warns:
        print('提示：' + w)
    if errs:
        raise SystemExit('视觉规划未通过（%s）：\n  %s\n按 references/01_白板稿.md「逐页视觉规划」修改 outline.json 各页的 visual，'
                         '再运行 deck visual <项目> 检查。' % (plan, '\n  '.join(errs)))
    direction = json.load(open(a.direction, encoding='utf-8'))
    base = os.path.dirname(os.path.abspath(a.direction))
    direction['refs'] = [r if os.path.isabs(r) else os.path.normpath(os.path.join(base, r)) for r in direction.get('refs', [])]
    os.makedirs(a.out, exist_ok=True)
    json.dump(direction, open(os.path.join(a.out, 'direction.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    ids = E.page_ids(outline)
    want = [p.strip() for p in a.pages.split(',') if p.strip()] or ids
    idx_path = os.path.join(a.out, 'index.json')
    index = json.load(open(idx_path, encoding='utf-8')) if os.path.exists(idx_path) else {}
    for n, (pid, page) in enumerate(zip(ids, outline['pages']), 1):
        if pid not in want:
            continue
        tone, text = build(cfg, outline, page, n, len(ids), direction)
        fn = os.path.join(a.out, pid + '.txt')
        open(fn, 'w', encoding='utf-8').write(text)
        index[pid] = dict(tone=tone, file=pid + '.txt', n=n, kind=page.get('kind', 'content'), title=page.get('title', ''),
                          skeleton=brief(page).get('skeleton'), strings=[s for _, s in E.page_strings(page)])
        if a.corner_guide or cfg.get('corner_guide'):
            g = corner_guide(cfg, outline['pages'], n, a.out)
            if g:
                index[pid]['guide'] = g
        else:
            index[pid].pop('guide', None)
        print(pid, tone, fn)
    json.dump(index, open(idx_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

if __name__ == '__main__':
    main()
