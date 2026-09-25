# -*- coding: utf-8 -*-
"""Stage 2 · Visual references: find candidates on disk before asking the user, and export the chosen ones.

Usage:
  refs.py <project> [dir ...] [--max 24] [--depth 3]
      Scan the project folder, its parent folder, the folder of project.json "source" and any extra dirs for images,
      PDFs, PPTX and Keynote files that could serve as a visual reference (mood boards, brand guides, earlier decks,
      KV, posters). Writes 01_设计方向/参考候选/候选清单.md, 候选对照.jpg (thumbnails labelled R01 …) and
      candidates.json. The candidates go to the user at confirmation point 1 together with the whiteboard deck.
  refs.py <project> --export <R03|file> [--pages 1,4] --to 01_设计方向/A/ref
      Turn a chosen reference into PNG images for direction.json "refs": images are copied (HEIC / WebP / TIFF
      converted), PDF pages rendered, PPTX exported through PowerPoint first. Keynote: export a PDF from Keynote.
"""
import os, re, sys, json, glob, shutil, zipfile, argparse, subprocess, datetime, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deckenv as E

IMG = {'.png', '.jpg', '.jpeg', '.webp', '.heic', '.tif', '.tiff'}
DOC = {'.pdf', '.pptx', '.key'}
DOC_KINDS = {'pdf', 'pptx', 'key'}
SKIP_DIRS = {E.D_WHITE, E.D_DIRS, E.D_GEN, E.D_COMP, E.D_EDIT, E.D_QA, 'tmp', 'node_modules', 'venv', '__pycache__',
             '01_原图', '02_分层', '03_QA'}
SKIP_NAME = re.compile(r'logo|标志|icon|图标|二维码|qrcode|favicon|avatar|头像', re.I)
KW_CJK = ['参考', '风格', '视觉', '设计', '灵感', '情绪板', '主视觉', '品牌手册', '案例', '样稿', '样张', '提案', '海报', '版式', '模板', '物料']
KW_LAT = {'ref', 'refs', 'reference', 'references', 'style', 'moodboard', 'mood', 'inspiration', 'kv', 'vi', 'brand',
          'guideline', 'guidelines', 'deck', 'poster', 'layout', 'template', 'lookbook', 'design'}
MAX_VISIT = 30000


def keyword_hits(rel):
    low = rel.lower()
    hits = [k for k in KW_CJK if k in rel]
    toks = set(re.split(r'[^a-z0-9]+', low))
    hits += sorted(k for k in KW_LAT if k in toks)
    return hits


def image_size(p):
    try:
        from PIL import Image
        with Image.open(p) as im:
            return im.size
    except Exception:
        r = subprocess.run(['sips', '-g', 'pixelWidth', '-g', 'pixelHeight', p], capture_output=True, text=True)
        n = re.findall(r'pixel(?:Width|Height): (\d+)', r.stdout)
        return (int(n[0]), int(n[1])) if len(n) == 2 else None


def page_count(p, ext):
    try:
        if ext == '.pdf':
            out = subprocess.run(['pdfinfo', p], capture_output=True, text=True).stdout
            m = re.search(r'Pages:\s+(\d+)', out)
            return int(m.group(1)) if m else None
        if ext == '.pptx':
            with zipfile.ZipFile(p) as z:
                return sum(1 for n in z.namelist() if re.match(r'ppt/slides/slide\d+\.xml$', n))
    except Exception:
        return None


def scan(proj, roots, depth, cfg):
    own = {os.path.abspath(x) for lg in cfg.get('logos', []) for x in (lg.get('light'), lg.get('dark')) if x}
    if cfg.get('source'):
        own.add(os.path.abspath(os.path.join(proj, cfg['source'])))
    seen, found, visited = set(), [], 0
    now = datetime.datetime.now().timestamp()
    for root in roots:
        root = os.path.abspath(root)
        if not os.path.isdir(root):
            continue
        base = root.count(os.sep)
        for d, dirs, files in os.walk(root):
            if visited > MAX_VISIT:
                break
            dirs[:] = [x for x in dirs if not x.startswith('.') and x not in SKIP_DIRS and not x.endswith(('.app', '.photoslibrary'))
                       and os.path.join(d, x).count(os.sep) - base < depth]
            for f in files:
                visited += 1
                if visited > MAX_VISIT:
                    break
                p = os.path.join(d, f)
                ext = os.path.splitext(f)[1].lower()
                if ext not in IMG | DOC or p in seen or p in own or SKIP_NAME.search(f) or f.startswith('.'):
                    continue
                if os.path.dirname(p) == proj and f.startswith(cfg['name'] + '_'):
                    continue                                    # this project's own deliverables
                seen.add(p)
                st = os.stat(p)
                info = dict(path=p, kind=ext[1:], bytes=st.st_size, mtime=st.st_mtime)
                if ext in IMG:
                    if st.st_size < 40000:
                        continue
                    sz = image_size(p)
                    if sz and min(sz) < 480:
                        continue
                    info['size'] = sz
                else:
                    info['pages'] = page_count(p, ext)
                rel = os.path.relpath(p, root)
                hits = keyword_hits(rel)
                score = 3 * min(2, len(hits))
                if ext in DOC:
                    score += 1
                elif info.get('size') and 1.6 <= info['size'][0] / float(info['size'][1]) <= 1.9:
                    score += 1
                if p.startswith(proj + os.sep):
                    score += 1
                if now - st.st_mtime < 180 * 86400:
                    score += 1
                info.update(score=score, hits=hits)
                found.append(info)
    # a folder full of images (exported pages, photo dumps) is represented by its best three
    by_dir = {}
    for c in found:
        if c['kind'] not in DOC_KINDS:
            by_dir.setdefault(os.path.dirname(c['path']), []).append(c)
    for d, lst in by_dir.items():
        if len(lst) > 6:
            lst.sort(key=lambda c: (-c['score'], -c['bytes']))
            for c in lst[3:]:
                c['drop'] = True
            lst[0]['more'] = len(lst) - 3
    found = [c for c in found if not c.get('drop')]
    found.sort(key=lambda c: (-c['score'], -c['mtime']))
    return found


