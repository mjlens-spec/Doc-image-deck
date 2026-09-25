---
name: doc-image-deck
description: 文图方案（Doc-image-deck）：从文档做出一套「整页生图」风格的演示稿，并最终交付可编辑 PowerPoint 的完整流程。文档 → 结构化白板稿 PPTX（含标点整理）→ 用户确认白板稿 → 查找本地视觉参考并询问用户 → 3 个完全不同的设计方向样张供用户选择 → 用 ChatGPT / Codex 内置生图逐页生成整页图片 → 加 Logo 与页码合成图文版 PPTX 和 PDF → 高保真还原为文字与排版都可编辑的 PPTX 和 PDF → 清理中间文件。用户说「文图方案」「Doc-image-deck」「把这份文档做成生图 PPT」「用 GPT 生图出一套提案」「先出白板稿再生图」「出三个设计方向」「图文版 PPT」「把图片版 / 生图版 PPT 转回可编辑」「整页图片的 PPT 还原成可编辑」时使用；已有白板稿、已有生图页面、已有整页图片 PPTX 或 PDF 时，从对应阶段进入。只要求普通可编辑 PPT、不走生图路线时不使用。
---

# 文图方案（Doc-image-deck）

脚本入口：`$S/deck`（`$S` = 本 skill 的 `scripts/` 目录，Claude Code 下为 `~/.claude/skills/doc-image-deck/scripts`，Codex 下为 `~/.codex/skills/doc-image-deck/scripts`，两者指向同一份文件）。`$S/deck help` 列出全部命令。

| 阶段 | 产出 | 停下来等用户 |
|---|---|---|
| 1 白板稿 | `outline.json` + 白板稿 PPTX：终稿文字、结构、每页版面与配图建议，不做设计；标点整理 | **确认点 1**：确认白板稿，同时询问视觉参考 |
| 2 设计方向与生图 | 3 个完全不同的设计方向样张 → 用户选定 → 全量逐页整页图片，逐页核对文字 | **确认点 2**：选方向 |
| 3 合成 | 图文版 PPTX + PDF（整页图 + 独立的 Logo 与页码对象） | — |
| 4 可编辑还原 | 可编辑版 PPTX + PDF（去字底图 + 可编辑文本框） | 仅页面含截图、海报时审阅排除区 |
| 5 交付清理 | 删除中间文件，写交付检查 | — |

入口判断：从文档出发走 1–5；用户给的是已定稿的大纲或白板稿，先转成 `outline.json`，生成白板稿后仍走确认点 1；已有逐页生图，从 3 开始；已有整页图片 PPTX 或 PDF（包括别人做的生图稿），只走 4、5，流程见 `references/04_可编辑还原.md`。

## 开始前

1. 运行 `$S/deck check`。有 ✗ 项时运行 `$S/setup.sh` 补齐（首次约 10 分钟，下载 Python 依赖约 1 GB、LaMa 权重 196 MB、缺失的思源字体），细节见 `references/06_环境与安装.md`。依赖 macOS、Microsoft PowerPoint for Mac、Codex CLI（用 ChatGPT 账号登录）。
2. 建项目目录，放在用户的交付目录下，命名遵循宿主的文件命名规则（例：`<项目名>_AC_0925A/`）。在里面写 `project.json`：

```json
{
  "name": "秋季新品上市整合营销方案",
  "suffix": "AC_0925A",
  "source": "../秋季新品上市方案.docx",
  "audience": "Chinese business proposal for a tea-drink brand",
  "brands": ["品牌名", "代理公司名"],
  "logos": [{"light": "<浅底用 logo.png>", "dark": "<深底用 logo.png>", "corner": "bl", "height_in": 0.26}],
  "page_number": {"corner": "br", "skip_first": true, "skip_last": true, "format": "{:02d}"},
  "parallel": 4
}
```

`suffix` 用于所有交付文件名（`<name>_白板稿_<suffix>.pptx`、`_图文版_`、`_可编辑版_`）；在 Codex 中按用户在 Codex 的命名习惯（如 `OC_0925A`）。`source` 是原文档的相对路径，查找视觉参考时会一并搜索它所在的目录。Logo 不清楚用哪个、放哪个角时，放到确认点 1 一起问；`brands` 里的品牌会写进提示词的禁画清单，避免生图自己画 Logo。

## 阶段 1 · 白板稿

