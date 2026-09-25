#!/bin/zsh
# Install / repair the machine-level runtime of Doc-image-deck（文图方案）(macOS only).
#   setup.sh             install everything that is missing
#   setup.sh --check     report only, change nothing
#   setup.sh --no-fonts  do not download missing fonts
#   setup.sh --no-calib  skip the PowerPoint calibration
# Runtime: $DOC_IMAGE_DECK_HOME (default ~/.local/share/doc-image-deck): venv/, bin/ocrbox, calibration.json
S=${0:A:h}
RUNTIME=${DOC_IMAGE_DECK_HOME:-$HOME/.local/share/doc-image-deck}
CHECK=0; FONTS=1; CALIB=1
for a in "$@"; do case $a in --check) CHECK=1;; --no-fonts) FONTS=0;; --no-calib) CALIB=0;; esac; done
ok()   { print -P "%F{green}✓%f $1"; }
warn() { print -P "%F{yellow}!%f $1"; }
bad()  { print -P "%F{red}✗%f $1"; MISSING=1; }
MISSING=0

[[ $(uname) == Darwin ]] || { bad "需要 macOS（OCR 用 Apple Vision，导出与标定用 PowerPoint for Mac）"; exit 1; }

# 1. Python 3.10+
PYSYS=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v $c >/dev/null && $c -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then PYSYS=$(command -v $c); break; fi
done
[[ -n $PYSYS ]] && ok "Python: $PYSYS" || bad "未找到 Python 3.10+（可用 brew install python）"

# 1b. poppler (pdftoppm / pdfinfo / pdfimages)
if command -v pdftoppm >/dev/null && command -v pdfimages >/dev/null; then ok "poppler：$(command -v pdftoppm)"
elif (( CHECK )); then bad "缺 poppler（pdftoppm 等）"
elif command -v brew >/dev/null; then brew install poppler >/dev/null && ok "poppler 已安装" || bad "poppler 安装失败"
else bad "缺 poppler：先安装 Homebrew，再 brew install poppler"; fi

# 2. venv + packages
PY=$RUNTIME/venv/bin/python
if [[ -x $PY ]] && $PY -c 'import numpy, scipy, cv2, PIL, pptx, lxml, torch, simple_lama_inpainting' 2>/dev/null; then
  ok "Python 环境：$RUNTIME/venv"
elif (( CHECK )); then bad "Python 环境未就绪：$RUNTIME/venv"
elif [[ -n $PYSYS ]]; then
  echo "安装 Python 环境到 $RUNTIME/venv（含 torch，约 1 GB）…"
  mkdir -p $RUNTIME && $PYSYS -m venv $RUNTIME/venv && \
  $PY -m pip install -q --upgrade pip && \
  $PY -m pip install -q numpy scipy opencv-python-headless pillow python-pptx lxml torch fonttools && \
  $PY -m pip install -q --no-deps simple-lama-inpainting && ok "Python 环境已安装" || bad "Python 依赖安装失败"
fi

# 3. LaMa weights
LAMA=$HOME/.cache/torch/hub/checkpoints/big-lama.pt
if [[ -s $LAMA ]] && (( $(stat -f%z $LAMA) > 150000000 )); then ok "LaMa 权重：$LAMA"
elif (( CHECK )); then bad "缺 LaMa 权重：$LAMA"
else
  echo "下载 LaMa 权重（约 196 MB，可断点续传）…"
  mkdir -p ${LAMA:h}
  curl -L --retry 5 -C - -o $LAMA "https://github.com/enesmsahin/simple-lama-inpainting/releases/download/v0.1.0/big-lama.pt" && ok "LaMa 权重已下载" || bad "LaMa 权重下载失败，可重跑本脚本续传"
fi

# 4. Fonts: 思源宋体 (variable) + 思源黑体 (static weights)
FD=$HOME/Library/Fonts
typeset -A FURL
FURL[NotoSerifSC-wght.ttf]="https://github.com/google/fonts/raw/main/ofl/notoserifsc/NotoSerifSC%5Bwght%5D.ttf"
for w in Light DemiLight Regular Medium Bold Black; do
  FURL[NotoSansCJKsc-$w.otf]="https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-$w.otf"
done
FMISS=0
for f in ${(k)FURL}; do
  if [[ -f $FD/$f || -f /Library/Fonts/$f ]]; then continue; fi
  if (( CHECK || !FONTS )); then bad "缺字体：$f"; FMISS=1; continue; fi
  echo "下载字体 $f …"; curl -fL --retry 3 -s -o $FD/$f "${FURL[$f]}" && ok "字体已安装：$f" || { bad "字体下载失败：$f"; FMISS=1; }
done
(( FMISS )) || ok "字体：思源宋体 Noto Serif SC、思源黑体 Noto Sans CJK SC"
[[ -f $FD/msyh.ttc || -f /Library/Fonts/msyh.ttc ]] || warn "未装微软雅黑：白板稿仍用微软雅黑排版，本机显示会被替换"

# 5. OCR tool (Apple Vision)
OCR=$RUNTIME/bin/ocrbox
if [[ -x $OCR && $OCR -nt $S/editable/ocrbox.swift ]]; then ok "OCR 工具：$OCR"
elif (( CHECK )); then bad "OCR 工具未编译：$OCR"
elif command -v swiftc >/dev/null; then
  mkdir -p $RUNTIME/bin && swiftc -O $S/editable/ocrbox.swift -o $OCR 2>/dev/null && ok "OCR 工具已编译" || bad "OCR 工具编译失败"
else bad "缺 swiftc：运行 xcode-select --install 安装命令行工具"; fi

# 6. Codex CLI (image generation through the ChatGPT plan)
if command -v codex >/dev/null; then
  if codex login status 2>&1 | grep -q ChatGPT; then ok "Codex CLI：$(codex --version 2>/dev/null)，已用 ChatGPT 账号登录"
  else bad "Codex CLI 未用 ChatGPT 账号登录：运行 codex login"; fi
else bad "缺 Codex CLI（生图用）：npm i -g @openai/codex 或 brew install codex，然后 codex login"; fi

# 7. PowerPoint + calibration
if [[ -d "/Applications/Microsoft PowerPoint.app" ]]; then
  PPV=$(defaults read '/Applications/Microsoft PowerPoint.app/Contents/Info.plist' CFBundleShortVersionString 2>/dev/null)
  ok "PowerPoint${PPV:+：$PPV}"
  if grep -q baseline_table $RUNTIME/calibration.json 2>/dev/null; then ok "PowerPoint 标定：$RUNTIME/calibration.json"
  elif (( CHECK || !CALIB )); then bad "未做 PowerPoint 标定"
  elif [[ -x $PY ]]; then
    echo "标定 PowerPoint 文字排版（会打开 PowerPoint 约 1 分钟）…"
    $PY $S/editable/calibrate.py $RUNTIME >/dev/null && $PY $S/editable/calibrate_table.py $RUNTIME && ok "标定完成" || bad "标定失败"
    rm -rf $RUNTIME/tmp
  fi
else bad "缺 Microsoft PowerPoint for Mac（用于导出 PDF、标定和比对）"; fi

(( MISSING )) && { echo "\n环境不完整，按上面提示处理后重跑：$S/setup.sh"; exit 2; } || echo "\n环境就绪。"
