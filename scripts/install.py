# -*- coding: utf-8 -*-
"""Install Doc-image-deck（文图方案）for Claude Code and Codex, then set up the runtime.

    macOS:   python3 scripts/install.py [--no-setup]
    Windows: py -3 scripts\\install.py [--no-setup]
The skill files (SKILL.md, LICENSE, agents, references, scripts) are copied to ~/.agents/skills/doc-image-deck;
~/.claude/skills and ~/.codex/skills get a link to it (symlink on macOS, directory junction on Windows, which needs
no admin rights), so both hosts read the same copy. Rerun after editing the repository.
"""
import os, sys, shutil, subprocess, time

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = 'doc-image-deck'
HOME = os.path.expanduser('~')
DEST = os.path.join(HOME, '.agents', 'skills', NAME)
PARTS = ['SKILL.md', 'LICENSE', 'agents', 'references', 'scripts']
IGNORE = shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store')


def is_link(p):
    if os.path.islink(p):
        return True
    return os.name == 'nt' and os.path.isdir(p) and os.path.realpath(p) != os.path.abspath(p)   # junction


def remove_link(p):
    if os.name == 'nt' and os.path.isdir(p) and not os.path.islink(p):
        os.rmdir(p)                      # removes the junction, not the target
    else:
        os.unlink(p)


def main():
    os.makedirs(DEST, exist_ok=True)
    for name in os.listdir(DEST):        # mirror: drop what the repository no longer has
        if name not in PARTS:
            p = os.path.join(DEST, name)
            shutil.rmtree(p) if os.path.isdir(p) and not os.path.islink(p) else os.remove(p)
    for part in PARTS:
        s, d = os.path.join(SRC, part), os.path.join(DEST, part)
        if os.path.isdir(d):
            shutil.rmtree(d)
        if os.path.isdir(s):
            shutil.copytree(s, d, ignore=IGNORE)
        else:
            shutil.copy2(s, d)
    if os.name != 'nt':
        for f in ('deck',):
            os.chmod(os.path.join(DEST, 'scripts', f), 0o755)
    for host in (os.path.join(HOME, '.claude', 'skills'), os.path.join(HOME, '.codex', 'skills')):
        os.makedirs(host, exist_ok=True)
        link = os.path.join(host, NAME)
        if os.path.lexists(link):
            if is_link(link):
                remove_link(link)
            else:
                os.rename(link, '%s.bak.%d' % (link, int(time.time())))
        if os.name == 'nt':
            subprocess.run(['cmd', '/c', 'mklink', '/J', link, DEST], check=True, capture_output=True)
        else:
            os.symlink(os.path.relpath(DEST, host), link)
        print('已链接：%s -> %s' % (link, DEST))
    if '--no-setup' not in sys.argv:
        sys.exit(subprocess.run([sys.executable, os.path.join(DEST, 'scripts', 'setup.py')]).returncode)


if __name__ == '__main__':
    main()
