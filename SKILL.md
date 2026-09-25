---
name: doc-image-deck
description: 文图方案（Doc-image-deck）：从文档做出一套「整页生图」风格的演示稿，并最终交付可编辑 PowerPoint 的完整流程。文档 → 大纲文案 → 用 humanizer-zh 去 AI 味 → 结构化白板稿 PPTX（含标点整理）→ 用户确认白板稿 → 查找本地视觉参考并询问用户 → 品牌 VI 与 Logo 快速调研、阅读客户视觉材料 → 3 个完全不同的设计方向样张供用户选择 → 用 ChatGPT / Codex 内置生图逐页生成整页图片 → 加 Logo 与页码合成图文版 PPTX 和 PDF → 高保真还原为文字与排版都可编辑的 PPTX 和 PDF → 清理中间文件。用户说「文图方案」「Doc-image-deck」「把这份文档做成生图 PPT」「用 GPT 生图出一套提案」「先出白板稿再生图」「出三个设计方向」「图文版 PPT」「把图片版 / 生图版 PPT 转回可编辑」「整页图片的 PPT 还原成可编辑」时使用；已有白板稿、已有生图页面、已有整页图片 PPTX 或 PDF 时，从对应阶段进入。macOS 与 Windows 10 22H2 / 11 均可运行。只要求普通可编辑 PPT、不走生图路线时不使用。
---

# 文图方案（Doc-image-deck）

脚本入口：macOS 为 `$S/deck`，Windows 为 `$S\deck.cmd`（PowerShell 中写 `& "$S\deck.cmd" …`）。`$S` = 本 skill 的 `scripts/` 目录：Claude Code 下为 `~/.claude/skills/doc-image-deck/scripts`，Codex 下为 `~/.codex/skills/doc-image-deck/scripts`，两者指向同一份文件；Windows 上 `~` 即 `%USERPROFILE%`。下文统一写 `$S/deck`，`$S/deck help` 列出全部命令。

| 阶段 | 产出 | 停下来等用户 |
|---|---|---|
| 1 白板稿 | `outline.json` → 用 humanizer-zh 去 AI 味 → 标点整理 → 白板稿 PPTX：终稿文字、结构、每页视觉规划与版面、配图建议，不做设计 | **确认点 1**：确认白板稿，同时索取视觉参考、品牌材料和 Logo |
| 2 设计方向与生图 | 品牌 VI 与 Logo 调研 → 3 个完全不同的设计方向样张 → 用户选定 → 全量逐页整页图片，逐页核对文字 | **确认点 2**：选方向 |
| 3 合成 | 图文版 PPTX + PDF（整页图 + 独立的 Logo 与页码对象） | — |
| 4 可编辑还原 | 可编辑版 PPTX + PDF（去字底图 + 可编辑文本框） | 仅页面含截图、海报时审阅排除区 |
| 5 交付清理 | 删除中间文件，写交付检查 | — |

入口判断：从文档出发走 1–5；用户给的是已定稿的大纲或白板稿，先转成 `outline.json`，生成白板稿后仍走确认点 1；已有逐页生图，从 3 开始；已有整页图片 PPTX 或 PDF（包括别人做的生图稿），只走 4、5，流程见 `references/04_可编辑还原.md`。

## 开始前

1. 运行 `$S/deck check`。有 ✗ 项时运行 `$S/deck setup` 补齐（首次约 10–20 分钟，下载 Python 依赖约 1 GB、LaMa 权重 196 MB、缺失的思源字体，没有 humanizer-zh 时一并安装），细节见 `references/06_环境与安装.md`。依赖 macOS 或 Windows 10 22H2 / 11、Microsoft PowerPoint、Codex CLI（用 ChatGPT 账号登录）。
2. 建项目目录，放在用户的交付目录下，命名遵循宿主的文件命名规则（例：`<项目名>_AC_0925A/`）。在里面写 `project.json`：

