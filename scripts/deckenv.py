# -*- coding: utf-8 -*-
"""Shared paths and helpers for Doc-image-deck（文图方案）.

Runtime (machine-level, created by setup.py):  $DOC_IMAGE_DECK_HOME  (default ~/.local/share/doc-image-deck on macOS,
%LOCALAPPDATA%\\doc-image-deck on Windows); platform differences live in hostos.py
    venv/            Python environment
    bin/ocrbox       macOS Vision OCR tool (Windows: RapidOCR inside the venv)
    fonts/           Windows: font files for fitting
    calibration.json PowerPoint text-placement calibration
Project (one per deck):  <project>/project.json  plus the stage folders below.
"""
import os, re, json, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
import hostos
RUNTIME = hostos.RUNTIME
PY = hostos.VENV_PY
OCR_BIN = hostos.OCR_BIN
CALIB = hostos.CALIB

# stage folders inside a project
D_WHITE = '00_白板稿'
D_DIRS = '01_设计方向'
D_GEN = '02_生图'
D_COMP = '03_合成'
D_EDIT = '04_可编辑'
D_QA = '05_QA'

SW, SH = 12192000, 6858000                     # 16:9 widescreen in EMU

# direction.json "imagery_mode": how a direction draws its pictures. The three directions of a project each use a
# different mode, so they differ in imagery as well as in type, colour and layout.
IMAGERY_MODES = {
    'photo':        ('写实摄影', 'photoreal photography of real scenes, places or people-free environments, natural or cinematic light'),
    'still_life':   ('产品静物', 'studio still life of products and objects, controlled lighting, tabletop compositions, shallow depth of field'),
    'illustration': ('插画', 'editorial illustration (flat, textured or hand-drawn), no photographs'),
    'graphic':      ('纯图形', 'no photographs: abstract geometric shapes, lines, data-inspired graphics and colour fields'),
    'material':     ('材质肌理', 'close-up material and texture imagery (paper, metal, fabric, stone, glass), tactile macro detail'),
    '3d':           ('三维渲染', 'clean 3D-rendered objects and scenes, soft global illumination, no photographs'),
    'typographic':  ('纯文字排版', 'no pictures at all: typography, whitespace, rules and colour blocks carry the page'),
}
DIMS = [('typeface', '字体'), ('palette', '配色'), ('layout', '版式语法'), ('imagery', '配图'), ('texture', '质感'),
        ('diagram', '图示语言')]

# outline.json page "visual" brief (visual.py checks it, build_prompts.py writes it into the prompt).
# structure: how the ideas on the slide relate to each other; decides what kind of diagram the slide gets.
STRUCTURES = {
    'claim':       ('单一论断', 'a single statement: type scale and one strong visual carry the page'),
    'kpi':         ('关键数字', 'a few key numbers: the numbers are the heroes, with a simple graphic that shows their scale or direction'),
    'compare':     ('对比', 'a comparison: the sides are drawn with the same structure next to each other so the differences stand out'),
    'flow':        ('流程 / 链路', 'a sequence: nodes connected by arrows in reading order, each arrow meaning "leads to"'),
    'loop':        ('闭环 / 回流', 'a closed loop: stages in a cycle, with the feedback path drawn explicitly'),
    'funnel':      ('漏斗 / 收窄', 'a funnel: stages narrowing step by step, the loss between stages visible'),
    'timeline':    ('时间轴 / 阶段', 'phases along a time axis from left to right, dates on the axis'),
    'hierarchy':   ('层级 / 分解', 'a breakdown: one whole split into parts (tree, pyramid or nested shapes)'),
    'composition': ('构成 / 占比', 'parts of a whole: a proportional graphic (stacked bar, ring, treemap or waffle) sized by the numbers'),
    'matrix':      ('矩阵 / 分类', 'a matrix: items placed on two dimensions or in a grid of categories'),
    'layers':      ('分层 / 梯度', 'tiers: stacked bands from core to periphery or from top to bottom, one strategy per tier'),
    'roles':       ('分工 / 泳道', 'responsibilities: parallel lanes or columns, one per party'),
    'checklist':   ('清单 / 待办', 'a checklist: items with owner and due date, checkbox-like markers'),
    'list':        ('并列要点', 'parallel points of equal weight'),
}
# skeleton: the composition of the slide; neighbouring slides never share one, so the deck does not look templated.
SKELETONS = {
    'hero':     ('满版主视觉', 'one dominant visual or very large type fills the slide, little text'),
    'split':    ('左右分屏', 'two panels side by side (about 40/60 or 50/50): text on one side, the visual on the other'),
    'diagram':  ('整幅图示', 'title on top, one wide diagram filling at least two thirds of the slide'),
    'cards':    ('并列卡片', 'three or four equal cards or columns in a row'),
    'bignum':   ('大数字', 'one to three very large numbers dominate, with a supporting graphic'),
    'table':    ('表格', 'a table or grid of cells dominates the slide'),
    'bands':    ('横向分层', 'horizontal bands stacked from top to bottom, one tier per band'),
    'radial':   ('中心放射', 'a central element with the other items arranged around it or on a ring'),
    'asym':     ('非对称', 'an asymmetric layout: one large visual block and a narrow text column'),
    'quadrant': ('四象限', 'a 2 × 2 grid of quadrants'),
}

