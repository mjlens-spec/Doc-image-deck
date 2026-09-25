# Doc-image-deck · 仓库维护说明

本仓库开发文图方案（Doc-image-deck）skill。Claude Code 与 Codex 的运行时入口都是根目录 `SKILL.md`；本文件只约束仓库维护。

## 工作规则

- 改运行规程时改 `SKILL.md` 和它引用的 `references/`；改脚本在 `scripts/`。改完运行 `python3 scripts/install.py --no-setup`（Windows：`py -3 scripts\install.py --no-setup`）同步到本机安装位置。
- `private/` 放客户测试项目和含客户名称的内部记录，已被 `.gitignore` 排除，不要加入版本库。公开文件里的示例一律用通用示例，不写客户名称、客户数据和客户 Logo。
- 提交前运行 `python3 tests/run_tests.py`（只用标准库，不需要运行环境）；改动识别、PDF、字体、可编辑还原相关代码时，再用运行环境的 Python 跑 `tests/pipeline_smoke.py`，Mac 上加 `DOC_IMAGE_DECK_OCR=rapid DOC_IMAGE_DECK_PDF=pdfium` 覆盖 Windows 路径。
- 平台差异只写在 `scripts/hostos.py`（以及 `editable/pptrender.py` 的 PowerPoint 驱动），其他脚本通过它调用。
- 改动流程或命令时同步更新 `README.md`、`CHANGELOG.md`，以及 `docs/前因后果.md` 里的对应记录；改动安装方式、前提或命令入口时同步更新 `docs/install-claude.md` 与 `docs/install-codex.md`。