```json
{
  "name": "秋季新品上市整合营销方案",
  "suffix": "AC_0925A",
  "source": "../秋季新品上市方案.docx",
  "audience": "Chinese business proposal for a tea-drink brand",
  "brands": ["品牌名", "代理公司名"],
  "brand_materials": ["<客户提供的品牌手册.pdf>", "<截图.png>"],
  "logos": [{"light": "00_Logo/<浅底用>.png", "dark": "00_Logo/<深底用>.png", "corner": "bl", "height_in": 0.26}],
  "page_number": {"corner": "br", "skip_first": true, "skip_last": true, "format": "{:02d}"},
  "parallel": 4
}
```

用户限定页数或不要章节页时，加 `"max_pages": 15`、`"section_pages": false`，`deck visual` 会检查。`suffix` 用于所有交付文件名（`<name>_白板稿_<suffix>.pptx`、`_图文版_`、`_可编辑版_`）；在 Codex 中按用户在 Codex 的命名习惯（如 `OC_0925A`）。`source` 是原文档的相对路径，查找视觉参考时会一并搜索它所在的目录。`brand_materials` 列客户提供的品牌材料（也可以直接放进 `01_设计方向/品牌材料/`）；`logos` 在阶段 2 用 `deck logo` 生成，路径可以相对项目目录。`brands` 里的品牌会写进提示词的禁画清单，避免生图自己画 Logo。

## 阶段 1 · 白板稿

1. 通读文档，按 `references/01_白板稿.md` 的结构写 `00_白板稿/outline.json`：每页一个结论式标题、终稿正文、`layout_hint`（版面建议）、`image_hint`（配图建议）、`tone`（明暗）、讲稿。文字按宿主的写作规范成稿，达到可以直接对客户使用的程度；生图阶段逐字照搬这里的文字，之后很难再改。
2. 控制每页字量：正文不超过约 150 个汉字，表格不超过 6 行 × 5 列。生图模型字越多错字越多，超出时拆页。
3. **逐页视觉规划**：分拆定稿后，逐页分析这一页在说什么、文字之间是什么关系，写 `visual`：`message`（观众要看懂的一件事）、`structure`（信息结构：流程、闭环、漏斗、时间轴、对比、构成等）、`form`（具体画法：图形、方向、比例、哪段文字落在哪个图形上）、`focal`（唯一的视觉焦点）、`skeleton`（构图骨架）、`motif`（配图母题）。相邻两页骨架不同，同一骨架不超过内容页的四分之一，「并列要点」只用于真正平行的内容。方法和两张可选表见 `references/01_白板稿.md`「逐页视觉规划」。这一步决定全稿是否雷同：只给文字和一句版面建议，模型会把多数页画成「标题 + 卡片」。
4. **去 AI 味**：`$S/deck humanize <项目> export` 把全部上屏文字和讲稿写成 `00_白板稿/文案_原稿.md`，并打印 humanizer-zh 的 SKILL.md 位置。按那份 SKILL.md 的规则编辑文案（Claude Code、Codex 里也可以直接调用 humanizer-zh skill），保留每行的 ⟦编号⟧ 标记，另存为同目录的 `文案_改后.md`，再运行 `$S/deck humanize <项目> import`。导入时逐条核对标记、数字、英文和引号内文字，不一致就拒绝写回，按提示改后重新导入。页数多时可以交给子 agent 处理这一步。规则见 `references/01_白板稿.md`「去 AI 味」。
5. `$S/deck whiteboard <项目>`：有文案没做去 AI 味时拒绝运行。先做**标点整理**（标题和短句去掉句号，只有详细描述和成段文字保留句号，规则见 `references/01_白板稿.md`），再生成白板稿 PPTX 和 `outline.md`，最后检查视觉规划并写 `00_白板稿/视觉规划.md`（也可单独运行 `$S/deck visual <项目>`）。标点改动记在 `00_白板稿/标点整理.md`；其中列出的「列表内句号不统一」要看一下，按需改写后重跑。视觉规划有 ✗ 项时改 `visual` 直到通过（`deck prompts` 会拒绝未通过的稿子）。打开 PPTX 检查有没有溢出、漏页。
6. `$S/deck refs <项目>`：在项目目录、上级目录和原文档所在目录里查找可用作视觉参考的图片、PDF、PPT（情绪板、品牌手册、往期提案、主视觉、海报），生成 `01_设计方向/参考候选/候选清单.md` 和 `候选对照.jpg`。
7. **确认点 1（必须停下）**：在一条消息里给用户：
   - 白板稿 PPTX 的路径、页数和逐页标题；去 AI 味改了几条（`去AI味记录.md`）、标点整理改了几处。
   - 视觉规划：`视觉规划.md` 的路径和构图节奏（逐页骨架），请用户顺带看各页画法是否合理。
   - 视觉参考：本地找到的候选（附 `候选对照.jpg`，按 R01、R02 编号），并问用户是否有想用的视觉参考，可以指定编号，也可以另外提供图片、PDF 或 PPT。说明规则：用户给一个参考，它成为三个方向之一，另外两个方向由你设计；不给参考，三个方向都由你设计。
   - 品牌材料与 Logo：请用户提供品牌手册或 VI 规范、Logo 文件（彩色版和反白版）、往期物料、官方页面截图，放进 `01_设计方向/品牌材料/` 或给出路径，并说明 Logo 放哪个角。没有也可以继续，阶段 2 会联网检索品牌的公开资料。

   然后结束本轮，等用户回复，不要继续做设计方向或生图。