# page kinds. agenda / summary / appendix are content-like pages with a fixed job; appendix pages come after the closing
# page, are numbered A1, A2 … and do not count toward max_pages.
KINDS = {'cover': '封面', 'agenda': '目录', 'summary': '执行摘要', 'section': '章节页', 'content': '内容页',
         'closing': '封底', 'appendix': '附录'}
CONTENT_KINDS = ('content', 'summary', 'agenda', 'appendix')     # pages that carry a title bar and body text

# project.json "deck_mode": what the deck is for. present = shown and spoken to (one point per slide, detail in the
# notes); read = sent and read without a presenter (self-contained pages, detail in an appendix). Default read.
MODES = {'present': '演讲稿', 'read': '阅读稿'}

# per-skeleton capacity: (body CJK characters, printed strings) for present / read. Body = every printed string except
# kicker, title and subtitle; strings = every printed string except table header and cells (a table is limited by
# TABLE_MAX instead). read values: the 1.2.1 test maxima + ~10% (all passed the first text check); present values are
# starting values without test data yet.
CAPACITY = {
    'hero':     {'present': (40, 5),   'read': (80, 12)},
    'bignum':   {'present': (60, 8),   'read': (120, 12)},
    'split':    {'present': (100, 10), 'read': (190, 25)},
    'asym':     {'present': (100, 10), 'read': (190, 25)},
    'cards':    {'present': (100, 10), 'read': (190, 16)},
    'diagram':  {'present': (120, 14), 'read': (250, 28)},
    'bands':    {'present': (120, 14), 'read': (250, 28)},
    'radial':   {'present': (120, 14), 'read': (250, 28)},
    'quadrant': {'present': (120, 14), 'read': (250, 28)},
    'table':    {'present': (120, 99), 'read': (250, 99)},
}
TABLE_MAX = (6, 5)          # data rows × columns
TITLE_MAX, KICKER_MAX = 30, 8

# direction.json "axes": one value per axis, so the three directions are compared on fixed options instead of free text.
AXES = {
    'typeface': ('字体', {'serif_title': '宋体标题 + 黑体正文', 'sans_bold': '粗黑体标题 + 黑体正文', 'serif_book': '宋体为主的书卷气',
                          'contrast': '黑宋强对比混排', 'rounded': '圆体或手写点缀'}),
    'layout':   ('版式语法', {'swiss_grid': '瑞士网格、严格对齐', 'magazine_asym': '杂志式非对称', 'centered': '居中对称、仪式感',
                            'modular': '模块卡片', 'fullbleed': '满版图上叠字'}),
    'texture':  ('质感', {'flat_print': '平面印刷', 'paper': '纸张压印、烫金', 'cinematic': '光影摄影、电影感',
                         'grain': '胶片颗粒、粗网点', 'gloss': '玻璃与光泽'}),
    'diagram':  ('图示语言', {'hairline': '发丝线矢量', 'solid': '实心色块', 'hand_drawn': '手绘线', 'isometric': '等距几何',
                            'print_block': '版画、印章肌理'}),
    'color_strategy': ('配色策略', {'restrained': '克制：中性色为主，强调色只用在焦点', 'dominant': '一色主导：主色占 30–60%',
                                   'multi': '多色：三到四个等权颜色', 'drenched': '满铺：整页铺主色'}),
}
AXES_DISTINCT = ('typeface', 'layout', 'texture', 'diagram')     # differ pairwise; color_strategy: at least two kinds
ICON_POLICIES = {
    'none':    ('不画图标', 'Icons: draw no icons or pictograms anywhere (no line icons in front of list items, cards, nodes or rows). '
                          'Hierarchy comes from numbers, type weight, rules and colour. Simple marks that the drawing directions '
                          'name (ticks, crosses, checkboxes, arrows) are drawing elements and are fine.'),
    'planned': ('只画规划里的图标', 'Icons: draw an icon only where the drawing directions name one, and only that icon; add no '
                                 'other icons or pictograms.'),
    'illustrative': ('允许插画小图', 'Icons: small illustrations are allowed where the imagery note asks for them; no rows of '
                                    'generic line icons.'),
}
TEMPERATURES = {'safe': '行业常见款', 'distinct': '与行业常见款拉开'}
# looks an image model falls into by default; banned on every slide unless the direction lists the key in "allow"
BASE_AVOID = {
    '3d':        'glossy plastic 3D objects, isometric blocks and 3D bar charts',
    'glass':     'glassmorphism and frosted-glass panels',
    'glow':      'glow, neon and light trails',
    'gradient':  'blue-to-cyan gradients on white (SaaS-dashboard look)',
    'float':     'floating cards with drop shadows',
    'underline': 'a short decorative rule under the title',
    'badges':    'number badges (01, 02 …) that are not among the quoted strings',
    'robot':     'robots, androids or helmeted figures standing for AI or agents',
}


