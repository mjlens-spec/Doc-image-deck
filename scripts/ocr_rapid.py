# -*- coding: utf-8 -*-
"""OCR with RapidOCR (PaddleOCR PP-OCRv6 models on ONNX Runtime): the Windows counterpart of editable/ocrbox.swift
(Apple Vision), with the same command line and the same JSON.

Usage: ocr_rapid.py <image>                              -> JSON array of lines
       ocr_rapid.py --batch <list.txt> [--words f] [--lc]  -> JSON object {path: [lines]}   (--words / --lc: ignored)
Each line: text, conf, x0 y0 x1 y1 (pixels, origin top-left), chars (one box per character, [] for a space), alts ([]).
DOC_IMAGE_DECK_OCR_MODEL=small (default, shipped inside the rapidocr wheel) | medium (downloaded once from ModelScope).
"""
import os, sys, json


def engine():
    import logging
    from rapidocr import RapidOCR, ModelType
    size = ModelType(os.environ.get('DOC_IMAGE_DECK_OCR_MODEL', 'small'))
    params = {'Global.log_level': 'error', 'Global.use_cls': False,
              'Det.model_type': size, 'Rec.model_type': size}
    eng = RapidOCR(params=params)
    logging.getLogger('RapidOCR').setLevel(logging.ERROR)
    return eng


def char_boxes(text, words):
    """One box per character of text, taken in order from the single-character results; [] for spaces."""
    out, k = [], 0
    flat = [w for w in words if w and w[0]]
    for c in text:
        if c.isspace():
            out.append([]); continue
        box = []
        for j in range(k, min(k + 3, len(flat))):          # tolerate a skipped glyph without losing the alignment
            if flat[j][0] == c:
                box = flat[j][2]; k = j + 1; break
        else:
            if k < len(flat):
                box = flat[k][2]; k += 1
        if box:
            xs, ys = [p[0] for p in box], [p[1] for p in box]
            out.append([float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))])
        else:
            out.append([])
    return out


def run(eng, path):
    try:
        r = eng(path, return_word_box=True, return_single_char_box=True)
    except Exception as e:
        print('ocr_rapid: %s: %s' % (path, e), file=sys.stderr)
        return []
    if r is None or r.txts is None:
        return []
    words = r.word_results or [()] * len(r.txts)
    lines = []
    for box, txt, sc, wr in zip(r.boxes, r.txts, r.scores, words):
        xs, ys = [float(p[0]) for p in box], [float(p[1]) for p in box]
        lines.append(dict(text=txt, conf=float(sc), x0=min(xs), y0=min(ys), x1=max(xs), y1=max(ys),
                          chars=char_boxes(txt, list(wr or [])), alts=[]))
    lines.sort(key=lambda L: (round(L['y0'] / 8), L['x0']))
    return lines


def main():
    args = sys.argv[1:]
    if not args:
        raise SystemExit(__doc__)
    eng = engine()
    if args[0] == '--batch':
        paths = [p.strip() for p in open(args[1], encoding='utf-8').read().splitlines() if p.strip()]
        res = {p: run(eng, p) for p in paths}
        sys.stdout.write(json.dumps(res, ensure_ascii=False))
    else:
        sys.stdout.write(json.dumps(run(eng, args[0]), ensure_ascii=False))


if __name__ == '__main__':
    main()
