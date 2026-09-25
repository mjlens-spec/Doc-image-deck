# 文图方案 · Doc-image-deck

![version](https://img.shields.io/badge/version-1.0.0-blue.svg) ![license](https://img.shields.io/badge/license-MIT-green.svg) ![platform](https://img.shields.io/badge/platform-macOS-lightgrey.svg)

从一份文档出发，做出一套「整页生图」风格的演示稿，最后交付文字和排版都能自由修改的 PowerPoint。Claude Code 与 Codex（ChatGPT）共用同一个 skill，生图用 ChatGPT 套餐里的 Codex 内置 `image_gen`，不走 API。

*A Claude Code / Codex skill that turns a document into a whiteboard deck, three distinct design directions, a fully image-generated slide deck (ChatGPT image generation via Codex), and finally an editable PowerPoint rebuilt from those images. macOS only.*

## 流程

```
文档
 │  1 白板稿      outline.json → 白板稿 PPTX（终稿文字 + 版面 / 配图建议，不做设计）；标点整理
 │     ⏸ 确认点 1  用户确认白板稿；同时在本地查找视觉参考，并询问用户有没有参考
 │  2 设计方向    3 个完全不同的方向（用户给的参考作为其中之一）→ 每个方向 2 张样张
 │     ⏸ 确认点 2  用户选方向
 │     全量生图    逐页生成整页图片（文字、版式、配图一次成形）→ OCR 核对文字、预留角落、多出的句号
 │  3 合成        放大 2 倍 + Logo + 页码（独立对象）→ 图文版 PPTX / PDF
 │  4 可编辑还原  三路 OCR 投票 → 按白板稿校字 → 字体与字重拟合 → LaMa 去字 → 可编辑文本框 → PowerPoint 导出比对
 │  5 交付清理    写交付检查，删除中间文件
 ▼
白板稿 PPTX · 图文版 PPTX + PDF · 可编辑版 PPTX + PDF
```

也可以从中间进入：已有定稿大纲从阶段 1 的白板稿开始；已有逐页生图从阶段 3 开始；手上只有别人做的整页图片 PPT 或 PDF，只走阶段 4、5。

### 1.0.0 的四项规则

1. **标点整理**：生成白板稿时，标题和短句去掉句号，只有详细描述（单句不少于 40 字，说明类文字不少于 30 字）和多句段落保留句号；列表条目结尾的「；」同样处理。改动逐条记在 `标点整理.md`。生图提示词禁止模型自行加句号，文字核对会标出多出句号的页。
2. **白板稿先确认**：白板稿交给使用者确认后才能生图。确认记录写进 `project.json`；生成提示词的命令会核对，没有确认、或确认后上屏文字改过，都会拒绝运行。
3. **三个完全不同的方向**：字体、配色、版式语法、配图、质感五项两两都不同，配图方式（写实摄影、产品静物、插画、纯图形、材质肌理、三维渲染、纯文字排版）三个方向各用一种，由 `deck directions` 检查。
4. **视觉参考**：在项目目录、上级目录和原文档所在目录里查找图片、PDF、PPT 等可能的视觉参考，连同缩略图一起询问使用者。使用者给一个参考，它成为三个方向之一，另外两个方向由 agent 设计；不给参考，三个方向都由 agent 设计。

## 安装

依赖：macOS、Microsoft PowerPoint for Mac、Codex CLI（用 ChatGPT 账号 `codex login`）、Xcode 命令行工具（`xcode-select --install`）、Homebrew。

```bash
git clone https://github.com/mjlens-spec/Doc-image-deck.git
zsh Doc-image-deck/scripts/install.sh
```

`install.sh` 把 skill 复制到 `~/.agents/skills/doc-image-deck/`，在 `~/.claude/skills/` 和 `~/.codex/skills/` 各建一个链接，再运行 `setup.sh` 安装运行环境（首次约 10 分钟）：

| 项目 | 位置 | 说明 |
|---|---|---|
| Python 虚拟环境 | `~/.local/share/doc-image-deck/venv` | numpy、opencv、python-pptx、torch 等，约 1 GB |
| LaMa 权重 | `~/.cache/torch/hub/checkpoints/big-lama.pt` | 196 MB，去字修补用 |
| 思源宋体、思源黑体 | `~/Library/Fonts` | 可编辑版的字体，缺什么补什么 |
| OCR 工具 | `~/.local/share/doc-image-deck/bin/ocrbox` | 调用 Apple Vision，本机编译 |
| PowerPoint 排版标定 | `~/.local/share/doc-image-deck/calibration.json` | 打开 PowerPoint 约 1 分钟 |

运行环境位置可用环境变量 `DOC_IMAGE_DECK_HOME` 修改。`scripts/deck check` 只检查不安装。

## 使用

在 Claude Code 或 Codex 里直接说：

- 「用文图方案把这份文档做成提案」「把这份文档做成生图 PPT」
- 「先出白板稿再生图」「出三个设计方向」
- 「把这份图片版 PPT 转回可编辑」

agent 会按 `SKILL.md` 的流程执行，在两个确认点停下来等你。主要命令（`scripts/deck help` 列出全部）：

| 命令 | 作用 |
|---|---|
| `deck whiteboard <项目>` | 标点整理 + 生成白板稿 PPTX |
| `deck refs <项目>` | 查找本地视觉参考，生成候选清单和缩略图对照 |
| `deck approve <项目>` | 记录使用者已确认白板稿 |
| `deck directions <项目>` | 检查三个方向是否完全不同，生成方向说明 |
| `deck prompts` / `deck gen` / `deck textcheck` | 生成提示词、并发生图、核对文字 |
| `deck compose <项目>` | 合成图文版 PPTX 与 PDF |
| `deck editable …` | 还原为可编辑 PPTX 与 PDF |
| `deck cleanup <项目> [--dry-run]` | 清理中间文件 |

在 Codex 中运行时，`deck gen`（需要联网）和驱动 PowerPoint 的 `deck compose`、`deck editable`、`deck pdf` 需要批准提权，或以完全访问模式启动会话。

## 实测

| 场景 | 结果 |
|---|---|
| 74 页整页图片提案还原为可编辑版 | 1,631 行文字全部可编辑；与原稿逐页平均色差全稿均值 6.91（0–255 色阶） |
| 4 页文档端到端 | 白板稿几秒；3 个方向 6 张样张约 3 分钟；4 页全量生图 77 秒；可编辑还原 73 秒，32 条文案与白板稿逐字一致；清理后项目从 124 MB 降到 36 MB |
| 生图单张耗时 | 55–120 秒（附参考图时偏长），4 路并发 |

## 仓库结构

```
SKILL.md                 运行规程（Claude Code / Codex 共用）
agents/openai.yaml       Codex 界面信息
references/              各阶段细则：白板稿、设计方向与生图、合成、可编辑还原、交付清理、环境安装
scripts/deck             命令入口
scripts/*.py             阶段 1–3、5 的脚本
scripts/editable/        阶段 4 可编辑还原
tests/                   不依赖运行环境的检查（CI 运行）
docs/前因后果.md          这个项目怎么来的、做过的决定和验证记录
```

## 已知限制

- 只支持 macOS：文字识别用 Apple Vision，导出、比对和标定用 PowerPoint for Mac。
- 生图的字形没有对应的字体文件，可编辑版用思源宋体 / 思源黑体按粗细近似；生图宋体字面比思源宋体宽，PowerPoint 又不能横向拉宽文字，只能做到接近。
- 页面里的截图、海报、表情包要人工圈定为排除区，留在底图上。
- 生图额度受 ChatGPT 套餐限制；74 页全量生图约 40 分钟。

## 许可

MIT，见 [LICENSE](LICENSE)。运行时下载的第三方组件不随仓库分发，各自遵循其许可：LaMa 模型与 simple-lama-inpainting（Apache-2.0）、思源宋体 / 思源黑体（SIL OFL 1.1）、python-pptx（MIT）等。

项目来历见 [docs/前因后果.md](docs/前因后果.md)，版本记录见 [CHANGELOG.md](CHANGELOG.md)。
