# 在 Claude Code 中安装文图方案（Doc-image-deck）

> **For agents:** Install for Claude Code by running the steps in「给 agent 的安装步骤」in order. Each step gives the exact command and the expected result; if a result differs, stop and show the output to the user. Never sign in to an account or type a password for the user: `codex login` and installing PowerPoint are the user's own steps.

## 适用范围

- 客户端：Claude Code 终端版、Claude Code IDE 插件、Claude 桌面应用的 Code 标签页。三者都从 `~/.claude/skills/` 读取 skill。
- 系统：macOS（Apple 芯片或 Intel）、Windows 10 22H2 / Windows 11。

## 前提

| 需要 | 用途 | 检查 |
|---|---|---|
| Microsoft PowerPoint | 导出 PDF、比对、可编辑版排版标定 | 能打开 PowerPoint |
| Python 3.10 及以上 | 运行全部脚本 | macOS `python3 --version`；Windows `py -3 --version` |
| git | 下载 skill | `git --version` |
| Codex CLI，用 ChatGPT 账号登录 | 生图。即使在 Claude Code 里使用，整页生图也走 Codex 内置的 `image_gen`，用 ChatGPT 套餐额度，不走 API | `codex login status` 显示 `Logged in using ChatGPT` |
| macOS：Xcode 命令行工具 | 编译文字识别工具 | `xcode-select -p` 有输出 |

Codex CLI 的安装：macOS 用 `brew install codex` 或 `npm i -g @openai/codex`；Windows 先 `winget install OpenJS.NodeJS.LTS`，再 `npm i -g @openai/codex`。装好后运行 `codex login`，在浏览器里用 ChatGPT 账号登录。

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

`install.py` 做三件事：

1. 把 skill 复制到 `~/.agents/skills/doc-image-deck/`。
2. 在 `~/.claude/skills/` 和 `~/.codex/skills/` 各建一个链接指向它。macOS 用符号链接，Windows 用目录联接，不需要管理员权限。
3. 运行 `setup.py` 安装运行环境：Python 依赖约 1 GB、LaMa 权重 196 MB、思源字体、humanizer-zh，并做一次 PowerPoint 排版标定。首次需要 10–20 分钟。

## 验证

macOS：

```bash
~/.claude/skills/doc-image-deck/scripts/deck check
```

Windows（PowerShell）：

```powershell
& "$HOME\.claude\skills\doc-image-deck\scripts\deck.cmd" check
```

每一项都是 ✓，最后一行是「环境就绪。」即安装完成。有 ✗ 时按提示运行 `deck setup`。

## 开始使用

新开一个 Claude Code 会话（已经打开的会话不会加载新装的 skill），然后：

- 输入 `/doc-image-deck`，或者直接说「用文图方案把这份文档做成提案」「把这份文档做成生图 PPT」「把这份图片版 PPT 转回可编辑」。
- agent 会在两个确认点停下来等你：确认白板稿（同时索取视觉参考、品牌材料和 Logo），以及从三个设计方向里选一个。
- 品牌调研用 Claude Code 自带的联网检索（WebSearch / WebFetch），不需要另外安装。

减少权限提示（可选）：Claude Code 每运行一条命令都会询问。可以在询问时选「始终允许」，或在 `~/.claude/settings.json` 的 `permissions.allow` 里加一条，把 `<用户目录>` 换成你的主目录的完整路径：

```json
"Bash(<用户目录>/.claude/skills/doc-image-deck/scripts/deck:*)"
```

## 更新

```bash
cd ~/Doc-image-deck && git pull && python3 scripts/install.py --no-setup
```

`--no-setup` 只同步 skill 文件。版本说明里提到运行环境有变化时，去掉这个参数重新运行，或运行 `deck setup`。

## 卸载

删除三处链接和副本，以及运行环境：

```bash
rm -rf ~/.claude/skills/doc-image-deck ~/.codex/skills/doc-image-deck ~/.agents/skills/doc-image-deck
rm -rf ~/.local/share/doc-image-deck
```

Windows 上运行环境在 `%LOCALAPPDATA%\doc-image-deck`。

## 给 agent 的安装步骤

1. **确认平台和前提。** 运行 `python3 --version`（Windows：`py -3 --version`）、`git --version`、`codex login status`。预期：Python 3.10 及以上；git 有版本号；Codex 显示 `Logged in using ChatGPT`。Codex 没装或没登录时，把「前提」一节的安装命令告诉用户，请用户自己完成 `codex login`，然后停下等待。没有 PowerPoint 时同样请用户自己安装。
2. **下载。** `~/Doc-image-deck` 不存在时运行 `git clone https://github.com/mjlens-spec/Doc-image-deck.git ~/Doc-image-deck`；已存在时运行 `git -C ~/Doc-image-deck pull`。
3. **安装。** 运行 `python3 ~/Doc-image-deck/scripts/install.py`（Windows：`py -3 $HOME\Doc-image-deck\scripts\install.py`）。首次 10–20 分钟，放到后台运行，超时上限设为 30 分钟。预期输出里有两行「已链接：…」，最后是 setup 的检查结果。
4. **验证。** 运行 `~/.claude/skills/doc-image-deck/scripts/deck check`（Windows 见「验证」一节）。预期最后一行是「环境就绪。」。仍有 ✗ 时运行 `deck setup` 一次；还不通过，就把 ✗ 行原样告诉用户。
5. **告诉用户。** 安装位置是 `~/.agents/skills/doc-image-deck/`，请用户新开一个 Claude Code 会话后使用，触发方式见「开始使用」。
