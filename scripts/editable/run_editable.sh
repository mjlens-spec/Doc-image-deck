#!/bin/zsh
# Stage 4 · Image deck -> editable deck, first pass (before the human review steps).
# usage: run_editable.sh <workdir> <image_deck.pptx|pdf> <out_editable.pptx> [--outline outline.json] [--draft <copy files...>] [--ref <reference.pdf>]
#   --outline : per-page copy from the whiteboard deck (authoritative text)
#   --draft   : older copy (prompts, md) used only to settle OCR disagreements
#   --ref     : PDF of the image deck, used as the comparison reference (else the page images)
set -e
PY=${PY:-${DOC_IMAGE_DECK_HOME:-$HOME/.local/share/doc-image-deck}/venv/bin/python}
S=${0:A:h}; W=${1:A}; SRC=${2:A}; OUT=${3:A}; shift 3
OUTLINE=""; REF=""; DRAFT=()
while (( $# )); do
  case $1 in
    --outline) OUTLINE=${2:A}; shift 2;;
    --ref) REF=${2:A}; shift 2;;
    --draft) shift; while (( $# )) && [[ $1 != --* ]]; do DRAFT+=${1:A}; shift; done;;
    *) echo "unknown option $1"; exit 1;;
  esac
done
mkdir -p "$W"
[[ -f "$W/manifest.json" ]] || $PY "$S/extract_pages.py" "$SRC" "$W"
if [[ -n $OUTLINE ]]; then $PY "$S/corpus.py" "$W" --outline "$OUTLINE"
elif (( ${#DRAFT} )); then $PY "$S/corpus.py" "$W" ${DRAFT[@]}; fi
[[ -f "$W/config.json" ]] || echo '{"pages": {}, "replace": {}}' > "$W/config.json"
PY=$PY "$S/run_pages.sh" "$W"
$PY "$S/build_pptx.py" "$W" "$OUT"
if [[ -n $REF ]]; then $PY "$S/verify.py" "$W" "$OUT" "${OUT%.pptx}.pdf" --ref "$REF"
else $PY "$S/verify.py" "$W" "$OUT" "${OUT%.pptx}.pdf"; fi
$PY "$S/proof_sheet.py" "$W" "$W/03_QA/校对表" | head -1
$PY "$S/qa_sheet.py" "$W" "${OUT%.pptx}.pdf" "$W/03_QA/全稿对照" 8 | tail -1
