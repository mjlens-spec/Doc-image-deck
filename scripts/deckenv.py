# -*- coding: utf-8 -*-
"""Shared paths and helpers for Doc-image-deck（文图方案）.

Runtime (machine-level, created by setup.sh):  $DOC_IMAGE_DECK_HOME  (default ~/.local/share/doc-image-deck)
    venv/            Python environment
    bin/ocrbox       macOS Vision OCR tool
    calibration.json PowerPoint text-placement calibration
Project (one per deck):  <project>/project.json  plus the stage folders below.
"""
import os, re, json, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
RUNTIME = os.path.expanduser(os.environ.get('DOC_IMAGE_DECK_HOME', '~/.local/share/doc-image-deck'))
PY = os.path.join(RUNTIME, 'venv', 'bin', 'python')
OCR_BIN = os.path.join(RUNTIME, 'bin', 'ocrbox')
CALIB = os.path.join(RUNTIME, 'calibration.json')

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
DIMS = [('typeface', '字体'), ('palette', '配色'), ('layout', '版式语法'), ('imagery', '配图'), ('texture', '质感')]


def load_project(proj):
    p = os.path.join(proj, 'project.json')
    cfg = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}
    cfg.setdefault('name', os.path.basename(os.path.abspath(proj)))
    cfg.setdefault('suffix', 'AC_%sA' % datetime.date.today().strftime('%m%d'))
    cfg.setdefault('logos', [])
    cfg.setdefault('page_number', {'corner': 'br', 'skip_first': True, 'skip_last': True,
                                   'format': '{:02d}', 'font': 'Arial', 'size_pt': 11})
    cfg.setdefault('margin_in', 0.8)
    cfg.setdefault('parallel', 4)
    cfg.setdefault('upscale', 2)
    return cfg


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
    if need_ocr and not os.path.exists(OCR_BIN):
        miss.append('OCR 工具 %s' % OCR_BIN)
    if need_calib and not os.path.exists(CALIB):
        miss.append('PowerPoint 标定 %s' % CALIB)
    if miss:
        raise SystemExit('运行环境不完整：%s。请先运行 scripts/setup.sh' % '；'.join(miss))
