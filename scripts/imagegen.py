#!/usr/bin/env python3
"""通过 Codex CLI 内置 image_gen 生成或修改图片，使用 ChatGPT 订阅额度，不调用 API。

用法：
  imagegen.py "<提示词>" -o <输出.png> [--ref 图片 ...] [--size 16:9|1536x1024] [--effort low] [--timeout 600]

成功时向 stdout 逐行输出保存后的绝对路径，退出码 0。
退出码：1 参数或前置检查失败 | 2 未生成图片 | 124 超时。
"""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys

CODEX_HOME = pathlib.Path(os.environ.get("CODEX_HOME", pathlib.Path.home() / ".codex"))


def die(msg, code=1):
    print(f"imagegen: {msg}", file=sys.stderr)
    sys.exit(code)


def build_instruction(prompt, size, has_refs):
    lines = [
        "Call the built-in image_gen tool exactly once.",
        "Use the image description below as the prompt verbatim; do not rewrite, expand or translate it.",
        "Do not run shell commands, read files, load skills or ask questions.",
        "After the tool returns, reply with the single word DONE.",
    ]
    if has_refs:
        lines.append(
            "The attached images are inputs. The description states which image is the edit target "
            "and which are references; preserve everything the description does not ask to change."
        )
    if size:
        lines.append(f"Output size / aspect ratio: {size}.")
    return "\n".join(lines) + "\n\nImage description:\n" + prompt


def next_free(path: pathlib.Path) -> pathlib.Path:
    if not path.exists():
        return path
    i = 2
    while True:
        cand = path.with_name(f"{path.stem}-{i}{path.suffix}")
        if not cand.exists():
            return cand
        i += 1


def main():
    ap = argparse.ArgumentParser(description="Generate or edit an image via Codex built-in image_gen.")
    ap.add_argument("prompt", help="图片描述；传 - 则从 stdin 读取")
    ap.add_argument("-o", "--out", required=True, help="输出路径（PNG）")
    ap.add_argument("--ref", action="append", default=[], help="输入图片，可重复，最多 4 张")
    ap.add_argument("--size", help="尺寸或比例，如 16:9、1536x1024")
    ap.add_argument("--effort", default="low", help="Codex 推理强度，默认 low")
    ap.add_argument("--timeout", type=int, default=600, help="超时秒数，默认 600")
    ap.add_argument("--overwrite", action="store_true", help="覆盖已存在的输出文件")
    a = ap.parse_args()

    prompt = sys.stdin.read() if a.prompt == "-" else a.prompt
    if not prompt.strip():
        die("提示词为空")
    if len(a.ref) > 4:
        die("--ref 最多 4 张")
    refs = [pathlib.Path(r).expanduser().resolve() for r in a.ref]
    for r in refs:
        if not r.is_file():
            die(f"找不到输入图片：{r}")

    out = pathlib.Path(a.out).expanduser().resolve()
    if out.suffix.lower() != ".png":
        out = out.with_suffix(".png")
        print(f"imagegen: 输出统一为 PNG，改存为 {out.name}", file=sys.stderr)
    out.parent.mkdir(parents=True, exist_ok=True)

    if not shutil.which("codex"):
        die("未找到 codex 命令")
    # 只允许 ChatGPT 登录，避免误走 API 计费
    env = {k: v for k, v in os.environ.items() if k not in ("OPENAI_API_KEY", "OPENAI_BASE_URL")}
    status = subprocess.run(["codex", "login", "status"], capture_output=True, text=True, env=env)
    if "ChatGPT" not in status.stdout + status.stderr:
        die("Codex 未以 ChatGPT 账号登录，已停止以免产生 API 费用。请先运行 codex login")

    cmd = [
        "codex", "exec", "--json",
        "-s", "read-only",
        "--skip-git-repo-check",
        # 不加载 config.toml 里的 MCP、hooks 等，缩短启动时间、减少上下文；登录仍用 CODEX_HOME
        "--ignore-user-config",
        "-C", str(out.parent),
        "-c", f'model_reasoning_effort="{a.effort}"',
    ]
    for r in refs:
        cmd += ["-i", str(r)]
    # -i 是变长参数，必须用 -- 隔开提示词
    cmd += ["--", build_instruction(prompt, a.size, bool(refs))]

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, env=env,
            stdin=subprocess.DEVNULL, timeout=a.timeout,
        )
    except subprocess.TimeoutExpired:
        die(f"{a.timeout} 秒内未完成，可调大 --timeout", 124)

    thread_id, messages = None, []
    for line in proc.stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        thread_id = thread_id or ev.get("thread_id")
        item = ev.get("item") or {}
        if item.get("type") == "agent_message":
            messages.append(item.get("text", "").strip())
    if not thread_id:
        die("未拿到 Codex 会话 ID：\n" + "\n".join(proc.stderr.splitlines()[-20:]), 2)

    # --json 事件流不含生图记录；按会话 ID 读会话日志，只取本次会话的图，不跨会话按时间猜
    saved, failures = [], []
    for rollout in CODEX_HOME.glob(f"sessions/*/*/*/rollout-*{thread_id}.jsonl"):
        for line in rollout.open(errors="ignore"):
            if "image_gen" not in line:
                continue
            try:
                item = json.loads(line).get("payload", {}).get("item", {})
            except ValueError:
                continue
            if not str(item.get("kind", "")).startswith("image_gen"):
                continue
            if item.get("status") == "completed" and item.get("savedPath"):
                saved.append(pathlib.Path(item["savedPath"]))
            elif item.get("failure"):
                failures.append(str(item["failure"]))
    if not saved:
        saved = sorted((CODEX_HOME / "generated_images" / thread_id).glob("*.png"))
    saved = [p for p in dict.fromkeys(saved) if p.is_file()]

    if not saved:
        for f in failures:
            print(f"imagegen: 生成失败：{f}", file=sys.stderr)
        for m in messages:
            print(f"imagegen: Codex 回复：{m}", file=sys.stderr)
        print(f"imagegen: 未生成图片（codex 退出码 {proc.returncode}，会话 {thread_id}）", file=sys.stderr)
        sys.exit(2)

    for i, src in enumerate(saved):
        dst = out if i == 0 else out.with_name(f"{out.stem}-{i + 1}{out.suffix}")
        if not a.overwrite:
            dst = next_free(dst)
        shutil.copyfile(src, dst)
        print(dst)


if __name__ == "__main__":
    main()