8. 用户要求改白板稿时，改 `outline.json`；改动的文字用 `deck humanize <项目> export --changed` 只导出改过的条目，处理后 import；用户给定原话的条目用 `deck humanize <项目> accept --note "用户指定原话"` 保留原样。然后重跑 `deck whiteboard`；改动大时把新版再给用户看一次。用户确认后运行 `$S/deck approve <项目> --note "<用户意见摘要>"`。`deck prompts` 在确认记录缺失、或确认后白板稿文字又被改过时会拒绝运行；之后任何改字都要让用户知道，并重新 `deck approve`。

## 阶段 2 · 设计方向与全量生图

生图走 Codex 内置 `image_gen`（ChatGPT 套餐额度，不走 API），每页一次调用，约 1–2.5 分钟，输出 1672 × 941；4 路并发稳定，4 页约 80 秒。方向写法、提示词结构、已知问题见 `references/02_设计方向与生图.md`。

1. **品牌 VI 与 Logo 调研（定方向前必须）**：设计方向要建立在客户品牌上，先花 10–15 分钟做快速调研，方法见 `references/02_设计方向与生图.md`「品牌调研与 Logo」。
   - `$S/deck brand <项目> init`：生成 `01_设计方向/品牌调研.md` 模板，列出 `品牌材料/` 和 `brand_materials` 里的文件。
   - 读客户材料：截图、图片直接看；PDF、PPTX 先导出为图片再看：`$S/deck refs <项目> --export <文件> --pages 1,3,5 --to 01_设计方向/品牌材料/导出`。
   - 联网检索：品牌官网、公开的品牌手册、电商旗舰店首页与详情页、官方社交账号，记下品牌色（色值）、Logo 的版本、标准字与常用字体、摄影或插画风格、禁用做法。Claude Code 用 WebSearch / WebFetch；Codex 要以 `codex --search` 启动才有联网检索。查不到的内容写「不适用」和原因，不要猜。
   - 填写 `品牌调研.md` 六节（资料来源、品牌色、Logo、字体与版式、视觉风格与禁忌、对三个方向的约束），运行 `$S/deck brand <项目> check` 直到通过。
   - Logo：只用客户提供或官方发布的文件，不重画。`$S/deck logo <项目> <客户Logo>[::反白版] [<代理Logo>[::反白版]] --corner bl`：多个 Logo 自动拼成联合 Logo，只有一个版本时自动生成另一版（白字改灰、深字改白，彩色部分保留），写入 `project.json`。打开 `00_Logo/预览.png` 看深浅两版是否正常。