1. 通读文档，按 `references/01_白板稿.md` 的结构写 `00_白板稿/outline.json`：每页一个结论式标题、终稿正文、`layout_hint`（版面建议）、`image_hint`（配图建议）、`tone`（明暗）、讲稿。文字按宿主的写作规范成稿，达到可以直接对客户使用的程度；生图阶段逐字照搬这里的文字，之后很难再改。
2. 控制每页字量：正文不超过约 150 个汉字，表格不超过 6 行 × 5 列。生图模型字越多错字越多，超出时拆页。
3. `$S/deck whiteboard <项目>`：先做**标点整理**（标题和短句去掉句号，只有详细描述和成段文字保留句号，规则见 `references/01_白板稿.md`），再生成白板稿 PPTX 和 `outline.md`。改动记在 `00_白板稿/标点整理.md`；其中列出的「列表内句号不统一」要看一下，按需改写后重跑。打开 PPTX 检查有没有溢出、漏页。
4. `$S/deck refs <项目>`：在项目目录、上级目录和原文档所在目录里查找可用作视觉参考的图片、PDF、PPT（情绪板、品牌手册、往期提案、主视觉、海报），生成 `01_设计方向/参考候选/候选清单.md` 和 `候选对照.jpg`。
5. **确认点 1（必须停下）**：在一条消息里给用户：
   - 白板稿 PPTX 的路径、页数和逐页标题；标点整理改了几处。
   - 视觉参考：本地找到的候选（附 `候选对照.jpg`，按 R01、R02 编号），并问用户是否有想用的视觉参考，可以指定编号，也可以另外提供图片、PDF 或 PPT。说明规则：用户给一个参考，它成为三个方向之一，另外两个方向由你设计；不给参考，三个方向都由你设计。
   - 其他缺的信息（Logo 文件与位置等）一并问。

   然后结束本轮，等用户回复，不要继续做设计方向或生图。
6. 用户要求改白板稿时，改 `outline.json` 并重跑 `deck whiteboard`；改动大时把新版再给用户看一次。用户确认后运行 `$S/deck approve <项目> --note "<用户意见摘要>"`。`deck prompts` 在确认记录缺失、或确认后白板稿文字又被改过时会拒绝运行；之后任何改字都要让用户知道，并重新 `deck approve`。

## 阶段 2 · 设计方向与全量生图

生图走 Codex 内置 `image_gen`（ChatGPT 套餐额度，不走 API），每页一次调用，约 1–2 分钟，输出 1672 × 941；4 路并发稳定，4 页约 80 秒。方向写法、提示词结构、已知问题见 `references/02_设计方向与生图.md`。

1. **定三个方向的来源**：
   - 用户给了 1 个参考（或几份风格相同的参考）：A 按参考建立，B、C 由你设计。
   - 用户给了 2 个风格不同的参考：A、B 按参考建立，C 由你设计。
   - 给了 3 个以上：按用户的优先顺序取 3 个风格最不同的；没有给：A、B、C 都由你设计。

   参考先导出为图片：`$S/deck refs <项目> --export R03 --pages 1,4 --to 01_设计方向/A/ref`（用户另给的文件把 `R03` 换成文件路径）。看过参考图后再写方向：从参考里提炼配色（写出色值）、字体、版式语法、配图处理和质感；只取风格，不照搬参考里的文字、Logo 和品牌资产。
2. **写 3 个方向**：`01_设计方向/A|B|C/direction.json`。三个方向要**完全不同**：`dims` 的字体、配色、版式语法、配图、质感五项两两都不一样，`imagery_mode`（写实摄影、产品静物、插画、纯图形、材质肌理、三维渲染、纯文字排版）三个方向各用一种；同时都要贴合内容和客户行业。按参考建立的方向写 `"source": "reference"` 和 `"refs"`，自行设计的写 `"source": "original"`。
3. `$S/deck directions <项目>` 检查三个方向，不通过就改到通过，同时生成 `01_设计方向/方向说明.md`（给用户看的对比表）。
4. **出样张**：每个方向选 2 页，封面 + 本稿信息最密的一页内容页：
   `$S/deck prompts <项目> --direction 01_设计方向/A/direction.json --out 01_设计方向/A/prompts --pages p01,p07`
   `$S/deck gen 01_设计方向/A/prompts --out 01_设计方向/A/samples`（B、C 同样，可同时后台运行；按参考建立的方向会自动附上参考图）
   `$S/deck sheet 01_设计方向/方向对比.jpg "A 封面=01_设计方向/A/samples/p01_v1.png" "A 内容=…" …`（每行一个方向）
5. **确认点 2（必须停下）**：把方向对比图和 `方向说明.md` 给用户，请用户选定方向（也可以指定混合调整，如「A 的版式 + C 的配色」，按要求改写方向后重出样张）。结束本轮等用户回复。
6. **全量生图**：
   `$S/deck prompts <项目> --direction 01_设计方向/<选定>/direction.json --out 02_生图/prompts`
   `$S/deck gen 02_生图/prompts --out 02_生图/raw --ref-light <选定方向的内容样张> --ref-dark <选定方向的封面样张>`
   样张作为风格参考图附上，保证全稿风格一致；选定方向来自用户参考时，参考图也会附上（每次最多 3 张）。页数多时后台运行，每 10 页约 3–5 分钟。
