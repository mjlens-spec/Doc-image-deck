# Doc-image-deck · 仓库维护说明

本仓库开发文图方案（Doc-image-deck）skill。Claude Code 与 Codex 的运行时入口都是根目录 `SKILL.md`；本文件只约束仓库维护。

## 工作规则

- 改运行规程时改 `SKILL.md` 和它引用的 `references/`；改脚本在 `scripts/`。改完运行 `zsh scripts/install.sh --no-setup` 同步到本机安装位置。
- `private/` 放客户测试项目和含客户名称的内部记录，已被 `.gitignore` 排除，不要加入版本库。公开文件里的示例一律用通用示例，不写客户名称、客户数据和客户 Logo。
- 提交前运行 `python3 tests/run_tests.py`（只用标准库，不需要运行环境）。
- 改动流程或命令时同步更新 `README.md`、`CHANGELOG.md`，以及 `docs/前因后果.md` 里的对应记录。