2. **定三个方向的来源**：
   - 用户给了 1 个参考（或几份风格相同的参考）：A 按参考建立，B、C 由你设计。
   - 用户给了 2 个风格不同的参考：A、B 按参考建立，C 由你设计。
   - 给了 3 个以上：按用户的优先顺序取 3 个风格最不同的；没有给：A、B、C 都由你设计。

   参考先导出为图片：`$S/deck refs <项目> --export R03 --pages 1,4 --to 01_设计方向/A/ref`（用户另给的文件把 `R03` 换成文件路径）。看过参考图后再写方向：从参考里提炼配色（写出色值）、字体、版式语法、配图处理和质感；只取风格，不照搬参考里的文字、Logo 和品牌资产。
3. **写 3 个方向**：`01_设计方向/A|B|C/direction.json`。三个方向都要遵守 `品牌调研.md` 第六节的约束，每个方向用 `brand_fit` 写清它怎样用品牌色、Logo 和品牌风格；在此之上三个方向要**完全不同**：`dims` 的字体、配色、版式语法、配图、质感五项两两都不一样，`imagery_mode`（写实摄影、产品静物、插画、纯图形、材质肌理、三维渲染、纯文字排版）三个方向各用一种；同时都要贴合内容和客户行业。按参考建立的方向写 `"source": "reference"` 和 `"refs"`，自行设计的写 `"source": "original"`。
4. `$S/deck directions <项目>` 检查品牌调研是否完成、三个方向是否都有 `brand_fit` 且完全不同，不通过就改到通过，同时生成 `01_设计方向/方向说明.md`（给用户看的对比表，含「品牌呼应」一行）。
5. **出样张**：每个方向选 2 页，封面 + 一页以图示为主的内容页（视觉规划里骨架为 `diagram`、信息最密的一页）：
   `$S/deck prompts <项目> --direction 01_设计方向/A/direction.json --out 01_设计方向/A/prompts --pages p01,p07`
   `$S/deck gen 01_设计方向/A/prompts --out 01_设计方向/A/samples`（B、C 同样，可同时后台运行；按参考建立的方向会自动附上参考图）
   `$S/deck sheet 01_设计方向/方向对比.jpg "A 封面=01_设计方向/A/samples/p01_v1.png" "A 内容=…" …`（每行一个方向）
6. **确认点 2（必须停下）**：把方向对比图、`方向说明.md` 和品牌调研的要点（品牌色、Logo 预览）给用户，请用户选定方向（也可以指定混合调整，如「A 的版式 + C 的配色」，按要求改写方向后重出样张）。三个方向用的是同一份视觉规划，样张构图相近是正常的，比较的是字体、配色、配图和质感。结束本轮等用户回复。
7. **全量生图**：先按选定方向复核视觉规划：`motif` 改成适合该方向配图方式的题材，样张暴露的问题（如图示画得太满、焦点不明显）写回相关页的 `form`，运行 `$S/deck visual <项目>` 通过后再生成提示词。
   `$S/deck prompts <项目> --direction 01_设计方向/<选定>/direction.json --out 02_生图/prompts`
   `$S/deck gen 02_生图/prompts --out 02_生图/raw --ref-light <选定方向的内容样张> --ref-dark <选定方向的封面样张>`
   样张作为风格参考图附上，保证全稿风格一致；选定方向来自用户参考时，参考图也会附上（每次最多 3 张）。页数多时后台运行，每 10 页约 3–5 分钟。
