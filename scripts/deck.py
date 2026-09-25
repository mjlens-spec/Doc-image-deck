# -*- coding: utf-8 -*-
"""Doc-image-deck（文图方案）command entry, identical on macOS and Windows.

    macOS:   scripts/deck <command> [args]
    Windows: scripts\\deck.cmd <command> [args]
Both launchers call this file. check / setup / imagegen run with any Python 3.10+; every other command runs with the
runtime's Python (created by setup.py) in UTF-8 mode.
"""
import os, sys, subprocess

S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, S)
import hostos

COMMANDS = {
    'humanize': 'humanize.py', 'whiteboard': 'whiteboard.py', 'punct': 'punct.py', 'refs': 'refs.py',
    'approve': 'approve.py', 'directions': 'directions.py', 'prompts': 'build_prompts.py', 'gen': 'gen_batch.py',
    'textcheck': 'textcheck.py', 'sheet': 'contact_sheet.py', 'compose': 'compose.py', 'pdf': 'editable/pptrender.py',
    'editable': 'editable/run_editable.py', 'layers': 'editable/run_pages.py', 'build': 'editable/build_pptx.py',
    'verify': 'editable/verify.py', 'review': 'editable/review_grid.py', 'proof': 'editable/proof_sheet.py',
    'zoom': 'editable/zoomcmp.py', 'qasheet': 'editable/qa_sheet.py', 'report': 'editable/report.py',
    'draftdiff': 'editable/draft_diff.py', 'cleanup': 'cleanup.py',
}
ANY_PYTHON = {'check': ('setup.py', ['--check']), 'setup': ('setup.py', []), 'imagegen': ('imagegen.py', [])}

HELP = '''deck check                                   检查运行环境
deck setup [--no-fonts] [--no-calib]         安装 / 修复运行环境
deck humanize <项目> export|import|accept|status   去 AI 味：文案交给 humanizer-zh 处理后写回
deck whiteboard <项目> [--no-punct]           阶段 1：标点整理 + outline.json → 白板稿 PPTX（须先去 AI 味）
deck punct <项目> [--check]                    标点整理：标题和短句去句号，详细描述保留
deck refs <项目> [目录 ...]                     找本地视觉参考候选（确认点 1 一并询问用户）
deck refs <项目> --export R03|文件 [--pages 1,4] --to <目录>   把选定参考导出为图片
deck approve <项目> [--note 意见] | --status    记录用户已确认白板稿（生图前必须）
deck directions <项目>                         检查三个方向是否完全不同，写方向说明.md
deck prompts <项目> --direction <方向.json> --out <目录> [--pages p01,p05]
deck gen <提示词目录> --out <生图目录> [--pages ..] [--ref-light 图] [--ref-dark 图] [--parallel 4]
deck textcheck <项目> <提示词目录> <生图目录>     生图文字、预留角落与多出句号核对
deck sheet <输出.jpg> 标签=图 ... | deck sheet <输出前缀> --raw <生图目录>
deck compose <项目>                           阶段 3：图文版 PPTX + PDF
deck editable <工作目录> <图文版.pptx> <输出.pptx> [--outline outline.json] [--ref 图文版.pdf]
deck layers|build|verify|review|proof|zoom|qasheet|report|draftdiff ...   阶段 4 分步命令
deck pdf <deck.pptx> [out.pdf]                用 PowerPoint 导出 PDF
deck cleanup <项目> [--dry-run] [--deep]       阶段 5：清理中间文件
deck imagegen "<提示词>" -o out.png [--ref 图] 单张生图（Codex 内置 image_gen）'''


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else 'help'
    rest = args[1:]
    env = hostos.child_env()
    if cmd in ANY_PYTHON:
        script, extra = ANY_PYTHON[cmd]
        py = sys.executable
    elif cmd in COMMANDS:
        script, extra = COMMANDS[cmd], []
        py = hostos.VENV_PY
        if not os.path.exists(py):
            raise SystemExit('运行环境未安装：请先运行 deck setup（%s）' % hostos.RUNTIME)
    else:
        print(HELP)
        return 0
    r = subprocess.run([py, '-X', 'utf8', os.path.join(S, script)] + extra + rest, env=env)
    return r.returncode


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