def deck_mode(cfg):
    m = (cfg or {}).get('deck_mode') or 'read'
    return m if m in MODES else 'read'


CJK_RE = re.compile(r'[㐀-鿿]')

def cjk_len(s):
    return len(CJK_RE.findall(s or ''))


def page_load(page):
    """(body CJK characters, printed strings, (table rows, table columns) of the largest table) for the capacity check."""
    body, n, table = 0, 0, (0, 0)
    for role, s in page_strings(page):
        if role in ('table header', 'table cell'):
            if role == 'table cell':
                body += cjk_len(s)
            continue
        n += 1
        if role not in ('kicker', 'title', 'subtitle'):
            body += cjk_len(s)
    for b in page.get('blocks', []):
        if b.get('type') == 'table':
            rows = b.get('rows', [])
            cols = max([len(b.get('header', []))] + [len(r) for r in rows] or [0])
            table = max(table, (len(rows), cols))
    return body, n, table


def page_labels(cfg, pages):
    """Page-number label per slide ('' = no number): the cover and the closing page skip it by default, appendix pages
    are numbered A1, A2 …, every other slide by its position. pages: outline pages (only kind is read) or a count."""
    if isinstance(pages, int):
        pages = [{}] * pages
    pn = (cfg or {}).get('page_number') or {}
    total = len(pages)
    has_closing = any(p.get('kind') == 'closing' for p in pages)
    out, app = [], 0
    for n, p in enumerate(pages, 1):
        kind = p.get('kind')
        if kind == 'appendix':
            app += 1
        if not pn.get('corner'):
            out.append('')
        elif n == 1 and pn.get('skip_first', True):
            out.append('')
        elif pn.get('skip_last', True) and (kind == 'closing' or (not has_closing and n == total)):
            out.append('')
        elif kind == 'appendix':
            out.append('A%d' % app)
        else:
            out.append(pn.get('format', '{:02d}').format(n))
    return out


def load_project(proj):
    p = os.path.join(proj, 'project.json')
    cfg = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}
    cfg.setdefault('name', os.path.basename(os.path.abspath(proj)))
    cfg.setdefault('suffix', 'AC_%sA' % datetime.date.today().strftime('%m%d'))
    cfg.setdefault('logos', [])
    for lg in cfg['logos']:                        # logo paths may be relative to the project folder
        for k in ('light', 'dark'):
            if lg.get(k) and not os.path.isabs(lg[k]):
                lg[k] = os.path.normpath(os.path.join(os.path.abspath(proj), lg[k]))
    cfg.setdefault('page_number', {'corner': 'br', 'skip_first': True, 'skip_last': True,
                                   'format': '{:02d}', 'font': 'Arial', 'size_pt': 11})
    cfg.setdefault('margin_in', 0.8)
    cfg.setdefault('parallel', 4)
    cfg.setdefault('upscale', 2)
    return cfg


def page_number_on(cfg, n, total, pages=None):
    """Whether compose.py puts a page number on slide n of total (the cover and closing slides skip it by default;
    pass the outline pages so a closing page followed by an appendix is recognised)."""
    return bool(page_labels(cfg, pages if pages else total)[n - 1])


