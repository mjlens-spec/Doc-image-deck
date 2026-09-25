# -*- coding: utf-8 -*-
"""Export a PPTX to PDF with Microsoft PowerPoint (the renderer the deck is meant for).

macOS: PowerPoint is sandboxed and can always read/write its own container, so files are staged there and the
export is driven with AppleScript.
Windows: PowerPoint is driven through COM (pywin32). A PowerPoint window the user has open is left alone; the
application is closed afterwards only when it has no other presentation open.
"""
import os, sys, shutil, subprocess, time, uuid
sys.path.insert(1, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hostos


def _mac(pptx, pdf, timeout):
    stage = hostos.ppt_stage_dir()
    os.makedirs(stage, exist_ok=True)
    tag = uuid.uuid4().hex[:8]
    sp, so = os.path.join(stage, tag + '.pptx'), os.path.join(stage, tag + '.pdf')
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


def _win(pptx, pdf, timeout):
    try:
        import pythoncom
        import win32com.client
    except ImportError:
        raise RuntimeError('缺少 pywin32：运行 deck setup')
    pythoncom.CoInitialize()
    app = pres = None
    try:
        app = win32com.client.DispatchEx('PowerPoint.Application')
        # Open(FileName, ReadOnly, Untitled, WithWindow): read-only, keep the file name, no window
        pres = app.Presentations.Open(os.path.abspath(pptx), True, False, False)
        try:
            # ppFixedFormatTypePDF = 2, ppFixedFormatIntentPrint = 2 (full-resolution pictures)
            pres.ExportAsFixedFormat(os.path.abspath(pdf), 2, 2)
        except Exception:
            pres.SaveAs(os.path.abspath(pdf), 32)          # ppSaveAsPDF
        pres.Close(); pres = None
        if not os.path.exists(pdf):
            raise RuntimeError('PowerPoint 没有写出 %s' % pdf)
        return pdf
    finally:
        try:
            if pres is not None:
                pres.Close()
            if app is not None and app.Presentations.Count == 0:
                app.Quit()
        except Exception:
            pass
        pythoncom.CoUninitialize()


def ppt_to_pdf(pptx, pdf, timeout=1800):
    pptx, pdf = os.path.abspath(pptx), os.path.abspath(pdf)
    if hostos.IS_WIN:
        return _win(pptx, pdf, timeout)
    if hostos.IS_MAC:
        return _mac(pptx, pdf, timeout)
    raise RuntimeError('导出 PDF 需要 Microsoft PowerPoint（macOS 或 Windows）')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit('usage: pptrender.py <deck.pptx> [out.pdf]')
    src = os.path.abspath(sys.argv[1])
    print(ppt_to_pdf(src, os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else src[:-5] + '.pdf'))
