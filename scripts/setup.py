# -*- coding: utf-8 -*-
"""Install / repair the machine-level runtime of Doc-image-deck（文图方案）. macOS, or Windows 10 22H2 / 11 (2024+).

    deck setup                 install everything that is missing
    deck check                 report only, change nothing (same as setup.py --check)
    deck setup --no-fonts      do not download fonts
    deck setup --no-calib      skip the PowerPoint calibration
Runs with any Python 3.10+ (standard library only); the Python packages go into <runtime>/venv.
Runtime: $DOC_IMAGE_DECK_HOME, default ~/.local/share/doc-image-deck (macOS) or %LOCALAPPDATA%\\doc-image-deck (Windows).
Set DOC_IMAGE_DECK_TORCH_INDEX=https://download.pytorch.org/whl/cu124 on Windows to install a CUDA build of torch.
"""
import os, sys, shutil, subprocess, urllib.request, glob

S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, S)
import hostos as H

CHECK = '--check' in sys.argv
FONTS = '--no-fonts' not in sys.argv
CALIB = '--no-calib' not in sys.argv
MISSING = []
COLOR = sys.stdout.isatty() and not H.IS_WIN


def ok(m):   print(('\033[32m✓\033[0m ' if COLOR else '✓ ') + m, flush=True)
def warn(m): print(('\033[33m!\033[0m ' if COLOR else '! ') + m, flush=True)
def bad(m):  print(('\033[31m✗\033[0m ' if COLOR else '✗ ') + m, flush=True); MISSING.append(m)


BASE_PKGS = ['numpy', 'scipy', 'opencv-python-headless', 'pillow', 'python-pptx', 'lxml', 'fonttools', 'pypdfium2',
             # RapidOCR's own dependencies (it is installed with --no-deps: it asks for opencv-python, which clashes
             # with the headless build above)
             'onnxruntime', 'pyclipper', 'shapely', 'six', 'pyyaml', 'tqdm', 'omegaconf', 'requests', 'colorlog']
NODEPS_PKGS = ['simple-lama-inpainting', 'rapidocr>=3.9,<4']
WIN_PKGS = ['pywin32', 'pillow-heif']
IMPORTS = 'import numpy, scipy, cv2, PIL, pptx, lxml, torch, fontTools, pypdfium2, simple_lama_inpainting, rapidocr'
LAMA_URL = 'https://github.com/enesmsahin/simple-lama-inpainting/releases/download/v0.1.0/big-lama.pt'
LAMA = os.path.join(os.path.expanduser('~'), '.cache', 'torch', 'hub', 'checkpoints', 'big-lama.pt')
FONT_URLS = {'NotoSerifSC-wght.ttf': 'https://github.com/google/fonts/raw/main/ofl/notoserifsc/NotoSerifSC%5Bwght%5D.ttf'}
for w in ('Light', 'DemiLight', 'Regular', 'Medium', 'Bold', 'Black'):
    FONT_URLS['NotoSansCJKsc-%s.otf' % w] = 'https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-%s.otf' % w
HUMANIZER_REPO = 'https://github.com/op7418/Humanizer-zh.git'


def run(cmd, **kw):
    return subprocess.run(cmd, **kw)