7. **核对与重生成**：`$S/deck textcheck <项目> 02_生图/prompts 02_生图/raw`。`MISS`（缺字、错字）和 `CORNER`（预留角落里有字）的页用 `--pages` 重新生成，最多两轮；两轮仍不过，改写该页版面建议后再生成；需要删改文字时先告诉用户，确认后 `deck approve` 再生成。`NEAR` 多为 OCR 误差，看图确认。
8. 生成全稿联系表 `$S/deck sheet 02_生图/联系表 --raw 02_生图/raw --cols 3`，逐张检查：配图题材不重复、同级标题大小一致、没有乱码和多余文字。有问题的页重生成，并在 `02_生图/raw/selected.json` 里指定采用的版本。

## 阶段 3 · 合成图文版

`$S/deck compose <项目>`：选定的生图放大 2 倍，每页一张满幅图，Logo 与页码作为独立对象叠加（按所在角落明暗自动选浅底 / 深底 Logo；页码落在照片上时加半透明底块；封面、封底默认不加页码），讲稿写入备注，并用 PowerPoint 导出 PDF。抽查 3–5 页 Logo 和页码有没有压到内容，压到了就回阶段 2 重生成该页，或调整 `project.json` 里的角落和尺寸。

## 阶段 4 · 可编辑还原

```
$S/deck editable <项目>/04_可编辑 03_合成/<name>_图文版_<suffix>.pptx 04_可编辑/<name>_可编辑版_<suffix>.pptx \
    --outline 00_白板稿/outline.json --ref 03_合成/<name>_图文版_<suffix>.pdf
```

一次完成抽页、识别、字体拟合、LaMa 去字、装配、PowerPoint 导出和比对。以白板稿文字为准校正识别结果，所以本流程自己生成的稿件几乎不需要人工校字。之后：

1. 看 `04_可编辑/03_QA/全稿对照_*.jpg`。页面里有截图、海报、图表、表情包时，用 `$S/deck review` 读出坐标，写进 `04_可编辑/config.json` 的排除区，重跑这些页（`$S/deck layers <工作目录> p05 p09`，再 `deck build`、`deck verify`）。
2. 看 `校对表_*.png`；有残留错字写进 `config.json` 的 `replace`。
3. 规则、参数和排查方法见 `references/04_可编辑还原.md` 与 `references/04b_还原技术细节.md`。

## 阶段 5 · 交付与清理

1. 把白板稿、图文版、可编辑版的 PPTX 和 PDF 放到项目根目录。
2. 按 `references/05_交付与清理.md` 写 `05_QA/交付检查_<suffix>.md`：页数、字体、比对数值、文字处理说明、留在底图的内容、已知差异。
3. `$S/deck cleanup <项目> --dry-run` 列出将删除的文件和可释放空间，然后 `$S/deck cleanup <项目>` 执行。默认保留大纲、方向与参考图、提示词、每页选定的生图原稿、`04_可编辑/config.json` 和全部交付文件，足够日后重新合成或重新还原；用户要求彻底清理时加 `--deep`。

## 在 Codex（ChatGPT）中运行

整套流程在 Codex 中同样可用，命令完全一致：`deck gen` 本身就是调用 Codex 的内置生图。区别有四处：

- 两个确认点同样要停：给出内容和问题后结束本轮，等用户回复再继续。
- 权限：`deck gen` 会再起一个 `codex exec`（需要联网）；`deck compose`、`deck editable`、`deck pdf` 和导出 PPTX 参考的 `deck refs --export` 会通过 AppleScript 驱动 PowerPoint。Codex 默认沙盒不允许这两类操作，运行这几条命令时按提示批准提权，或以完全访问模式启动会话；`deck whiteboard`、`deck refs`（查找）、`deck approve`、`deck directions`、`deck prompts`、`deck check` 在默认沙盒里就能运行。
- 单页返修可以直接调用内置 `image_gen` 工具生成，再把图片复制到 `02_生图/raw/pNN_vK.png` 并更新 `selected.json`。
- 整个会话使用 Codex 配置中最强的模型和高推理强度（如 `model_reasoning_effort = "high"`）；批量生图的子调用固定用低推理强度，因为提示词原样传给生图工具，不需要模型改写。

## 容易出错的地方

- 不要跳过确认点 1：白板稿文字会逐字进入每一页生图，生图后再改字要重新生成对应页。
- 三个方向容易只在配色上有差别、配图都是同一类题材；`deck directions` 会拦下五项维度或配图方式重复的方向。
- 生图模型不严格遵守「角落留空」，交给 `textcheck` 的 `CORNER` 检查兜底，不要跳过。
- 同一套稿的配图题材容易撞车（机房、光纤、芯片反复出现）；写 `image_hint` 时就逐页区分，联系表阶段再核对一遍。
- PowerPoint for Mac 受沙盒限制，脚本会把文件复制到它的容器目录再导出；不要改成直接打开桌面上新建目录里的文件。
- 可编辑还原阶段最多开 2 个进程（LaMa 在 16 GB 内存上的上限），`deck layers` 已按此设置。