def save_project(proj, cfg):
    json.dump(cfg, open(os.path.join(proj, 'project.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def update_project(proj, **fields):
    """Write fields into project.json without adding the defaults that load_project fills in."""
    p = os.path.join(proj, 'project.json')
    raw = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}
    raw.update(fields)
    save_project(proj, raw)


def out_name(cfg, label, ext):
    """<name>_<label>_<suffix>.<ext>, e.g. 秋季上新方案_图文版_AC_0925A.pptx"""
    return '%s_%s_%s.%s' % (cfg['name'], label, cfg['suffix'], ext)


def load_outline(proj):
    return json.load(open(os.path.join(proj, D_WHITE, 'outline.json'), encoding='utf-8'))


def page_ids(outline):
    return [p.get('id') or 'p%02d' % (i + 1) for i, p in enumerate(outline['pages'])]


def page_strings(page):
    """Every string that must appear on the slide, in reading order, with its role."""
    out = []
    def add(role, s):
        if isinstance(s, str) and s.strip():
            out.append((role, s.strip()))
    add('kicker', page.get('kicker'))
    add('title', page.get('title'))
    add('subtitle', page.get('subtitle'))
    for b in page.get('blocks', []):
        t = b.get('type')
        if t in ('bullets', 'steps'):
            for it in b.get('items', []):
                add('bullet' if t == 'bullets' else 'step', it if isinstance(it, str) else it.get('text'))
        elif t == 'numbered':
            for it in b.get('items', []):
                add('number', it.get('label')); add('item title', it.get('title')); add('item text', it.get('text'))
        elif t == 'kpis':
            for it in b.get('items', []):
                add('big number', it.get('value')); add('number label', it.get('label'))
        elif t == 'table':
            add('table caption', b.get('caption'))
            for h in b.get('header', []):
                add('table header', h)
            for row in b.get('rows', []):
                for c in row:
                    add('table cell', c)
        elif t == 'columns':
            for col in b.get('columns', []):
                add('column title', col.get('title'))
                for it in col.get('items', []):
                    add('column item', it)
        elif t in ('quote', 'text', 'callout'):
            add(t, b.get('text')); add('source', b.get('source'))
        elif t == 'heading':
            add('heading', b.get('text'))
    add('takeaway', page.get('takeaway'))
    add('footnote', page.get('footnote'))
    return out


def text_signature(outline):
    """Short hash of every string that will be printed on the slides: the text the user approves."""
    import hashlib
    h = hashlib.sha256((outline.get('title') or '').encode('utf-8'))
    for pid, page in zip(page_ids(outline), outline['pages']):
        h.update(('\n#' + pid).encode('utf-8'))
        for role, s in page_strings(page):
            h.update(('\n%s\t%s' % (role, s)).encode('utf-8'))
    return h.hexdigest()[:16]


def whiteboard_approval(proj, outline=None):
    """(ok, message): the user approved the whiteboard text (deck approve) and it has not changed since."""
    outline = outline or load_outline(proj)
    ap = (load_project(proj).get('approval') or {}).get('whiteboard')
    if not ap:
        return False, ('白板稿还没有经过用户确认。先把白板稿 PPTX 发给用户确认（确认点 1），'
                       '用户确认后运行 deck approve <项目>，再做设计方向和生图。')
    if ap.get('signature') != text_signature(outline):
        return False, ('白板稿文字在 %s 确认之后又改过。把改动告诉用户并得到确认后，重新运行 deck approve <项目>。'
                       % ap.get('time', '上次'))
    return True, '白板稿已确认（%s）' % ap.get('time', '')


PUNCT = {'，': ',', '。': '.', '：': ':', '；': ';', '（': '(', '）': ')', '“': '"', '”': '"', '—': '-', '–': '-', '−': '-',
         '、': ',', '！': '!', '？': '?', '｜': '|', '／': '/', '「': '"', '」': '"', '·': '', '•': '', '×': 'X', '✕': 'X'}

def norm(s):
    """Compare text regardless of punctuation form, spaces and case."""
    s = ''.join(PUNCT.get(c, c) for c in s)
    return re.sub(r'[\s"\'.,;:!?()/|\-~·+*#]', '', s).upper()


def ensure_runtime(need_ocr=False, need_calib=False):
    miss = []
    if not os.path.exists(PY):
        miss.append('Python 环境 %s' % PY)
    if need_ocr and not hostos.ocr_ready():
        miss.append('OCR 工具（macOS：%s；Windows：rapidocr）' % OCR_BIN)
    if need_calib and not os.path.exists(CALIB):
        miss.append('PowerPoint 标定 %s' % CALIB)
    if miss:
        raise SystemExit('运行环境不完整：%s。请先运行 deck setup' % '；'.join(miss))
