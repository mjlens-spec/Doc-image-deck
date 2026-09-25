# -*- coding: utf-8 -*-
"""Confirmation point 1 · Record that the user approved the whiteboard deck.

Usage: approve.py <project> [--note "用户意见摘要"]      record the approval (after the user said yes)
       approve.py <project> --status                    show whether the current text is approved

Stage 2 (design directions, prompts, image generation) starts only after this: build_prompts.py refuses to run
until project.json holds an approval whose text signature matches outline.json. Any later change to the printed
text needs a new confirmation from the user and a new `deck approve`.
Refuses when the whiteboard deck is older than outline.json (not re-rendered after an edit) or when titles and
short phrases still end with a full stop.
"""
import os, sys, argparse, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deckenv as E
import punct


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project'); ap.add_argument('--note', default=''); ap.add_argument('--status', action='store_true')
    a = ap.parse_args()
    proj = os.path.abspath(a.project)
    outline = E.load_outline(proj)
    if a.status:
        ok, msg = E.whiteboard_approval(proj, outline)
        print(msg)
        sys.exit(0 if ok else 1)
    cfg = E.load_project(proj)
    src = os.path.join(proj, E.D_WHITE, 'outline.json')
    deck = os.path.join(proj, E.D_WHITE, E.out_name(cfg, '白板稿', 'pptx'))
    if not os.path.exists(deck) or os.path.getmtime(deck) < os.path.getmtime(src):
        raise SystemExit('白板稿 PPTX 不存在或早于 outline.json：先运行 deck whiteboard，把新版发给用户确认后再运行本命令。')
    _, leftovers, _ = punct.run(proj, check=True)
    if leftovers:
        raise SystemExit('还有 %d 处标题或短句以句号结尾：先运行 deck punct（会重新生成白板稿），再把新版发给用户确认。' % len(leftovers))
    stamp = datetime.datetime.now().isoformat(timespec='seconds')
    approval = dict(cfg.get('approval') or {})
    approval['whiteboard'] = dict(signature=E.text_signature(outline), time=stamp, pages=len(outline['pages']),
                                  deck=os.path.basename(deck), note=a.note)
    E.update_project(proj, approval=approval)
    print('已记录白板稿确认：%d 页，%s。可以开始阶段 2（视觉参考与设计方向）。' % (len(outline['pages']), stamp))


if __name__ == '__main__':
    main()