def download(url, dst, min_size=0):
    """Download with resume (Range) and retries."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    part = dst + '.part'
    for attempt in range(5):
        have = os.path.getsize(part) if os.path.exists(part) else 0
        req = urllib.request.Request(url, headers={'Range': 'bytes=%d-' % have} if have else {})
        try:
            with urllib.request.urlopen(req, timeout=60) as r, open(part, 'ab' if have and r.status == 206 else 'wb') as f:
                shutil.copyfileobj(r, f, 1 << 20)
            if os.path.getsize(part) >= min_size:
                os.replace(part, dst)
                return True
        except Exception as e:
            warn('下载中断（%s），重试 %d/5' % (type(e).__name__, attempt + 1))
    return False


def step_platform():
    if H.IS_MAC:
        ok('macOS %s' % os.uname().release)
    elif H.IS_WIN:
        b = sys.getwindowsversion().build
        (ok if b >= 19045 else warn)('Windows build %d%s' % (b, '' if b >= 19045 else '：低于 Windows 10 22H2，未测试'))
    else:
        bad('只支持 macOS 与 Windows（需要 Microsoft PowerPoint）'); finish()
    if sys.version_info < (3, 10):
        bad('Python %d.%d 太旧，需要 3.10 或更高（%s）' % (sys.version_info[:2] + (
            'winget install Python.Python.3.12' if H.IS_WIN else 'brew install python',))); finish()
    ok('Python：%s（%d.%d）' % ((sys.executable,) + sys.version_info[:2]))


def step_venv():
    py = H.VENV_PY
    if os.path.exists(py) and run([py, '-c', IMPORTS + (', win32com' if H.IS_WIN else '')], capture_output=True).returncode == 0:
        ok('Python 环境：%s' % os.path.dirname(os.path.dirname(py))); return
    if CHECK:
        bad('Python 环境未就绪：%s' % os.path.join(H.RUNTIME, 'venv')); return
    print('安装 Python 环境到 %s（含 torch，约 1 GB）…' % os.path.join(H.RUNTIME, 'venv'), flush=True)
    os.makedirs(H.RUNTIME, exist_ok=True)
    if not os.path.exists(py):
        run([sys.executable, '-m', 'venv', os.path.join(H.RUNTIME, 'venv')], check=True)
    pip = [py, '-m', 'pip', 'install', '-q']
    steps = [pip[:-1] + ['--upgrade', 'pip', '-q']]
    torch = pip + ['torch'] + (['--index-url', os.environ['DOC_IMAGE_DECK_TORCH_INDEX']] if os.environ.get('DOC_IMAGE_DECK_TORCH_INDEX') else [])
    steps += [torch, pip + BASE_PKGS + (WIN_PKGS if H.IS_WIN else []), pip + ['--no-deps'] + NODEPS_PKGS]
    for st in steps:
        if run(st).returncode != 0:
            bad('Python 依赖安装失败：%s' % ' '.join(st[4:])); return
    ok('Python 环境已安装')


def step_poppler():
    if not H.IS_MAC:
        ok('PDF 渲染：pypdfium2'); return
    if shutil.which('pdftoppm') and shutil.which('pdfimages'):
        ok('poppler：%s' % shutil.which('pdftoppm'))
    elif CHECK or not shutil.which('brew'):
        warn('未装 poppler，PDF 渲染改用 pypdfium2（brew install poppler 可恢复原方式）')
    else:
        (ok if run(['brew', 'install', 'poppler'], capture_output=True).returncode == 0 else warn)('poppler 安装')


def step_lama():
    if os.path.exists(LAMA) and os.path.getsize(LAMA) > 150_000_000:
        ok('LaMa 权重：%s' % LAMA)
    elif CHECK:
        bad('缺 LaMa 权重：%s' % LAMA)
    else:
        print('下载 LaMa 权重（约 196 MB，可断点续传）…', flush=True)
        (ok('LaMa 权重已下载') if download(LAMA_URL, LAMA, 150_000_000) else bad('LaMa 权重下载失败，重跑 deck setup 可续传'))


def step_fonts():
    dest = os.path.join(H.RUNTIME, 'fonts') if H.IS_WIN else os.path.expanduser('~/Library/Fonts')
    # Windows: fontsetup.py installs from <runtime>/fonts, so the files must be there even if a copy exists elsewhere
    miss = [f for f in FONT_URLS if not (os.path.exists(os.path.join(dest, f)) if H.IS_WIN else H.find_font(f))]
    for f in miss:
        if CHECK or not FONTS:
            bad('缺字体：%s' % f); continue
        print('下载字体 %s …' % f, flush=True)
        if not download(FONT_URLS[f], os.path.join(dest, f), 1_000_000):
            bad('字体下载失败：%s' % f)
    if H.IS_WIN and os.path.exists(H.VENV_PY) and all(os.path.exists(os.path.join(dest, f)) for f in FONT_URLS):
        # static serif weights with the typeface names the deck uses, installed for the current user
        r = run([H.VENV_PY, os.path.join(S, 'fontsetup.py'), dest] + (['--check'] if CHECK else []), env=H.child_env())
        if r.returncode:
            bad('字体未安装到 Windows（运行 deck setup）' if CHECK else '字体安装失败')
    if not [m for m in MISSING if '字体' in m]:
        ok('字体：思源宋体 Noto Serif SC、思源黑体 Noto Sans CJK SC')
    if not H.find_font('msyh.ttc', 'msyh.ttf'):
        warn('未装微软雅黑：白板稿仍用微软雅黑排版，本机显示会被替换')


def step_ocr():
    if H.IS_MAC:
        src = os.path.join(S, 'editable', 'ocrbox.swift')
        if os.path.exists(H.OCR_BIN) and os.path.getmtime(H.OCR_BIN) >= os.path.getmtime(src):
            ok('OCR：Apple Vision（%s）' % H.OCR_BIN); return
        if CHECK:
            bad('OCR 工具未编译：%s' % H.OCR_BIN); return
        if not shutil.which('swiftc'):
            bad('缺 swiftc：运行 xcode-select --install 安装命令行工具'); return
        os.makedirs(os.path.dirname(H.OCR_BIN), exist_ok=True)
        r = run(['swiftc', '-O', src, '-o', H.OCR_BIN], capture_output=True)
        (ok('OCR 工具已编译') if r.returncode == 0 else bad('OCR 工具编译失败'))
    else:
        r = run([H.VENV_PY, '-c', 'import rapidocr'], capture_output=True) if os.path.exists(H.VENV_PY) else None
        (ok('OCR：RapidOCR（PP-OCRv6）') if r is not None and r.returncode == 0 else bad('OCR：RapidOCR 未安装（随 Python 环境安装）'))


def step_codex():
    codex = H.codex_exe()
    if not codex:
        hint = 'winget install OpenJS.NodeJS.LTS，再 npm i -g @openai/codex' if H.IS_WIN else 'npm i -g @openai/codex 或 brew install codex'
        bad('缺 Codex CLI（生图用）：%s，然后 codex login' % hint); return
    st = run([codex, 'login', 'status'], capture_output=True, text=True, encoding='utf-8', errors='replace')
    ver = run([codex, '--version'], capture_output=True, text=True, encoding='utf-8', errors='replace').stdout.strip()
    if 'ChatGPT' in (st.stdout or '') + (st.stderr or ''):
        ok('Codex CLI：%s，已用 ChatGPT 账号登录' % ver)
    else:
        bad('Codex CLI 未用 ChatGPT 账号登录：运行 codex login')


def humanizer_dirs():
    return [os.path.join(os.path.expanduser('~'), d, 'skills') for d in ('.agents', '.claude', '.codex')]


def link_dir(src, dst):
    if H.IS_WIN:
        run(['cmd', '/c', 'mklink', '/J', dst, src], capture_output=True)   # a junction needs no admin rights
    else:
        os.symlink(src, dst)


def step_humanizer():
    found = [os.path.join(d, 'humanizer-zh') for d in humanizer_dirs() if os.path.isfile(os.path.join(d, 'humanizer-zh', 'SKILL.md'))]
    if found:
        ok('humanizer-zh：%s' % found[0]); return
    if CHECK:
        bad('缺 humanizer-zh（去 AI 味用）：运行 deck setup 安装'); return
    if not shutil.which('git'):
        bad('缺 git，无法安装 humanizer-zh：安装 git 后重跑，或手动把 %s 下载到 ~/.agents/skills/humanizer-zh' % HUMANIZER_REPO); return
    dst = os.path.join(humanizer_dirs()[0], 'humanizer-zh')
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if run(['git', 'clone', '--depth', '1', HUMANIZER_REPO, dst], capture_output=True).returncode != 0:
        bad('humanizer-zh 下载失败：%s' % HUMANIZER_REPO); return
    for host in humanizer_dirs()[1:]:
        if os.path.isdir(host) and not os.path.exists(os.path.join(host, 'humanizer-zh')):
            link_dir(dst, os.path.join(host, 'humanizer-zh'))
    ok('humanizer-zh 已安装：%s' % dst)


def step_powerpoint():
    if not H.powerpoint_installed():
        bad('缺 Microsoft PowerPoint（用于导出 PDF、标定和比对）'); return
    ok('PowerPoint 已安装')
    try:
        has_table = 'baseline_table' in open(H.CALIB, encoding='utf-8').read()
    except OSError:
        has_table = False
    if has_table:
        ok('PowerPoint 标定：%s' % H.CALIB)
    elif CHECK or not CALIB:
        bad('未做 PowerPoint 标定')
    elif os.path.exists(H.VENV_PY) and not MISSING:
        print('标定 PowerPoint 文字排版（会打开 PowerPoint 约 1 分钟）…', flush=True)
        env = H.child_env()
        r1 = run([H.VENV_PY, os.path.join(S, 'editable', 'calibrate.py'), H.RUNTIME], env=env, capture_output=True, text=True)
        r2 = run([H.VENV_PY, os.path.join(S, 'editable', 'calibrate_table.py'), H.RUNTIME], env=env) if r1.returncode == 0 else r1
        (ok('标定完成') if r1.returncode == 0 and r2.returncode == 0 else bad('标定失败：%s' % (r1.stderr or '')[-400:]))
        shutil.rmtree(os.path.join(H.RUNTIME, 'tmp'), ignore_errors=True)
    else:
        warn('先补齐上面的缺项，再运行 deck setup 做标定')


def finish():
    if MISSING:
        print('\n环境不完整，按上面提示处理后重跑：deck setup')
        sys.exit(2)
    print('\n环境就绪。')
    sys.exit(0)


if __name__ == '__main__':
    step_platform()
    step_venv()
    step_poppler()
    step_lama()
    step_fonts()
    step_ocr()
    step_codex()
    step_humanizer()
    step_powerpoint()
    finish()