8. **核对与重生成**：`$S/deck textcheck <项目> 02_生图/prompts 02_生图/raw`。`MISS`（缺字、错字）和 `CORNER`（预留角落里有字）的页先放大看图：OCR 偶尔漏读大标题，确认文字在图上就不必重生成。确实有问题的页用 `--pages` 重新生成，最多两轮；两轮仍不过，改写该页版面建议后再生成。`CORNER` 多半是脚注落进了 Logo 角，在版面建议里把脚注放进结论横栏右端或标题区，一轮就能解决。需要删改文字时先告诉用户，确认后 `deck approve` 再生成。`NEAR` 多为 OCR 误差（如把「滞」读成「滯」），看图确认。
9. 生成全稿联系表 `$S/deck sheet 02_生图/联系表 --raw 02_生图/raw --cols 3`，逐张检查：对照 `视觉规划.md` 看每页的图示和构图是否落地、相邻页是否雷同、图示关系（箭头方向、回流、比例）是否画对；配图题材不重复、同级标题大小一致、没有乱码。`textcheck` 查不出多出来的文字，要人工看：模型会把画法说明里的词画成标签，也会自行算出百分比写在图上。有问题的页重生成，并在 `02_生图/raw/selected.json` 里指定采用的版本。

## 阶段 3 · 合成图文版

`$S/deck compose <项目>`：选定的生图放大 2 倍，每页一张满幅图，Logo 与页码作为独立对象叠加（按所在角落明暗自动选浅底 / 深底 Logo；页码落在照片上时加半透明底块；封面、封底默认不加页码），讲稿写入备注，并用 PowerPoint 导出 PDF。抽查 3–5 页 Logo 和页码有没有压到内容，压到了就回阶段 2 重生成该页，或调整 `project.json` 里的角落和尺寸。

## 阶段 4 · 可编辑还原

```
$S/deck editable <项目>/04_可编辑 03_合成/<name>_图文版_<suffix>.pptx 04_可编辑/<name>_可编辑版_<suffix>.pptx \
    --outline 00_白板稿/outline.json --ref 03_合成/<name>_图文版_<suffix>.pdf
```

一次完成抽页、识别、字体拟合、LaMa 去字、装配、PowerPoint 导出和比对。以白板稿文字为准校正识别结果，所以本流程自己生成的稿件几乎不需要人工校字。之后：

1. 看 `04_可编辑/03_QA/全稿对照_*.jpg`。页面里有截图、海报、图表、表情包时，用 `$S/deck review` 读出坐标，写进 `04_可编辑/config.json` 的排除区，重跑这些页（`$S/deck layers <工作目录> p05 p09`，再 `deck build`、`deck verify`）。
2. 看 `校对表_*.png`；有残留错字写进 `config.json` 的 `replace`（繁体字如「約」也在这里改回）。
3. 大号数字配小号单位或前缀（「约 250 条」「310 万元」）常被识别成一行、按大号字排版；行首的小字「约」还会被当成图标剔出墨迹框。在 `pages.<pid>.split_points` 里把小字和数字切开，切分点的 x 取两者之间的空白处。渐变色的艺术字标题颜色可能取错，放进排除区留在底图。
4. 规则、参数和排查方法见 `references/04_可编辑还原.md` 与 `references/04b_还原技术细节.md`。

## 阶段 5 · 交付与清理

1. 把白板稿、图文版、可编辑版的 PPTX 和 PDF 放到项目根目录。
2. 按 `references/05_交付与清理.md` 写 `05_QA/交付检查_<suffix>.md`：页数、字体、比对数值、文字处理说明、留在底图的内容、已知差异。
3. `$S/deck cleanup <项目> --dry-run` 列出将删除的文件和可释放空间，然后 `$S/deck cleanup <项目>` 执行。默认保留大纲、方向与参考图、提示词、每页选定的生图原稿、`04_可编辑/config.json` 和全部交付文件，足够日后重新合成或重新还原；用户要求彻底清理时加 `--deep`。

## 在 Windows 上运行

命令与 macOS 相同，用 `$S\deck.cmd` 代替 `$S/deck`。差别：

