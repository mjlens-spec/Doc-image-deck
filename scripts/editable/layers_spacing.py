# -*- coding: utf-8 -*-
"""Per-character spacing model shared by layers.py (fitting) and build_pptx.py (PowerPoint runs)."""
CLOSE_PUNCT = set('，。、：；！？」』）》〉】”’')
OPEN_PUNCT = set('「『（《〈【“‘')

def punct_slots(text):
    n = len(text)
    return [i for i in range(n - 1) if text[i] in CLOSE_PUNCT or text[i + 1] in OPEN_PUNCT]

def track_list(text, track, extra, pq=0.0):
    """Spacing after each character (PowerPoint spc): base tracking, + extra after spaces,
    + pq (negative) at compressed full-width punctuation gaps."""
    slots = set(punct_slots(text)) if pq else ()
    return [track + (extra if c == ' ' else 0.0) + (pq if i in slots else 0.0) for i, c in enumerate(text)]


def char_layout(l):
    """Per-character (spacing after, size factor) for a fitted line, including a smaller trailing unit
    ('%' set a size down after big figures): l['tail'] = {'n': chars, 'scale': size factor, 'gap': spacing
    after the last full-size character}."""
    text = l['text']
    sp = track_list(text, l['track_px'], l.get('space_extra_px', 0.0), l.get('punct_extra_px', 0.0))
    fac = [1.0] * len(text)
    t = l.get('tail')
    if t and 0 < t['n'] < len(text):
        k = len(text) - t['n']
        for i in range(k, len(text)):
            fac[i] = t['scale']; sp[i] = l['track_px'] * t['scale']
        sp[k - 1] = t['gap']
    return sp, fac
