# Changelog

## 2.0.1 - 2026-09-26

2.0.0 发布后跑完的全流程测试（一份内部方法文档，演讲稿，12 页正文 + 1 页附录）和新旧提示词对比中修正的问题。

- 可编辑还原：`deck editable` 在图文版改过之后重跑时，沿用了上一次抽出的页面图，重生成的页按旧图还原；现在按图文版的大小和修改时间判断，图文版有变化或页面图已被清理时重新抽页
- 可编辑还原：一行同时完整匹配两条白板稿文字时，选整条匹配的那一条，不再从较长的标题里带出逗号（「单一对象」被还原成「单一对象，」）；4–5 个字的短行少识别一个字时（Vision 漏读「的」）按白板稿补回，不再拉大字距填满原宽度
- 可编辑还原：大字去字后 LaMa 偶尔在中间填出一块灰色；外圈是单一底色时，偏离底色较远的像素改为底色，浅网格和纸纹保留
- 可编辑还原：按字高切分大小字混排时，切口落在拉丁字母与汉字交界处不再切开（小写字母比汉字矮不是字号变化），修正「Agent 负责…」被切成两段、字母被拉开
- `deck textcheck`：`DRIFT` 不再比较 `hero` 页（标题有意放大）和 `asym` 页；`NEAR` 的字串也记录位置
- `deck fix`：新增 `--near`（长句里只错一个字时核对结果是 NEAR）和 `--only`（只改含指定文字的那一句）；修正羽化半径参数类型错误
- 提示词：折行时行首不放中文标点（审图发现圆形节点里逗号落在行首）
- references：标题位置全稿固定，版面建议不把标题挪进侧栏（审图判为不一致的两页都是侧栏标题）
- 测试结果写进 README「实测」和 `docs/前因后果.md`；`--skeleton-refs` 在这次对比中没有看出差别，仍为可选项
- 回归：用新的可编辑还原重跑 1.2.1 的 15 页稿，结果见 `docs/前因后果.md`


## 2.0.0 - 2026-09-26

大工作流（五个阶段、两个确认点）不变，细化各环节内部：分页先定故事线、按用途和构图骨架控制字量，三个设计方向连封面构图也各不相同，生图质检增加多出文字与风格漂移检查、局部改字和子 agent 审图，可编辑还原自动处理大数字与单位。依据是对 1.2.x 两次 15 页测试的复盘和对同类开源项目的调研。

分页与大纲（阶段 1）

- 故事线：新增 `scripts/storyline.py`（`deck storyline`）。写正文之前先写 `storyline`（全稿结论、论证方式、不上屏的原文及理由）和每页的 `chapter`、`title`、`source`（原文出处）；检查章节连续、3–7 章、每个出处都能在原文（Markdown、.docx）里找到、原文一二级标题都有对应的页、封底不是「谢谢」页、标题不描述稿子本身、目录与执行摘要对应章节、同一指标跨页数值一致；生成 `00_白板稿/故事线.md`（标题串读、原文来源、原文覆盖），确认点 1 放在第一项。`deck whiteboard`、`deck prompts` 在故事线未通过时拒绝运行
- 读法：`project.json` 新增 `deck_mode`（`read` 阅读稿，默认；`present` 演讲稿）和 `duration_min`。演讲稿按时长检查页数，连续高密度页不超过 3 页，8 页以上至少一页低密度页
- 每页容量：字量改为按构图骨架和读法分别设上限（正文汉字与上屏文字条数），由 `deck visual` 检查；标题不超过 30 字。阅读稿的数值按 1.2.1 测试实测值定，全稿统一的「约 150 字」不再使用
- 新页型：`agenda` 目录、`summary` 执行摘要、`appendix` 附录（放在封底之后，页码 A1、A2，不计入 `max_pages`，按阅读稿容量检查）

设计方向（阶段 2）

- `direction.json` 新增 `cover`（这个方向自己的封面构图和主体，替代大纲封面页的版面建议和画法）、`axes`（字体、版式语法、质感、图示语言、配色策略各选一个固定值）、`dims.diagram`（图示语言）、`temperature`（是否接近「行业常见款」）、`icons`（图标策略，默认不画）、`allow`（放开默认禁画项）。`deck directions` 检查封面构图、`axes` 两两不同，配色策略至少两种，三个方向不全是行业常见款；`--samples` 对样张做文字核对并写进方向说明
- 品牌调研第六节要写「行业常见款」
- 提示词：默认禁画塑胶三维物体、玻璃拟态、发光线条、白底青蓝渐变、悬浮投影卡片、标题下装饰短线、非文案的编号徽章、代表 AI 的机器人形象；按方向写图标规则；图片里的纸张、便签、屏幕不出现可读文字；没有配图建议时写「不用照片、不画图标」

生图与质检（阶段 2）

- `deck textcheck` 新增 `EXTRA`（图上有文案以外的文字：画成标签的画法说明、自行算出的百分比、英文装饰词）和 `DRIFT`（标题位置或笔画字高与同明暗其他页不一致）；只核对部分页时保留其他页的结果；缺字时记录错字位置
- 新增 `scripts/fix.py`（`deck fix`）：只错一两处字时，把该页交给 `image_gen` 改字，只取错字区域贴回原图，改完自动重新核对，没有改善就恢复原版本
- 新增 `scripts/slidereview.py`（`deck audit init|check`）：生成审图清单交给新开的子 agent 逐页对照视觉规划看图，同一问题出现在 3 页以上时列为全稿问题
- `deck gen --skeleton-refs`：用了两页以上的构图骨架先各生成一页，其余同骨架的页以它为参考；`deck prompts --corner-guide` 可另附预留角落的定位图

可编辑还原（阶段 4）

- 白板稿 `kpis` 块里带中文前缀或单位的大数字（「约 250 条」「310 万元」）自动切成前缀、数字、单位三段，各按自己的字号还原；用 1.2.1 测试稿回归，此前手工留在底图的 4 组中 3 组变为可编辑
- 高于页高 18% 且以数字为主的超大数字留在底图（去字会留下光晕），交付统计里列为「超大数字」
- 粗笔画大字的背景色估计：行框外一圈是单一颜色、框内估计偏离时改用外圈颜色，修正大数字取色成底色的问题
- 窄字形标题先向右侧空白延伸（最多 10%），仍不够再缩字号；只用于标题级的行

其他

- 故事线相关的记录写进白板稿备注和 `outline.md`；交付检查模板增加故事线、EXTRA / DRIFT 与审图汇总
- 测试：新增故事线、容量与节奏、附录页码、提示词、骨架参考规划、EXTRA / DRIFT / 错字定位、审图的单元测试，共 63 项；冒烟测试的大纲补上故事线字段
- 升级：运行环境没有变化，已安装 1.x 的机器运行 `git pull` 后 `python3 scripts/install.py --no-setup` 即可。进行中的 1.x 项目需要在 `outline.json` 里补 `storyline.thesis` 和各页 `chapter`（原文可读时还要补 `source`），否则 `deck whiteboard` 和 `deck prompts` 会拒绝运行

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
