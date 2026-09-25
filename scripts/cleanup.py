# -*- coding: utf-8 -*-
"""Stage 5 · Remove intermediate files that the deliverables no longer need.

Usage: cleanup.py <project> [--dry-run] [--deep]

Kept: outline + whiteboard deck, direction specs and samples, prompts, the selected raw image of every page,
all deliverable PPTX/PDF files, project.json, 04_可编辑 config.json (the human review: exclusions, replacements,
split points), manifest.json and layers.json (records), QA documents and contact sheets. To redo stage 4 after
cleanup, run `deck editable` again from the image deck; config.json is reused.
Removed: tmp folders; unselected raw versions and generation logs; upscaled pages in 03_合成 (embedded in the
image deck); in 04_可编辑 the extracted page images and the plate / debug / preview images (embedded in the
editable deck), per-page comparison images; PowerPoint staging files.
--deep also removes the selected raw images and the direction samples (the image deck still holds every page).
"""
import os, sys, json, glob, shutil, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deckenv as E

def size(p):
    if os.path.isfile(p):
        return os.path.getsize(p)
    return sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(p) for f in fs)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('project'); ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--deep', action='store_true')
    a = ap.parse_args()
    proj = os.path.abspath(a.project)
    doomed = []
    doomed += glob.glob(os.path.join(proj, '**', 'tmp'), recursive=True)
    raw = os.path.join(proj, E.D_GEN, 'raw')
    sel_p = os.path.join(raw, 'selected.json')
    if os.path.exists(sel_p):
        sel = set(json.load(open(sel_p, encoding='utf-8')).values())
        for f in glob.glob(os.path.join(raw, 'p*_v*.png')):
            if os.path.basename(f) not in sel or a.deep:
                doomed.append(f)
    doomed += glob.glob(os.path.join(proj, E.D_COMP, 'p*.png')) + glob.glob(os.path.join(proj, E.D_COMP, 'p*.jpg'))
    ed = os.path.join(proj, E.D_EDIT)
    doomed += [os.path.join(ed, '01_原图')] if os.path.isdir(os.path.join(ed, '01_原图')) else []
    for f in ('plate.jpg', 'debug.jpg', 'preview.jpg', 'ocr.json'):
        doomed += glob.glob(os.path.join(ed, '02_分层', '*', f))
    doomed += glob.glob(os.path.join(ed, '03_QA', 'cmp_*.jpg'))
    if a.deep:
        doomed += glob.glob(os.path.join(proj, E.D_DIRS, '*', 'samples'))
    for d in (E.D_WHITE, E.D_COMP, E.D_EDIT):
        for f in glob.glob(os.path.join(proj, d, '*.pptx')) + glob.glob(os.path.join(proj, d, '*.pdf')):
            top = os.path.join(proj, os.path.basename(f))
            if os.path.exists(top) and os.path.getsize(top) == os.path.getsize(f):
                doomed.append(f)
    import hostos
    stage = hostos.ppt_stage_dir()
    doomed += glob.glob(os.path.join(stage, '*')) if stage else []
    doomed = sorted(set(p for p in doomed if os.path.exists(p)))
    total = sum(size(p) for p in doomed)
    for p in doomed:
        print(('将删除 ' if a.dry_run else '删除 ') + os.path.relpath(p, proj) if p.startswith(proj) else p)
    if not a.dry_run:
        for p in doomed:
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    print('%s %d 项，%.1f MB' % ('可释放' if a.dry_run else '已释放', len(doomed), total / 1048576))

if __name__ == '__main__':
    main()