def thumbnail(c, tmp, i):
    """A JPEG preview of the candidate (first page for documents); None when no preview can be made."""
    p, kind = c['path'], c['kind']
    out = os.path.join(tmp, 'r%02d.jpg' % i)
    try:
        if kind in ('png', 'jpg', 'jpeg', 'webp', 'tif', 'tiff'):
            from PIL import Image
            im = Image.open(p).convert('RGB'); im.thumbnail((900, 900)); im.save(out, quality=85)
            return out
        if kind == 'heic':
            subprocess.run(['sips', '-s', 'format', 'jpeg', '-Z', '900', p, '--out', out], capture_output=True, timeout=60)
            return out if os.path.exists(out) else None
        if kind == 'pdf':
            stem = os.path.join(tmp, 'r%02d' % i)
            subprocess.run(['pdftoppm', '-f', '1', '-l', '1', '-scale-to', '900', '-jpeg', '-singlefile', p, stem],
                           capture_output=True, timeout=60)
            return out if os.path.exists(out) else None
        if kind in ('pptx', 'key'):                    # packaged preview first: fast and needs no GUI session
            with zipfile.ZipFile(p) as z:
                names = z.namelist()
                for n in ('docProps/thumbnail.jpeg', 'preview.jpg', 'QuickLook/Thumbnail.jpg'):
                    if n in names:
                        open(out, 'wb').write(z.read(n))
                        from PIL import Image, ImageStat
                        if max(ImageStat.Stat(Image.open(out).convert('L')).stddev) > 3:
                            return out                   # python-pptx files carry a blank template thumbnail
                        os.remove(out)
                        return None
        qd = os.path.join(tmp, 'ql%02d' % i); os.makedirs(qd, exist_ok=True)
        subprocess.run(['qlmanage', '-t', '-s', '900', '-o', qd, p], capture_output=True, timeout=20)
        got = glob.glob(os.path.join(qd, '*.png'))
        if got:
            from PIL import Image
            Image.open(got[0]).convert('RGB').save(out, quality=85)
            return out
    except Exception:
        pass
    return None


def placeholder(tmp, i, text):
    from PIL import Image, ImageDraw
    import contact_sheet
    im = Image.new('RGB', (900, 506), (200, 200, 200))
    ImageDraw.Draw(im).text((30, 230), text, fill=(60, 60, 60), font=contact_sheet.font(36))
    out = os.path.join(tmp, 'r%02d.jpg' % i); im.save(out)
    return out


