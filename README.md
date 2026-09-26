# 文图方案 · Doc-image-deck

![version](https://img.shields.io/badge/version-2.0.0-blue.svg) ![license](https://img.shields.io/badge/license-MIT-green.svg) ![platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey.svg)

从一份文档出发，做出一套「整页生图」风格的演示稿，最后交付文字和排版都能自由修改的 PowerPoint。Claude Code 与 Codex（ChatGPT）共用同一个 skill，生图用 ChatGPT 套餐里的 Codex 内置 `image_gen`，不走 API。支持 macOS 和 Windows 10 22H2 / 11。

*A Claude Code / Codex skill that turns a document into a whiteboard deck, three distinct design directions, a fully image-generated slide deck (ChatGPT image generation via Codex), and finally an editable PowerPoint rebuilt from those images. Runs on macOS and Windows 10 22H2 / 11.*

## 流程

```
文档
 │  1 白板稿      故事线（标题串读、章节、原文来源）→ outline.json 正文与逐页视觉规划 → humanizer-zh 去 AI 味 → 标点整理 → 白板稿 PPTX（终稿文字 + 画法 / 版面 / 配图建议，不做设计）
 │     ⏸ 确认点 1  用户确认故事线与白板稿；同时在本地查找视觉参考，并向用户索取参考、品牌材料和 Logo
 │  2 设计方向    品牌 VI 与 Logo 快速调研（客户材料 + 联网检索）→ 3 个完全不同的方向（封面构图各不相同；用户给的参考作为其中之一）→ 每个方向 2 张样张
 │     ⏸ 确认点 2  用户选方向
 │     全量生图    逐页生成整页图片（文字、版式、配图一次成形）→ OCR 核对缺字、预留角落、多出文字、标题漂移、多出句号 → 局部改字 → 子 agent 审图
 │  3 合成        放大 2 倍 + Logo + 页码（独立对象）→ 图文版 PPTX / PDF
 │  4 可编辑还原  三路 OCR 投票 → 按白板稿校字、切分大数字与单位 → 字体与字重拟合 → LaMa 去字 → 可编辑文本框 → PowerPoint 导出比对
 │  5 交付清理    写交付检查，删除中间文件
 ▼
白板稿 PPTX · 图文版 PPTX + PDF · 可编辑版 PPTX + PDF
```

也可以从中间进入：已有定稿大纲从阶段 1 的白板稿开始；已有逐页生图从阶段 3 开始；手上只有别人做的整页图片 PPT 或 PDF，只走阶段 4、5。

### 流程规则

1. **去 AI 味**：白板稿文案（上屏文字与讲稿）先用 [humanizer-zh](https://github.com/op7418/Humanizer-zh) 处理，再生成白板稿。导出的文案每条带编号标记；写回时逐条核对标记、数字、英文和引号内文字，有变化就拒绝写回。改动逐条记在 `去AI味记录.md`，没处理完不能生成白板稿。
2. **标点整理**：标题和短句去掉句号，只有详细描述（单句不少于 40 字，说明类文字不少于 30 字）和多句段落保留句号；列表条目结尾的「；」同样处理。生图提示词禁止模型自行加句号，文字核对会标出多出句号的页。
3. **白板稿先确认**：白板稿交给使用者确认后才能生图。确认记录写进 `project.json`；生成提示词的命令会核对，没有确认、或确认后上屏文字改过，都会拒绝运行。
4. **三个完全不同的方向**：字体、配色、版式语法、配图、质感五项两两都不同，配图方式（写实摄影、产品静物、插画、纯图形、材质肌理、三维渲染、纯文字排版）三个方向各用一种，由 `deck directions` 检查。
5. **视觉参考**：在项目目录、上级目录和原文档所在目录里查找图片、PDF、PPT 等可能的视觉参考，连同缩略图一起询问使用者。使用者给一个参考，它成为三个方向之一，另外两个方向由 agent 设计；不给参考，三个方向都由 agent 设计。
6. **品牌调研先于设计方向**：定方向前先读客户提供的品牌手册、Logo、往期物料和截图，再联网检索品牌官网、旗舰店和官方账号，把品牌色（色值）、Logo 版本、字体、视觉风格与禁忌、对三个方向的约束写进 `品牌调研.md`。`deck directions` 在调研完成、每个方向都写明如何呼应品牌之前不放行。`deck logo` 把客户与代理的 Logo 拼成浅底、深底两版联合 Logo，只有一个版本时自动生成另一版。
7. **故事线先于正文**：先写全稿结论、章节和每页的结论式标题，并标出每页来自原文哪一节。`deck storyline` 检查章节连续、每个出处都能在原文里找到、原文的章节都有着落（不上屏的要写理由）、封底不是「谢谢」页、同一指标跨页数值一致，生成标题串读，确认点 1 放在第一项给使用者看。
8. **按用途和构图控制字量**：`deck_mode` 分阅读稿（默认，页面脱离讲者也能看懂）和演讲稿（一页一个观点，细节进讲稿）；每种构图骨架有各自的字数和文字条数上限，演讲稿还检查页面节奏；明细放进附录页（A1、A2）。
9. **逐页视觉规划**：分拆定稿后，逐页分析这一页要说清什么、文字之间是什么关系（流程、闭环、漏斗、时间轴、对比、构成……），写出具体画法、唯一的视觉焦点和构图骨架。提示词把风格系统写成全稿统一、把构图和图示写成逐页变化，并告诉模型前后两页用的骨架。`deck visual` 拦下缺规划、相邻两页同骨架、同一骨架用得过多、超出容量的稿子，避免整套稿画成一页一个样板。
10. **方向之间连封面也不同**：每个方向写自己的封面构图和主体，图示语言、配色策略也按固定选项比较；默认不画图标，默认禁画常见的生成外观（塑胶三维、玻璃拟态、发光线条、代表 AI 的机器人等）。
11. **生图质检**：OCR 核对缺字、预留角落、多出的文字和标题漂移；只错一两个字时局部改字、其余像素不变；最后交给新开的子 agent 对照视觉规划逐页审图，同一问题出现在 3 页以上时改方向或提示词，不逐页修。

## 安装

一次安装同时给 Claude Code 和 Codex 用。在 ChatGPT 里使用指的是 Codex（CLI、桌面应用或 IDE 插件，用 ChatGPT 账号登录）；ChatGPT 网页版和桌面版的对话窗口不能运行本地脚本，不能运行本 skill。skill 复制到 `~/.agents/skills/doc-image-deck/`，两个客户端各有一个链接指向它。两边都需要 Microsoft PowerPoint、Python 3.10+、git，以及用 ChatGPT 账号登录的 Codex CLI（生图走 Codex 内置 `image_gen`，在 Claude Code 里使用也一样）。

### Claude Code（终端、IDE 插件、Claude 桌面应用的 Code 标签页）

```bash
git clone https://github.com/mjlens-spec/Doc-image-deck.git ~/Doc-image-deck
python3 ~/Doc-image-deck/scripts/install.py
~/.claude/skills/doc-image-deck/scripts/deck check
```

最后一行显示「环境就绪。」后，新开一个会话，输入 `/doc-image-deck` 或说「用文图方案把这份文档做成提案」。品牌调研用 Claude Code 自带的联网检索。完整步骤、Windows 命令、权限设置和给 agent 的逐条安装步骤见 [docs/install-claude.md](docs/install-claude.md)。

### Codex（ChatGPT 账号登录的 Codex CLI）

```bash
git clone https://github.com/mjlens-spec/Doc-image-deck.git ~/Doc-image-deck
python3 ~/Doc-image-deck/scripts/install.py
~/.codex/skills/doc-image-deck/scripts/deck check
codex --search
```

`--search` 打开联网检索，品牌调研需要它。生图和驱动 PowerPoint 的命令会请求提权，按提示批准，或用 `codex --search -s danger-full-access` 启动。提示里写 `$doc-image-deck` 触发。完整步骤、Windows 命令和给 agent 的逐条安装步骤见 [docs/install-codex.md](docs/install-codex.md)。

### 安装内容

Windows 用 PowerShell 运行 `py -3 $HOME\Doc-image-deck\scripts\install.py`，入口是 `deck.cmd`。`install.py` 把 skill 复制到 `~/.agents/skills/doc-image-deck/`，在 `~/.claude/skills/` 和 `~/.codex/skills/` 各建一个链接，再运行 `setup.py` 安装运行环境（首次约 10–20 分钟）：

| 项目 | macOS | Windows |
|---|---|---|
| 运行环境 | `~/.local/share/doc-image-deck/` | `%LOCALAPPDATA%\doc-image-deck\` |
| Python 虚拟环境 | numpy、opencv、python-pptx、torch 等，约 1 GB | 同左，另加 pywin32 |
| LaMa 权重（去字） | `~/.cache/torch/hub/checkpoints/big-lama.pt`，196 MB | 同左 |
| 文字识别 | Apple Vision，本机编译 `bin/ocrbox` | RapidOCR（PaddleOCR PP-OCRv6 模型） |
| 思源宋体、思源黑体 | 装到 `~/Library/Fonts` | 思源宋体按字重生成静态字体，与思源黑体一起为当前用户安装 |
| humanizer-zh | 没有时自动下载到 `~/.agents/skills/humanizer-zh` | 同左 |
| PowerPoint 排版标定 | `calibration.json`，打开 PowerPoint 约 1 分钟 | 同左 |

`scripts/deck check`（Windows：`scripts\deck.cmd check`）只检查不安装。运行环境位置可用环境变量 `DOC_IMAGE_DECK_HOME` 修改。

## 使用

在 Claude Code 或 Codex 里直接说：

- 「用文图方案把这份文档做成提案」「把这份文档做成生图 PPT」
- 「先出白板稿再生图」「出三个设计方向」
- 「把这份图片版 PPT 转回可编辑」

agent 会按 `SKILL.md` 的流程执行，在两个确认点停下来等你。主要命令（`deck help` 列出全部；Windows 用 `deck.cmd`）：

| 命令 | 作用 |
|---|---|
| `deck storyline <项目>` | 检查故事线：章节、原文来源与覆盖、首尾页、跨页数据，生成标题串读 |
| `deck humanize <项目> export` / `import` | 导出文案交给 humanizer-zh，处理后核对并写回 |
| `deck whiteboard <项目>` | 标点整理 + 生成白板稿 PPTX + 检查视觉规划 |
| `deck visual <项目>` | 检查逐页视觉规划，生成视觉规划表 |
| `deck refs <项目>` | 查找本地视觉参考，生成候选清单和缩略图对照 |
| `deck brand <项目> init` / `check` | 品牌 VI 与 Logo 调研：生成调研模板、检查是否填完 |
| `deck logo <项目> <Logo>[::反白版] …` | 生成浅底、深底用（联合）Logo，写入 `project.json` |
| `deck approve <项目>` | 记录使用者已确认白板稿 |
| `deck directions <项目>` | 检查品牌调研和三个方向，生成方向说明 |
| `deck prompts` / `deck gen` / `deck textcheck` | 生成提示词、并发生图（`--skeleton-refs` 按构图骨架配参考）、核对文字 |
| `deck fix <项目> <提示词目录> <生图目录> --pages p05` | 只错一两处字时局部改字 |
| `deck audit <项目> init` / `check` | 审图清单交给子 agent，汇总全稿问题 |
| `deck compose <项目>` | 合成图文版 PPTX 与 PDF |
| `deck editable …` | 还原为可编辑 PPTX 与 PDF |
| `deck cleanup <项目> [--dry-run]` | 清理中间文件 |

在 Codex 中运行时，`deck gen`（需要联网）和驱动 PowerPoint 的 `deck compose`、`deck editable`、`deck pdf` 需要批准提权，或以完全访问模式启动会话。

## 实测

| 场景 | 结果 |
|---|---|
| 74 页整页图片提案还原为可编辑版（macOS） | 1,631 行文字全部可编辑；与原稿逐页平均色差全稿均值 6.91（0–255 色阶） |
| 4 页文档端到端（macOS） | 白板稿几秒；3 个方向 6 张样张约 3 分钟；4 页全量生图 77 秒；可编辑还原约 3 分钟，32 条文案与白板稿逐字一致 |
| 同一 4 页走 Windows 的识别与渲染路径（RapidOCR + pypdfium2，在 Mac 上运行） | 32 条文案逐字一致；逐页色差 7.76、12.96、5.29、4.85，与 Apple Vision 路径（8.04、13.34、5.91、5.52）相当 |
| 15 页执行规划端到端（macOS，1.2.0） | 白板稿 15 页，13 页内容页用 8 种构图骨架；3 个方向 6 张样张一次成功；全量 15 页一次成功，2 页返修；可编辑版 274 行文字可编辑，与图文版逐页平均色差均值 8.11 |
| 同一份执行规划第二版（macOS，1.2.1） | 先做品牌调研，再出 3 个扁平杂志编辑风方向；上屏文字增加 48%；全量 15 页一次成功，2 页返修；可编辑版 364 行文字可编辑，逐页平均色差均值 9.22 |
| 2.0.0 回归：用新的可编辑还原重跑 1.2.1 的 15 页稿 | 不再手工圈大数字：373 行可编辑（原 364 行），留在底图 13 处（原 16 处），其中 1 处是自动识别的超大数字；逐页平均色差均值 9.49（原 9.22，原稿把 4 组大数字留在底图） |
| 2.0.0：新文档、演讲稿、13 页（含附录）| 故事线与容量检查一次通过；3 个方向样张的封面构图互不相同（1.2.x 两次测试的 6 张封面都是同一构图）；内容样张没有规划外的图标；多出文字检查拦下一张照片封面里模型自行写的手写字 |
| 生图单张耗时 | 55–220 秒（附参考图时偏长），4 路并发 |

## 关于生图模型

Codex CLI 0.155 的内置 `image_gen` 在请求里写的模型名是 `gpt-image-2`，没有选择模型的配置项。OpenAI 2026-09-08 发布 ChatGPT Images 2.5 时称其面向 ChatGPT 和 Codex 用户开放，但从客户端无法确认服务端实际用的版本，生成图片的元数据里也没有版本号。API 里可以显式指定 `gpt-image-2.5-flare` / `gpt-image-2.5-sunburst`，需要 API Key、按量计费。OpenAI 使用条款禁止用程序自动抓取 ChatGPT 网页的输出，本项目不做网页自动化。

## 仓库结构

```
SKILL.md                 运行规程（Claude Code / Codex 共用）
agents/openai.yaml       Codex 界面信息
references/              各阶段细则：白板稿、设计方向与生图、合成、可编辑还原、交付清理、环境安装
scripts/deck, deck.cmd   命令入口（macOS / Windows），都调用 deck.py
scripts/hostos.py        平台差异：运行环境路径、识别、PDF、字体、外部程序
scripts/*.py             阶段 1–3、5 的脚本，setup.py / install.py 安装
scripts/editable/        阶段 4 可编辑还原
tests/                   单元测试（CI：Linux、Windows）与合成页面的全流程冒烟测试（CI：Windows）
docs/install-claude.md   在 Claude Code 中安装（含给 agent 的逐条步骤）
docs/install-codex.md    在 Codex 中安装（含给 agent 的逐条步骤）
docs/前因后果.md          这个项目怎么来的、做过的决定和验证记录
```

## 已知限制

- 需要 Microsoft PowerPoint：导出、比对和标定都以 PowerPoint 的渲染为准。可编辑版按生成它的那台机器上的 PowerPoint 标定，换平台打开时行位置可能有 1 pt 左右的偏差。
- Windows 上没有 NVIDIA 显卡时，LaMa 去字在 CPU 上运行，可编辑还原比 Apple 芯片慢。
- 生图的字形没有对应的字体文件，可编辑版用思源宋体 / 思源黑体按粗细近似；生图宋体字面比思源宋体宽，PowerPoint 又不能横向拉宽文字，只能做到接近。
- 页面里的截图、海报、表情包要人工圈定为排除区，留在底图上。
- 生图额度受 ChatGPT 套餐限制；74 页全量生图约 40 分钟。
- 演讲稿的每页容量是初始值，还没有足够的测试数据；阅读稿的容量来自一次 15 页测试。
- `deck gen --skeleton-refs` 和 `deck prompts --corner-guide` 是可选项，对标题漂移和压角的改善还在对比测试中。
- 多出文字检查查不出两位数编号（01、02）和图标，这两类靠默认禁画项和审图。

## 许可

MIT，见 [LICENSE](LICENSE)。运行时下载的第三方组件不随仓库分发，各自遵循其许可：LaMa 模型与 simple-lama-inpainting（Apache-2.0）、RapidOCR 与 PaddleOCR 模型（Apache-2.0）、pypdfium2（Apache-2.0 / BSD-3-Clause）、思源宋体 / 思源黑体（SIL OFL 1.1）、python-pptx（MIT）、humanizer-zh（MIT）等。

项目来历见 [docs/前因后果.md](docs/前因后果.md)，版本记录见 [CHANGELOG.md](CHANGELOG.md)。
