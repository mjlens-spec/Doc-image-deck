# -*- coding: utf-8 -*-
"""Platform layer: everything that differs between macOS and Windows goes through here.

                 macOS                                   Windows 10 22H2 / Windows 11 (2024 or later)
runtime          ~/.local/share/doc-image-deck           %LOCALAPPDATA%\\doc-image-deck
OCR              Apple Vision (bin/ocrbox)               RapidOCR: PaddleOCR models on ONNX Runtime (ocr_rapid.py)
PDF              poppler when installed, else pdfium     pypdfium2
PowerPoint       AppleScript (editable/pptrender.py)     COM automation through pywin32 (editable/pptrender.py)
fonts            ~/Library/Fonts                         <runtime>\\fonts (files) + per-user installed fonts

For testing the Windows code paths on a Mac: DOC_IMAGE_DECK_OCR=rapid, DOC_IMAGE_DECK_PDF=pdfium.
Only the standard library is imported at module level.
"""
import os, sys, glob, shutil, subprocess

IS_WIN = os.name == 'nt'
IS_MAC = sys.platform == 'darwin'
HERE = os.path.dirname(os.path.abspath(__file__))


def runtime_dir():
    env = os.environ.get('DOC_IMAGE_DECK_HOME')
    if env:
        return os.path.abspath(os.path.expanduser(env))
    if IS_WIN:
        base = os.environ.get('LOCALAPPDATA') or os.path.join(os.path.expanduser('~'), 'AppData', 'Local')
        return os.path.join(base, 'doc-image-deck')
    return os.path.expanduser('~/.local/share/doc-image-deck')


RUNTIME = runtime_dir()
VENV_PY = os.path.join(RUNTIME, 'venv', 'Scripts', 'python.exe') if IS_WIN else os.path.join(RUNTIME, 'venv', 'bin', 'python')
OCR_BIN = os.path.join(RUNTIME, 'bin', 'ocrbox')                  # macOS only
CALIB = os.path.join(RUNTIME, 'calibration.json')


def child_env(**extra):
    """Environment for child processes: UTF-8 everywhere (Windows consoles default to a legacy code page)."""
    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
    env.update(extra)
    return env