def human(n):
    return '%.1f MB' % (n / 1e6) if n >= 1e6 else '%d KB' % (n // 1000)


def cmd_scan(a):
    proj = os.path.abspath(a.project)
    cfg = E.load_project(proj)
    roots = [proj, os.path.dirname(proj)]
    if cfg.get('source'):
        roots.append(os.path.dirname(os.path.abspath(os.path.join(proj, cfg['source']))))
    roots += a.dirs
    found = scan(proj, roots, a.depth, cfg)[:a.max]
    out_dir = os.path.join(proj, E.D_DIRS, '参考候选')
    os.makedirs(out_dir, exist_ok=True)
    for old in glob.glob(os.path.join(out_dir, '候选对照*.jpg')):
        os.remove(old)
    cands = {}
    lines = ['# 视觉参考候选', '',
             '在项目目录、上级目录%s中找到 %d 个可能用作视觉参考的文件，按相关程度排序。缩略图见 `候选对照.jpg`。' % (
                 '、原文档所在目录' if cfg.get('source') else '', len(found)), '']
    if found:
        lines += ['| 编号 | 文件 | 类型 | 尺寸 / 页数 | 大小 | 修改日期 | 命中关键词 |', '|---|---|---|---|---|---|---|']
    tmp = tempfile.mkdtemp(prefix='refs_', dir=out_dir)
    tiles = []
    for i, c in enumerate(found, 1):
        rid = 'R%02d' % i
        cands[rid] = c['path']
        dims = ('%d × %d' % tuple(c['size'])) if c.get('size') else ('%s 页' % c['pages'] if c.get('pages') else '—')
        more = '（同目录另有 %d 张）' % c['more'] if c.get('more') else ''
        rel = os.path.relpath(c['path'], os.path.dirname(proj))
        lines.append('| %s | `%s`%s | %s | %s | %s | %s | %s |' % (
            rid, rel.replace('|', '｜'), more, c['kind'].upper(), dims, human(c['bytes']),
            datetime.date.fromtimestamp(c['mtime']).isoformat(), '、'.join(c['hits']) or '—'))
        th = thumbnail(c, tmp, i) or placeholder(tmp, i, '%s（无预览）' % c['kind'].upper())
        tiles.append(('%s  %s' % (rid, os.path.basename(c['path'])[:28]), th))
    if tiles:
        import contact_sheet
        for k in range(0, len(tiles), 12):
            contact_sheet.sheet(tiles[k:k + 12], os.path.join(out_dir, '候选对照%s.jpg' % ('' if len(tiles) <= 12 else '_%d' % (k // 12 + 1))), 4, 420)
    shutil.rmtree(tmp, ignore_errors=True)
    lines += ['', '用法：用户选定的参考用 `deck refs <项目> --export R03 --pages 1,4 --to 01_设计方向/A/ref` 导出为图片，'
              '再写进该方向 direction.json 的 `refs`。用户另给的参考文件同样用 `--export <文件>` 导出。']
    open(os.path.join(out_dir, '候选清单.md'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    json.dump(cands, open(os.path.join(out_dir, 'candidates.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('找到 %d 个候选：%s' % (len(found), os.path.join(out_dir, '候选清单.md')))


def cmd_export(a):
    proj = os.path.abspath(a.project)
    src = a.export
    if re.fullmatch(r'R\d+', src, re.I):
        cands = json.load(open(os.path.join(proj, E.D_DIRS, '参考候选', 'candidates.json'), encoding='utf-8'))
        src = cands['R%02d' % int(src[1:])]
    src = os.path.abspath(src)
    ext = os.path.splitext(src)[1].lower()
    to = os.path.abspath(os.path.join(proj, a.to)) if not os.path.isabs(a.to) else a.to
    os.makedirs(to, exist_ok=True)
    stem = re.sub(r'[^\w㐀-鿿-]+', '_', os.path.splitext(os.path.basename(src))[0])[:40]
    pages = [int(x) for x in a.pages.split(',') if x.strip()] or [1]
    outs = []
    if ext in ('.png', '.jpg', '.jpeg'):
        dst = os.path.join(to, stem + ext); shutil.copy(src, dst); outs.append(dst)
    elif ext in IMG:
        dst = os.path.join(to, stem + '.png')
        subprocess.run(['sips', '-s', 'format', 'png', src, '--out', dst], capture_output=True, check=True); outs.append(dst)
    elif ext in ('.pdf', '.pptx'):
        pdf = src
        if ext == '.pptx':
            sys.path.insert(0, os.path.join(E.HERE, 'editable'))
            import pptrender
            pdf = pptrender.ppt_to_pdf(src, os.path.join(to, stem + '_export.pdf'))
        for pg in pages:
            base = os.path.join(to, '%s_p%02d' % (stem, pg))
            subprocess.run(['pdftoppm', '-f', str(pg), '-l', str(pg), '-scale-to', '1600', '-png', '-singlefile', pdf, base],
                           capture_output=True, check=True)
            outs.append(base + '.png')
        if pdf != src:
            os.remove(pdf)
    else:
        raise SystemExit('Keynote 文件请先在 Keynote 中导出为 PDF，再用 --export <PDF> 导出所需页。')
    for o in outs:
        print(o)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project'); ap.add_argument('dirs', nargs='*')
    ap.add_argument('--max', type=int, default=24); ap.add_argument('--depth', type=int, default=3)
    ap.add_argument('--export', default=''); ap.add_argument('--pages', default=''); ap.add_argument('--to', default='')
    a = ap.parse_args()
    if a.export:
        if not a.to:
            raise SystemExit('--export 需要 --to <目录>，例如 01_设计方向/A/ref')
        cmd_export(a)
    else:
        cmd_scan(a)


if __name__ == '__main__':
    main()
