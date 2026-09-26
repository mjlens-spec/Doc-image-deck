# -*- coding: utf-8 -*-
"""Stage 2 · Brand VI research before the three design directions.

Usage: brand.py <project> init      write 01_设计方向/品牌调研.md (template + the materials found) and list what to read
       brand.py <project> check     check the research is filled in (directions.py runs the same check)

Materials the user provides (brand manual, VI PDF, logo files, past decks, screenshots) go into 01_设计方向/品牌材料/
or are listed in project.json "brand_materials" (paths relative to the project or absolute). The agent reads them
(PDF / PPTX pages exported with `deck refs --export`), does a short web search on the brand (official site, flagship
stores, social accounts), and fills six sections of 品牌调研.md:
  一、资料来源  二、品牌色  三、Logo  四、字体与版式  五、视觉风格与禁忌  六、对三个方向的约束
A section may say 不适用：<理由> (for example an internal deck with no client brand). 品牌色 needs at least one #RRGGBB
colour and 资料来源 at least one file path or URL, unless marked 不适用. Every direction.json then carries "brand_fit":
how that direction uses the brand colours, logo and style; directions.py refuses directions without it.
"""
import os, re, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deckenv as E

FILE = '品牌调研.md'
MAT_DIR = '品牌材料'
SECTIONS = [
    ('资料来源', '逐个列出客户提供的材料（文件名、页码、看到了什么）和联网检索的网址与检索日期'),
    ('品牌色', '主色、辅助色写色值 #RRGGBB，注明出处；标出哪一个是强调色'),
    ('Logo', '有哪些版本（彩色、反白、单色、横版、竖版），各自适合浅底还是深底，文件路径；是否要做联合 Logo'),
    ('字体与版式', '标准字与常用字体、物料里的版式特点（网格、留白、标题位置）'),
    ('视觉风格与禁忌', '摄影或插画的风格、质感、关键词；品牌手册里明确禁止的用法'),
    ('对三个方向的约束', '三个方向都要遵守的底线：必须出现的品牌色、Logo 的放置与留白、不能用的颜色和元素；另起一行写「行业常见款：」，描述这个行业的提案最常见的样子，三个方向里最多一个接近它'),
]
NUM = '一二三四五六'
MATERIAL_EXT = ('.pdf', '.pptx', '.key', '.png', '.jpg', '.jpeg', '.webp', '.heic', '.tif', '.tiff', '.ai', '.svg', '.eps')


def path(proj):
    return os.path.join(proj, E.D_DIRS, FILE)


def materials(proj, cfg=None):
    """Brand materials: files in 01_设计方向/品牌材料/ plus project.json brand_materials."""
    cfg = cfg or E.load_project(proj)
    found = []
    for f in sorted(glob.glob(os.path.join(proj, E.D_DIRS, MAT_DIR, '**', '*'), recursive=True)):
        if os.path.isfile(f) and f.lower().endswith(MATERIAL_EXT) and '/导出/' not in f.replace(os.sep, '/'):
            found.append(f)
    for m in cfg.get('brand_materials', []):
        p = m if os.path.isabs(m) else os.path.normpath(os.path.join(proj, m))
        if p not in found:
            found.append(p)
    return found


def template(proj):
    cfg = E.load_project(proj)
    mats = materials(proj, cfg)
    logos = [v for lg in cfg['logos'] for v in (lg.get('light'), lg.get('dark')) if v]
    out = ['# 品牌调研', '',
           '品牌：%s' % ('、'.join(cfg.get('brands', [])) or '（在 project.json 的 brands 里填写）'), '',
           '找到的材料（逐个打开阅读；PDF、PPTX 先用 `deck refs <项目> --export <文件> --pages 1,2 --to %s/%s/导出` 导出为图片）：'
           % (E.D_DIRS, MAT_DIR), '']
    rel = lambda p: os.path.relpath(p, proj) if p.startswith(proj) else p
    out += ['- `%s`%s' % (rel(m), '' if os.path.exists(m) else '（不存在）') for m in mats] or ['- 没有找到。向用户索取，或只用联网检索']
    if logos:
        out += ['- 已配置的 Logo：' + '、'.join('`%s`' % rel(v) for v in logos)]
    out.append('')
    for i, (title, hint) in enumerate(SECTIONS):
        out += ['## %s、%s' % (NUM[i], title), '', '（%s）' % hint, '']
    return '\n'.join(out)


def parse(text):
    """{section title: content without the template hint lines}"""
    parts = re.split(r'^##\s+[一二三四五六七八九十]+、\s*', text, flags=re.M)
    out = {}
    for part in parts[1:]:
        title, _, body = part.partition('\n')
        body = '\n'.join(l for l in body.splitlines() if not re.fullmatch(r'\s*（.*）\s*', l)).strip()   # template hints
        out[title.strip()] = body
    return out


def check(proj):
    """List of problems; empty when the research is complete."""
    p = path(proj)
    if not os.path.exists(p):
        return ['还没有品牌调研：先运行 deck brand <项目> init，读客户材料、联网检索品牌 VI 与 Logo，填写 %s/%s' % (E.D_DIRS, FILE)]
    sec = parse(open(p, encoding='utf-8').read())
    errs = []
    for title, _ in SECTIONS:
        body = sec.get(title)
        if body is None:
            errs.append('品牌调研缺少「%s」一节' % title)
        elif body.startswith('不适用'):
            if len(body) < 8:
                errs.append('品牌调研「%s」写了不适用，但没有写理由' % title)
        elif len(re.sub(r'\s', '', body)) < 12:
            errs.append('品牌调研「%s」还没有填写' % title)
        elif title == '品牌色' and not re.search(r'#[0-9A-Fa-f]{6}\b', body):
            errs.append('品牌调研「品牌色」要写出色值（#RRGGBB）')
        elif title == '资料来源' and not re.search(r'https?://|[\\/]|\.(pdf|pptx|png|jpe?g|key)\b', body, re.I):
            errs.append('品牌调研「资料来源」要列出文件路径或网址')
        elif title == '对三个方向的约束' and not re.search(r'行业常见款[:：]\s*\S{4,}', body):
            errs.append('品牌调研「对三个方向的约束」要另起一行写「行业常见款：」，描述这个行业提案最常见的样子')
    return errs


def main():
    if len(sys.argv) < 3 or sys.argv[2] not in ('init', 'check'):
        raise SystemExit(__doc__)
    proj = os.path.abspath(sys.argv[1])
    p = path(proj)
    if sys.argv[2] == 'init':
        os.makedirs(os.path.join(proj, E.D_DIRS, MAT_DIR), exist_ok=True)
        if os.path.exists(p):
            print('已存在，不覆盖：%s' % p)
        else:
            open(p, 'w', encoding='utf-8').write(template(proj) + '\n')
            print(p)
        mats = materials(proj)
        print('品牌材料 %d 个（放在 %s/%s/ 或写进 project.json 的 brand_materials）' % (len(mats), E.D_DIRS, MAT_DIR))
        for m in mats:
            print('  ' + m)
        print('下一步：逐个阅读材料，联网检索品牌官网、旗舰店和官方账号，填写六节内容，再运行 deck brand <项目> check。')
        return
    errs = check(proj)
    for e in errs:
        print('✗ ' + e)
    if errs:
        sys.exit(1)
    print('品牌调研已完成：%s' % p)


if __name__ == '__main__':
    main()
