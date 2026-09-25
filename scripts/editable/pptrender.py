# -*- coding: utf-8 -*-
"""Export a PPTX to PDF with Microsoft PowerPoint (the renderer the deck is meant for).

PowerPoint for Mac is sandboxed: it can always read/write its own container, so files are staged
there instead of asking for folder access.
"""
import os, shutil, subprocess, time, uuid
STAGE = os.path.expanduser('~/Library/Containers/com.microsoft.Powerpoint/Data/tmp/deckrender')

def ppt_to_pdf(pptx, pdf, timeout=1800):
    os.makedirs(STAGE, exist_ok=True)
    tag = uuid.uuid4().hex[:8]
    sp, so = os.path.join(STAGE, tag + '.pptx'), os.path.join(STAGE, tag + '.pdf')
    shutil.copy(pptx, sp)
    script = '''
set inF to POSIX file "%s"
tell application "Microsoft PowerPoint"
  with timeout of %d seconds
    open inF
    delay 2
    set pres to active presentation
    save pres in POSIX file "%s" as save as PDF
    delay 1
    close pres saving no
  end timeout
end tell
return "ok"''' % (sp, timeout, so)
    r = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=timeout + 60)
    if r.returncode != 0 or not os.path.exists(so):
        raise RuntimeError('PowerPoint export failed: ' + r.stderr.strip())
    shutil.move(so, pdf)
    os.remove(sp)
    return pdf

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        raise SystemExit('usage: pptrender.py <deck.pptx> [out.pdf]')
    src = os.path.abspath(sys.argv[1])
    print(ppt_to_pdf(src, os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else src[:-5] + '.pdf'))
