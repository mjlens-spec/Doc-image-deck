# 在 Codex（ChatGPT）中安装文图方案（Doc-image-deck）

> **For agents:** Install for Codex by running the steps in「给 agent 的安装步骤」in order. Each step gives the exact command and the expected result; if a result differs, stop and show the output to the user. Never sign in to an account or type a password for the user: `codex login` and installing PowerPoint are the user's own steps. The first install downloads about 1.3 GB and needs network access; if the sandbox blocks it, ask the user to approve or to rerun Codex with full access.

## 适用范围

- 客户端：Codex CLI（终端），用 ChatGPT 账号登录。「在 ChatGPT 里用」指的就是 Codex；ChatGPT 网页版和桌面版的对话窗口不能运行本地脚本，装不了本 skill。Codex 从 `~/.codex/skills/` 读取 skill；Codex IDE 插件和 Codex 桌面应用只要使用同一个 `~/.codex` 目录，同样适用。
- 系统：macOS（Apple 芯片或 Intel）、Windows 10 22H2 / Windows 11。
- 生图走 Codex 内置的 `image_gen`，用 ChatGPT 套餐额度，不需要 `OPENAI_API_KEY`。脚本会先确认 Codex 用 ChatGPT 账号登录，否则停止，避免产生 API 费用。

## 前提

| 需要 | 用途 | 检查 |
|---|---|---|
| Codex CLI，用 ChatGPT 账号登录 | 运行 skill、整页生图 | `codex login status` 显示 `Logged in using ChatGPT` |
| Microsoft PowerPoint | 导出 PDF、比对、可编辑版排版标定 | 能打开 PowerPoint |
| Python 3.10 及以上 | 运行全部脚本 | macOS `python3 --version`；Windows `py -3 --version` |
| git | 下载 skill | `git --version` |
| macOS：Xcode 命令行工具 | 编译文字识别工具 | `xcode-select -p` 有输出 |

Codex CLI 的安装：macOS 用 `brew install codex` 或 `npm i -g @openai/codex`；Windows 先 `winget install OpenJS.NodeJS.LTS`，再 `npm i -g @openai/codex`。然后运行 `codex login`，在浏览器里用 ChatGPT 账号登录。

## 安装

macOS：

```bash
git clone https://github.com/mjlens-spec/Doc-image-deck.git ~/Doc-image-deck
python3 ~/Doc-image-deck/scripts/install.py
```

Windows（PowerShell）：

```powershell
git clone https://github.com/mjlens-spec/Doc-image-deck.git $HOME\Doc-image-deck
py -3 $HOME\Doc-image-deck\scripts\install.py
```

`install.py` 把 skill 复制到 `~/.agents/skills/doc-image-deck/`，在 `~/.codex/skills/` 和 `~/.claude/skills/` 各建一个链接指向它，再安装运行环境（Python 依赖约 1 GB、LaMa 权重 196 MB、思源字体、humanizer-zh、PowerPoint 排版标定），首次 10–20 分钟。

## 验证

macOS：

```bash
~/.codex/skills/doc-image-deck/scripts/deck check
```

Windows（PowerShell）：

```powershell
& "$HOME\.codex\skills\doc-image-deck\scripts\deck.cmd" check
```

每一项都是 ✓，最后一行是「环境就绪。」即安装完成。

## 启动方式与设置

推荐这样启动 Codex：

```bash
codex --search
```

- `--search` 打开联网检索（`web_search`）。设计方向之前的品牌 VI 与 Logo 调研需要它；不开时只能用客户提供的材料。
- 权限：`deck gen` 会再启动一个 `codex exec`，需要联网；`deck compose`、`deck editable`、`deck pdf` 要驱动 PowerPoint（macOS 走 AppleScript，Windows 走 COM）。默认沙盒不允许这两类操作，运行时按提示批准。不想逐条批准，可以用 `codex --search -s danger-full-access` 启动；这个模式下 Codex 执行命令不受沙盒限制，由你决定是否使用。
- 推理强度：在 `~/.codex/config.toml` 里设 `model_reasoning_effort = "high"`。批量生图的子调用由脚本固定为低推理强度，不受影响。

## 开始使用

新开一个 Codex 会话（已经打开的会话不会加载新装的 skill），然后：

- 在提示里写 `$doc-image-deck`，或者直接说「用文图方案把这份文档做成提案」「先出白板稿再生图」「把这份图片版 PPT 转回可编辑」。
- agent 会在两个确认点停下来等你：确认白板稿（同时索取视觉参考、品牌材料和 Logo），以及从三个设计方向里选一个。

## 更新

```bash
cd ~/Doc-image-deck && git pull && python3 scripts/install.py --no-setup
```

`--no-setup` 只同步 skill 文件。版本说明里提到运行环境有变化时，去掉这个参数重新运行，或运行 `deck setup`。从 1.x 升到 2.0.0 运行环境没有变化，`--no-setup` 即可；进行中的 1.x 项目要在 `outline.json` 里补 `storyline.thesis` 和各页 `chapter`（原文是 Markdown 或 .docx 时还要补 `source`），见 CHANGELOG。

## 卸载

```bash
rm -rf ~/.codex/skills/doc-image-deck ~/.claude/skills/doc-image-deck ~/.agents/skills/doc-image-deck
rm -rf ~/.local/share/doc-image-deck
```

Windows 上运行环境在 `%LOCALAPPDATA%\doc-image-deck`。

## 给 agent 的安装步骤

1. **确认平台和前提。** 运行 `python3 --version`（Windows：`py -3 --version`）、`git --version`、`codex login status`。预期：Python 3.10 及以上；git 有版本号；Codex 显示 `Logged in using ChatGPT`。显示用 API Key 登录时，告诉用户生图会改走 API 计费，请用户改用 `codex login` 登录 ChatGPT 账号，然后停下等待。没有 PowerPoint 时请用户自己安装。
2. **确认权限。** 安装要联网下载约 1.3 GB，并写入 `~/.agents`、`~/.codex/skills`、`~/.claude/skills` 和运行环境目录。当前沙盒不允许时，请用户批准，或以 `codex -s danger-full-access` 重新启动后再装。
3. **下载。** `~/Doc-image-deck` 不存在时运行 `git clone https://github.com/mjlens-spec/Doc-image-deck.git ~/Doc-image-deck`；已存在时运行 `git -C ~/Doc-image-deck pull`。
4. **安装。** 运行 `python3 ~/Doc-image-deck/scripts/install.py`（Windows：`py -3 $HOME\Doc-image-deck\scripts\install.py`）。首次 10–20 分钟，超时上限设为 30 分钟。预期输出里有两行「已链接：…」，最后是 setup 的检查结果。
5. **验证。** 运行 `~/.codex/skills/doc-image-deck/scripts/deck check`（Windows 见「验证」一节）。预期最后一行是「环境就绪。」。仍有 ✗ 时运行 `deck setup` 一次；还不通过，就把 ✗ 行原样告诉用户。
6. **告诉用户。** 请用户用 `codex --search` 新开一个会话后使用，触发方式见「开始使用」。
