# 文图方案（Doc-image-deck）安装：交给 Codex 执行

用法：把这份文档发给 Codex，说「按这份文档安装」。

## 适配环境

| 项目 | 要求 |
|---|---|
| 系统 | macOS（Apple 芯片或 Intel）；Windows 10 22H2 / Windows 11 |
| 必须由人完成 | 安装 Microsoft PowerPoint；Codex 用 ChatGPT 账号登录（`codex login`），生图用 ChatGPT 套餐额度 |
| 由 Codex 安装 | Python 3.10+、git、Xcode 命令行工具（macOS）；安装脚本再装 Python 依赖（约 1 GB）、去字模型、思源字体、humanizer-zh，并做一次 PowerPoint 排版标定 |
| 网络与磁盘 | 能访问 GitHub 和 PyPI（大陆网络可能要代理）；约 1.5 GB |
| 权限 | 要联网并写入用户目录：用 `codex --search -s danger-full-access` 启动，或在提示时逐条批准 |

## 给 Codex 的步骤

按顺序执行。某一步结果与预期不符就停下，把输出原样给用户看。不替用户登录账号、不输入密码。

1. **确认登录**：运行 `codex login status`，输出要含 `ChatGPT`。显示 API Key 登录或未登录时，请用户运行 `codex login` 用 ChatGPT 账号登录，然后停下。
2. **补齐基础工具**
   - macOS：`xcode-select -p` 没有输出时运行 `xcode-select --install`，请用户在弹窗里点「安装」，装完再继续（git 和 swiftc 随之装上）。`python3 --version` 低于 3.10 时：有 Homebrew 就运行 `brew install python`，之后用 `$(brew --prefix)/bin/python3` 代替 `python3`；没有 Homebrew 时请用户从 https://www.python.org/downloads/ 安装 3.12。
   - Windows（PowerShell）：`py -3 --version` 失败或低于 3.10 时运行 `winget install -e --id Python.Python.3.12`；`git --version` 失败时运行 `winget install -e --id Git.Git`。装完新开一个 PowerShell 窗口再继续。
3. **下载**：`~/Doc-image-deck` 不存在时运行 `git clone https://github.com/mjlens-spec/Doc-image-deck.git ~/Doc-image-deck`；已存在时运行 `git -C ~/Doc-image-deck pull`。Windows 把路径写成 `$HOME\Doc-image-deck`。
4. **安装**：macOS 运行 `python3 ~/Doc-image-deck/scripts/install.py`；Windows 运行 `py -3 $HOME\Doc-image-deck\scripts\install.py`。超时设为 30 分钟。
   - 中途会打开 PowerPoint 约 1 分钟做排版标定；macOS 弹出「允许控制 Microsoft PowerPoint」时请用户点允许。
   - 报「缺 Microsoft PowerPoint」：请用户安装 PowerPoint 后重跑这一步。
   - pip 下载很慢或失败：设置环境变量 `PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple` 后重跑这一步。
5. **验证**：macOS 运行 `~/.codex/skills/doc-image-deck/scripts/deck check`；Windows 运行 `& "$HOME\.codex\skills\doc-image-deck\scripts\deck.cmd" check`。最后一行应为「环境就绪。」。有 ✗ 时把 `check` 换成 `setup` 运行一次，再 `check`；仍有 ✗ 就把这些行告诉用户。
6. **告诉用户**：用 `codex --search` 新开一个会话（已打开的会话不会加载新装的 skill），提示里写 `$doc-image-deck`，或直接说「用文图方案把这份文档做成提案」。

## 更新

macOS：`cd ~/Doc-image-deck && git pull && python3 scripts/install.py --no-setup`
Windows：`cd $HOME\Doc-image-deck; git pull; py -3 scripts\install.py --no-setup`
