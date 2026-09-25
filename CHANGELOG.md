# Changelog

## 1.1.0 - 2026-09-25

去 AI 味工序、Windows 支持，以及生图模型的调研结论。

- 去 AI 味：新增 `scripts/humanize.py`（`deck humanize`）。白板稿文案（上屏文字与讲稿）导出为带编号标记的 `文案_原稿.md`，按 [humanizer-zh](https://github.com/op7418/Humanizer-zh) 编辑后导入；导入时核对标记、数字、英文和引号内文字，改动记入 `去AI味记录.md`。`deck whiteboard` 在有文案未处理时拒绝运行；`--changed` 只导出改过的条目，`accept` 记录用户指定原话的条目
- Windows 10 22H2 / 11：新增 `scripts/hostos.py` 集中处理平台差异。文字识别用 RapidOCR（PP-OCRv6，`scripts/ocr_rapid.py`，输出与 Apple Vision 工具同一格式）；PDF 渲染与抽图用 pypdfium2；PowerPoint 通过 COM 驱动；思源宋体按字重生成静态字体并为当前用户安装（`scripts/fontsetup.py`）；LaMa 支持 CUDA
- 命令入口改为 `scripts/deck.py`，macOS 用 `scripts/deck`、Windows 用 `scripts\deck.cmd` 启动，全部以 UTF-8 模式运行；`setup.sh`、`install.sh`、`run_editable.sh`、`run_pages.sh` 改写为 Python（`setup.py`、`install.py`、`editable/run_editable.py`、`editable/run_pages.py`）。Windows 上 skill 链接用目录联接，不需要管理员权限
- `deck setup` 在各 skills 目录都没有 humanizer-zh 时自动下载安装
- `imagegen.py`：提示词改由标准输入传给 Codex（Windows 的 `codex.cmd` 启动器会截断多行参数），按完整路径启动 Codex
- 测试：新增 `tests/pipeline_smoke.py`（合成页面走完抽页、识别、拟合、LaMa、装配）；CI 增加 Windows 单元测试，以及 Windows 上完整安装运行环境后的冒烟测试
- 调研：Codex 内置 `image_gen` 客户端请求 `gpt-image-2`、不能选模型；Images 2.5 的 API 模型为 `gpt-image-2.5-flare` / `sunburst`；网页版自动化违反 OpenAI 使用条款，不采用。结论写入 README「关于生图模型」

## 1.0.0 - 2026-09-25

首次公开发布。改名为 Doc-image-deck，中文名「文图方案」（skill 名 `doc-image-deck`），并加入四项规则。

- 标点整理：`scripts/punct.py`，`deck whiteboard` 生成白板稿前自动执行，也可单独运行 `deck punct`。标题和短句去掉句号；详细描述（单句不少于 40 字，说明类文字不少于 30 字）和多句段落保留；列表结尾的「；」一并处理。阈值和保留清单可在 `project.json` 的 `punct` 中设置，改动逐条记入 `00_白板稿/标点整理.md`
- 白板稿确认：`deck approve` 记录使用者已确认白板稿（上屏文字摘要写入 `project.json`），`deck prompts` 核对后才生成提示词；确认后改字须重新确认
- 视觉参考：`deck refs` 在项目目录、上级目录和原文档目录查找图片、PDF、PPTX、Keynote，生成候选清单和编号缩略图，在确认点 1 连同白板稿一起询问使用者；`deck refs --export` 把选定的参考导出为图片
- 三个完全不同的方向：`direction.json` 新增 `source`、`refs`、`imagery_mode`、`dims`；`deck directions` 检查五项维度和配图方式两两不同，生成 `方向说明.md`；按参考建立的方向在样张和全量生图时自动附参考图（每次最多 3 张）
- 提示词要求模型不得自行加句号；`deck textcheck` 新增 `PUNCT` 状态，标出多出句号的页
- 运行环境改到 `~/.local/share/doc-image-deck`，环境变量改为 `DOC_IMAGE_DECK_HOME`
- 仓库整理：README、前因后果、MIT 许可、不依赖运行环境的测试与 CI；示例中的客户材料换成通用示例

## 0.2.0 - 2026-09-25（未公开，名为 image-deck-pipeline）

- 从文档到可编辑版的完整流程：白板稿、3 个设计方向样张、全量生图与文字核对、图文版合成、可编辑还原、清理
- Claude Code 与 Codex 共用安装，`setup.sh` 安装运行环境

## 0.1.0 - 2026-09-24（未公开）

- 整页图片 PPTX / PDF 还原为可编辑 PPTX：三路 OCR 投票、字体与字重拟合、LaMa 去字、PowerPoint 排版标定、逐页比对
