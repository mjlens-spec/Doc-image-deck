# -*- coding: utf-8 -*-
"""Windows · fonts for the editable deck. Run by setup.py with the runtime's Python (needs fontTools).

PowerPoint for Windows looks fonts up by their Windows family name. The deck names the serif weights
"Noto Serif SC Light / Medium / SemiBold / Black" and "Noto Serif SC" (Regular, Bold), as the named instances of
the variable font are called on macOS. This builds one static font per weight from the same variable font, with
exactly those names, and installs them and the Noto Sans CJK SC files for the current user (no admin rights):
file into %LOCALAPPDATA%\\Microsoft\\Windows\\Fonts, value under HKCU\\...\\Fonts, then a WM_FONTCHANGE broadcast.
The variable font itself stays in <runtime>\\fonts for text fitting only.

Usage: fontsetup.py <fonts_dir> [--check] [--build-only <out_dir>]
--build-only writes the static serif fonts to out_dir without installing (used by tests on any platform).
"""
import os, sys, shutil

SERIF = [  # (weight name, wght, family (name ID 1), subfamily (name ID 2))
    ('Light', 300, 'Noto Serif SC Light', 'Regular'),
    ('Regular', 400, 'Noto Serif SC', 'Regular'),
    ('Medium', 500, 'Noto Serif SC Medium', 'Regular'),
    ('SemiBold', 600, 'Noto Serif SC SemiBold', 'Regular'),
    ('Bold', 700, 'Noto Serif SC', 'Bold'),
    ('Black', 900, 'Noto Serif SC Black', 'Regular'),
]
SANS = ['Light', 'DemiLight', 'Regular', 'Medium', 'Bold', 'Black']
REG = r'Software\Microsoft\Windows NT\CurrentVersion\Fonts'


def build_serif(vf_path, out_dir):
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer
    os.makedirs(out_dir, exist_ok=True)
    outs = []
    for wname, wght, family, sub in SERIF:
        out = os.path.join(out_dir, 'NotoSerifSC-%s.ttf' % wname)
        outs.append(out)
        if os.path.exists(out):
            continue
        f = instancer.instantiateVariableFont(TTFont(vf_path), {'wght': wght}, inplace=False)
        full = 'Noto Serif SC %s' % wname
        ps = 'NotoSerifSC-%s' % wname
        name = f['name']
        name.names = [n for n in name.names if n.nameID not in (1, 2, 3, 4, 6, 16, 17, 21, 22, 25)]
        for nid, text in ((1, family), (2, sub), (3, '%s;static-instance' % ps), (4, full), (6, ps),
                          (16, 'Noto Serif SC'), (17, wname)):
            name.setName(text, nid, 3, 1, 0x409)
        f['OS/2'].usWeightClass = wght
        sel = f['OS/2'].fsSelection & ~(1 | 1 << 5 | 1 << 6)
        f['OS/2'].fsSelection = sel | (1 << 5 if sub == 'Bold' else 1 << 6)
        f['head'].macStyle = (f['head'].macStyle & ~1) | (1 if sub == 'Bold' else 0)
        for t in ('STAT', 'fvar', 'avar'):
            if t in f:
                del f[t]
        f.save(out)
        print('已生成 %s' % os.path.basename(out), flush=True)
    return outs


def font_title(path):
    from fontTools.ttLib import TTFont
    f = TTFont(path, fontNumber=0, lazy=True)
    full = f['name'].getDebugName(4) or os.path.splitext(os.path.basename(path))[0]
    return '%s (%s)' % (full, 'OpenType' if path.lower().endswith('.otf') else 'TrueType')


def installed(path):
    import winreg
    dst = os.path.join(os.environ['LOCALAPPDATA'], 'Microsoft', 'Windows', 'Fonts', os.path.basename(path))
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG) as k:
            v, _ = winreg.QueryValueEx(k, font_title(path))
        return os.path.exists(dst) and os.path.normcase(v) == os.path.normcase(dst)
    except OSError:
        return False


def install(path):
    import ctypes, winreg
    d = os.path.join(os.environ['LOCALAPPDATA'], 'Microsoft', 'Windows', 'Fonts')
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, os.path.basename(path))
    shutil.copyfile(path, dst)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG) as k:
        winreg.SetValueEx(k, font_title(path), 0, winreg.REG_SZ, dst)
    ctypes.windll.gdi32.AddFontResourceW(dst)
    HWND_BROADCAST, WM_FONTCHANGE, SMTO_ABORTIFHUNG = 0xFFFF, 0x001D, 0x0002
    ctypes.windll.user32.SendMessageTimeoutW(HWND_BROADCAST, WM_FONTCHANGE, 0, 0, SMTO_ABORTIFHUNG, 1000, None)


def main():
    a = sys.argv[1:]
    fonts = os.path.abspath(a[0])
    if '--build-only' in a:
        print('\n'.join(build_serif(os.path.join(fonts, 'NotoSerifSC-wght.ttf'), a[a.index('--build-only') + 1])))
        return 0
    check = '--check' in a
    static = os.path.join(fonts, 'static')
    targets = [os.path.join(static, 'NotoSerifSC-%s.ttf' % w) for w, *_ in SERIF] + \
              [os.path.join(fonts, 'NotoSansCJKsc-%s.otf' % w) for w in SANS]
    if not check:
        build_serif(os.path.join(fonts, 'NotoSerifSC-wght.ttf'), static)
    missing = [t for t in targets if not (os.path.exists(t) and installed(t))]
    if check:
        for t in missing:
            print('未安装：%s' % os.path.basename(t))
        return 1 if missing else 0
    for t in missing:
        install(t)
        print('已安装 %s' % os.path.basename(t), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
