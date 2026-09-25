#!/bin/zsh
# Run layers.py over pages with 2 parallel workers (LaMa on Apple GPU: more than 2 exhausts 16 GB of memory).
# usage: run_pages.sh <workdir> [pid ...]      (no pids = every page in manifest.json)
# env:   PY = python of the venv (default $DOC_IMAGE_DECK_HOME/venv/bin/python)
PY=${PY:-${DOC_IMAGE_DECK_HOME:-$HOME/.local/share/doc-image-deck}/venv/bin/python}
S=${0:A:h}; W=${1:A}; shift
if (( $# )); then P=("$@"); else P=($($PY -c "import json,sys;print(' '.join(p['pid'] for p in json.load(open(sys.argv[1]))['pages']))" "$W/manifest.json")); fi
mkdir -p "$W/tmp"
A=(); B=(); k=0
for p in $P; do if (( k % 2 )); then B+=$p; else A+=$p; fi; k=$((k+1)); done
(( ${#A} )) && $PY "$S/layers.py" "$W" ${A[@]} > "$W/tmp/run_a.log" 2>&1 &
(( ${#B} )) && $PY "$S/layers.py" "$W" ${B[@]} > "$W/tmp/run_b.log" 2>&1 &
wait
grep -h "^p" "$W"/tmp/run_[ab].log | sort
grep -hiE "traceback|error" -A4 "$W"/tmp/run_[ab].log | grep -vi warn | head -20