# ─────────────────────────────── fonts
def font_dirs():
    if IS_WIN:
        local = os.environ.get('LOCALAPPDATA', '')
        return [os.path.join(RUNTIME, 'fonts'), os.path.join(local, 'Microsoft', 'Windows', 'Fonts'),
                os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')]
    return [os.path.expanduser('~/Library/Fonts'), '/Library/Fonts', '/System/Library/Fonts/Supplemental',
            '/System/Library/Fonts', '/usr/share/fonts', os.path.expanduser('~/.local/share/fonts')]


def find_font(*names):
    """Path of the first font file found among names (file names such as NotoSansCJKsc-Bold.otf, msyh.ttc)."""
    for n in names:
        for d in font_dirs():
            p = os.path.join(d, n)
            if os.path.isfile(p):
                return p
    return None


UI_BOLD = ('NotoSansCJKsc-Bold.otf', 'msyhbd.ttc', 'msyh.ttc', 'Songti.ttc', 'simhei.ttf')
UI_REGULAR = ('NotoSansCJKsc-Regular.otf', 'msyh.ttc', 'Songti.ttc', 'simhei.ttf')


def ui_font(size, bold=False):
    """A CJK-capable PIL font for labels on review sheets."""
    from PIL import ImageFont
    p = find_font(*(UI_BOLD if bold else UI_REGULAR))
    try:
        return ImageFont.truetype(p, size) if p else ImageFont.load_default()
    except Exception:
        return ImageFont.load_default()


# ─────────────────────────────── OCR
def ocr_backend():
    forced = os.environ.get('DOC_IMAGE_DECK_OCR', '').lower()
    if forced in ('rapid', 'vision'):
        return forced
    return 'vision' if IS_MAC and os.path.exists(OCR_BIN) else 'rapid'


def ocr_cmd(work=None):
    """Command prefix of the OCR tool. Both tools take `<image>` or `--batch <list.txt>` and print the same JSON:
    lines with text, conf, x0 y0 x1 y1 (pixels, origin top-left), chars (one box per character) and alts."""
    if ocr_backend() == 'vision':
        for b in ([os.path.join(work, 'bin', 'ocrbox')] if work else []) + [OCR_BIN]:
            if os.path.exists(b):
                return [b]
    return [sys.executable, os.path.join(HERE, 'ocr_rapid.py')]


def run_ocr(args, work=None):
    """Run the OCR tool with args and return its stdout (JSON text)."""
    r = subprocess.run(ocr_cmd(work) + list(args), capture_output=True, text=True, encoding='utf-8', env=child_env())
    if r.returncode != 0 and not r.stdout:
        raise RuntimeError('OCR failed: ' + (r.stderr or '').strip()[-800:])
    return r.stdout


def ocr_ready():
    if ocr_backend() == 'vision':
        return True
    try:
        import rapidocr  # noqa: F401
        return True
    except Exception:
        return False


# ─────────────────────────────── PDF
def pdf_backend():
    forced = os.environ.get('DOC_IMAGE_DECK_PDF', '').lower()
    if forced in ('pdfium', 'poppler'):
        return forced
    return 'poppler' if shutil.which('pdftoppm') and shutil.which('pdfinfo') else 'pdfium'


def pdf_page_count(pdf):
    if pdf_backend() == 'poppler':
        out = subprocess.run(['pdfinfo', pdf], capture_output=True, text=True).stdout
        for line in out.splitlines():
            if line.startswith('Pages:'):
                return int(line.split()[1])
        return 0
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(pdf)
    try:
        return len(doc)
    finally:
        doc.close()


def render_pdf(pdf, prefix, dpi=None, size=None, long_side=None, first=None, last=None, fmt='png', single=False):
    """Render PDF pages to images, named like pdftoppm: <prefix>-<n>.<ext> (n zero-padded to the page-count
    width) or <prefix>.<ext> with single=True. Scale by dpi, by size=(W, H) or by long_side. Returns the paths."""
    ext = 'jpg' if fmt in ('jpg', 'jpeg') else 'png'
    n = pdf_page_count(pdf)
    first, last = first or 1, min(last or n, n)
    if single:
        last = first
    if pdf_backend() == 'poppler':
        cmd = ['pdftoppm', '-jpeg' if ext == 'jpg' else '-png', '-f', str(first), '-l', str(last)]
        if dpi:
            cmd += ['-r', str(dpi)]
        if size:
            cmd += ['-scale-to-x', str(size[0]), '-scale-to-y', str(size[1])]
        if long_side:
            cmd += ['-scale-to', str(long_side)]
        if single:
            cmd.append('-singlefile')
        subprocess.run(cmd + [pdf, prefix], check=True, capture_output=True)
    else:
        import pypdfium2 as pdfium
        from PIL import Image
        doc = pdfium.PdfDocument(pdf)
        width = len(str(n))
        try:
            for k in range(first, last + 1):
                page = doc[k - 1]
                wpt, hpt = page.get_size()
                if dpi:
                    scale = dpi / 72.0
                elif size:
                    scale = max(size[0] / wpt, size[1] / hpt)
                elif long_side:
                    scale = long_side / max(wpt, hpt)
                else:
                    scale = 150 / 72.0
                im = page.render(scale=scale).to_pil().convert('RGB')
                if size and im.size != tuple(size):
                    im = im.resize(tuple(size), Image.LANCZOS)
                out = '%s.%s' % (prefix, ext) if single else '%s-%0*d.%s' % (prefix, width, k, ext)
                im.save(out, quality=92) if ext == 'jpg' else im.save(out)
                page.close()
        finally:
            doc.close()
    if single:
        return ['%s.%s' % (prefix, ext)]
    return sorted(glob.glob(glob.escape(prefix) + '-*.' + ext))


def pdf_page_images(pdf, page_no, tmp):
    """Embedded images of one page as PIL images, largest first (the full-bleed picture of an image deck)."""
    from PIL import Image
    if pdf_backend() == 'poppler':
        for f in glob.glob(os.path.join(tmp, '*')):
            os.remove(f)
        subprocess.run(['pdfimages', '-png', '-f', str(page_no), '-l', str(page_no), pdf, os.path.join(tmp, 'i')],
                       check=True, capture_output=True)
        files = sorted(glob.glob(os.path.join(tmp, 'i-*.png')), key=lambda f: -os.path.getsize(f))
        return [Image.open(f) for f in files]
    import pypdfium2 as pdfium
    import pypdfium2.raw as pdfium_c
    doc = pdfium.PdfDocument(pdf)
    out = []
    try:
        page = doc[page_no - 1]
        for obj in page.get_objects(filter=(pdfium_c.FPDF_PAGEOBJ_IMAGE,)):
            try:
                out.append(obj.get_bitmap(render=False).to_pil())
            except Exception:
                pass
        page.close()
    finally:
        doc.close()
    return sorted(out, key=lambda im: -(im.size[0] * im.size[1]))


# ─────────────────────────────── images and previews
def image_to_png(src, dst, max_side=None):
    """Convert any supported image (HEIC through pillow-heif, or sips on macOS) to PNG / JPEG at dst."""
    from PIL import Image
    try:
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except Exception:
            pass
        im = Image.open(src).convert('RGB')
        if max_side:
            im.thumbnail((max_side, max_side))
        im.save(dst, quality=88)
        return dst
    except Exception:
        if IS_MAC:
            cmd = ['sips', '-s', 'format', 'jpeg' if dst.lower().endswith(('.jpg', '.jpeg')) else 'png']
            if max_side:
                cmd += ['-Z', str(max_side)]
            subprocess.run(cmd + [src, '--out', dst], capture_output=True, timeout=60)
            return dst if os.path.exists(dst) else None
        return None


def quicklook_thumbnail(src, out_dir, size=900):
    """System thumbnail of a document (macOS Quick Look); None elsewhere."""
    if not IS_MAC:
        return None
    try:
        subprocess.run(['qlmanage', '-t', '-s', str(size), '-o', out_dir, src], capture_output=True, timeout=20)
    except Exception:
        return None
    got = glob.glob(os.path.join(out_dir, '*.png'))
    return got[0] if got else None


# ─────────────────────────────── external programs
def codex_exe():
    """Full path of the Codex CLI (on Windows the npm shim is codex.cmd, which CreateProcess only finds by path)."""
    return shutil.which('codex')


def powerpoint_installed():
    if IS_MAC:
        return os.path.isdir('/Applications/Microsoft PowerPoint.app')
    if IS_WIN:
        try:
            import winreg
            winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r'PowerPoint.Application\CLSID'))
            return True
        except OSError:
            return False
    return False


def ppt_stage_dir():
    """Where PowerPoint for Mac may open files without a permission prompt (its sandbox container)."""
    return os.path.expanduser('~/Library/Containers/com.microsoft.Powerpoint/Data/tmp/deckrender') if IS_MAC else None