- 运行环境在 `%LOCALAPPDATA%\doc-image-deck`；文字识别用 RapidOCR（PaddleOCR PP-OCRv6 模型），代替 macOS 的 Apple Vision；PDF 渲染用 pypdfium2；PowerPoint 通过 COM 驱动，不需要 macOS 那样的沙盒中转。
- 字体由 `deck setup` 为当前用户安装（不需要管理员权限）：思源宋体按粗细生成独立字体，名称与可编辑版里写的字体名一致；装完后要重启已打开的 PowerPoint。
- 没有 NVIDIA 显卡时 LaMa 在 CPU 上运行，可编辑还原每页比 Apple 芯片慢；有显卡时先设置 `DOC_IMAGE_DECK_TORCH_INDEX` 再 `deck setup` 安装 CUDA 版 torch（见 `references/06_环境与安装.md`）。
- 在 Windows 上生成的可编辑版按 Windows 版 PowerPoint 标定；在另一平台打开时，行位置可能有 1 pt 左右的偏差。

## 在 Codex（ChatGPT）中运行

整套流程在 Codex 中同样可用，命令完全一致：`deck gen` 本身就是调用 Codex 的内置生图。区别有五处：

- 两个确认点同样要停：给出内容和问题后结束本轮，等用户回复再继续。
- 权限：`deck gen` 会再起一个 `codex exec`（需要联网）；`deck compose`、`deck editable`、`deck pdf` 和导出 PPTX 参考的 `deck refs --export` 会通过 AppleScript 驱动 PowerPoint。Codex 默认沙盒不允许这两类操作，运行这几条命令时按提示批准提权，或以完全访问模式启动会话；`deck humanize`、`deck whiteboard`、`deck refs`（查找）、`deck approve`、`deck directions`、`deck prompts`、`deck check` 在默认沙盒里就能运行。
- 品牌调研要联网：以 `codex --search` 启动会话才有 `web_search`；没有联网时只用客户材料，在 `品牌调研.md` 的资料来源里写明。
- 单页返修可以直接调用内置 `image_gen` 工具生成，再把图片复制到 `02_生图/raw/pNN_vK.png` 并更新 `selected.json`。
- 整个会话使用 Codex 配置中最强的模型和高推理强度（如 `model_reasoning_effort = "high"`）；批量生图的子调用固定用低推理强度，因为提示词原样传给生图工具，不需要模型改写。

## 容易出错的地方

- 不要跳过确认点 1：白板稿文字会逐字进入每一页生图，生图后再改字要重新生成对应页。
- 去 AI 味只改表达，不补充原文没有的事实；导入核对只能拦住数字、英文和引文的变化，改后的意思是否走样还要看 `去AI味记录.md`。
- 三个方向容易只在配色上有差别、配图都是同一类题材；`deck directions` 会拦下五项维度或配图方式重复的方向。
- 没看品牌 VI 就定方向，三个方向可能都用了与品牌色冲突的主色，或让反白 Logo 落在浅底上；`deck directions` 会拦下没有完成品牌调研、方向没写 `brand_fit` 的稿子。
- 画法说明（`visual.form`、正文块 `visual`）里写了上屏文字以外的词，模型会把它们画成标签；这类标签要么写进正文重新确认，要么在画法说明里换成形状描述。
- 生图模型不严格遵守「角落留空」，交给 `textcheck` 的 `CORNER` 检查兜底，不要跳过；脚注最容易落进左下角的 Logo 区。
- 同一套稿的配图题材容易撞车（机房、光纤、芯片反复出现）；写 `image_hint` 时就逐页区分，联系表阶段再核对一遍。
- 全稿版式雷同（每页都是标题 + 三张卡片）：根源是提示词里只有文字、没有画法。逐页写 `visual`，按文字之间的关系选信息结构和画法，相邻页换骨架；`deck visual` 拦下缺规划、相邻同骨架和骨架用得过多的稿子。
- PowerPoint for Mac 受沙盒限制，脚本会把文件复制到它的容器目录再导出；不要改成直接打开桌面上新建目录里的文件。
- 可编辑还原阶段最多开 2 个进程（LaMa 在 16 GB 内存上的上限），`deck layers` 已按此设置。
