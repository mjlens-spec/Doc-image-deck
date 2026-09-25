# Changelog

## 1.2.1 - 2026-09-25

第二次 15 页端到端测试（扁平杂志编辑风、信息密度提高约一半）中修正的三个问题。

- 封面、封底不加页码时，提示词不再要求页码角留空，`deck textcheck` 也不再检查这个角（新增 `deckenv.page_number_on`）
- `deck textcheck`：上下两行叠在同一栏的文字（时间轴上阶段名在上、日期在下）也能匹配，不再误报 MISS
- 可编辑还原：生图标题字形比思源黑体窄时，原来靠 15%–20% 的负字距对齐宽度，相邻字会叠在一起；现在负字距不超过字号的 6%，其余改为缩小字号（`layers.py` 的 `cap_tracking`）

## 1.2.0 - 2026-09-25

逐页视觉规划、定方向前的品牌 VI 与 Logo 调研、Claude Code 与 Codex 的安装说明，以及一次 15 页端到端测试中修正的问题。

- 品牌调研：新增 `scripts/brand.py`（`deck brand <项目> init|check`）。定设计方向之前读客户提供的品牌材料（`01_设计方向/品牌材料/` 或 `project.json` 的 `brand_materials`），联网检索品牌官网、旗舰店和官方账号，填写 `01_设计方向/品牌调研.md` 六节：资料来源、品牌色（色值）、Logo、字体与版式、视觉风格与禁忌、对三个方向的约束。`deck directions` 在调研未完成时拒绝通过；`direction.json` 新增必填的 `brand_fit`，写进方向说明的「品牌呼应」一行。确认点 1 同时向用户索取品牌材料与 Logo
- Logo：新增 `scripts/logo.py`（`deck logo`）。去掉不透明图片的白底或黑底；只有反白版或只有深色版时自动生成另一版，彩色部分保留；多个 Logo 按面积平衡拼成联合 Logo；输出浅底、深底两版和预览图，写入 `project.json`
- 安装说明：新增 `docs/install-claude.md`、`docs/install-codex.md`，分别写明前提、安装、验证、启动方式、更新、卸载和给 agent 的逐条安装步骤；README 的安装一节改为两个客户端的摘要
- 逐页视觉规划：`outline.json` 每页新增 `visual`：`message`（这一页要说清什么）、`structure`（信息结构，14 种）、`form`（具体画法）、`focal`（视觉焦点）、`skeleton`（构图骨架，10 种）、`motif`（配图母题）；正文块可加 `visual`，把文字绑定到图中的某个部分
- 新增 `scripts/visual.py`（`deck visual`）：检查每页规划齐全、相邻两页骨架不同、同一骨架不超过内容页的四分之一、「并列要点」不超过五分之一，以及 `project.json` 的 `max_pages`、`section_pages`；生成 `00_白板稿/视觉规划.md`。`deck whiteboard` 生成后自动检查，`deck prompts` 在未通过时拒绝运行
- 提示词：新增全稿统一与逐页变化的说明、本页视觉规划、前后两页的骨架对照和图示规则（箭头、分组、比例都要对应文字里的关系）；正文块带 `visual` 时文字分组列出
- 图示规则要求图上只写引号里的文字，不加自行算出的数字和标签；有脚注且底部有预留角落时，要求脚注放在角落上方
- 风格参考图的说明改为不照搬参考图的构图、图示类型和配图题材
- 样张的内容页改选以图示为主的一页；联系表检查增加对照视觉规划一项
- `deck textcheck`：在同一栏里折成 3–4 行的文字（窄图示节点、卡片里常见）也能匹配，不再误报 MISS
- `project.json` 的 Logo 路径可以写相对项目目录的路径（此前按当前目录解析，从别处运行会找不到文件）
- `deck refs` 候选对照图：过高的缩略图只保留顶部 4:3，单张长图不再撑高整行
- references：可编辑还原补充排除区要完整包住 OCR 行框、大号数字配小号单位的 KPI 组切不开时留在底图；生图补充脚注落进 Logo 角、画法说明里的词被画成标签的处理办法
- 测试：新增视觉规划、提示词拼装、文字核对多行匹配、品牌调研、Logo 生成的单元测试（共 43 项）

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
