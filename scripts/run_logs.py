#!/usr/bin/env python
"""前台日志模式运行器：启动 Blender + MCP Server，日志实时滚动输出，Ctrl+C 统一关闭。

特性：
- 所有子进程输出同时写入 logs/*.log 并实时打印到终端（tail 效果）
- 启动时清空旧日志，每次都是干净会话
- Ctrl+C / SIGTERM 优雅终止所有子进程（terminate → 超时则 kill）

用法：
    python scripts/run_logs.py                # 默认文件
    python scripts/run_logs.py /path/to.blend # 指定文件
"""

import os
import signal
import subprocess
import sys
import threading
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(ROOT, "logs")

BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"
BLEND_FILE = sys.argv[1] if len(sys.argv) > 1 else "/Users/hezenghui/Public/blender/cli_test.blend"
ADDON = os.path.join(ROOT, "blender_addon", "subhuti_blender_mcp.py")
VENV_PY = os.path.join(ROOT, ".venv", "bin", "python")

PORT = 9876
HTTP_PORT = 8100

procs: list[subprocess.Popen] = []


def cleanup(signum=None, frame=None):  # noqa: ARG001
    print("\n==> 收到退出信号，关闭所有进程...")
    for p in procs:
        if p.poll() is None:
            p.terminate()
    for p in procs:
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
    print("==> 已全部关闭 ✅")
    sys.exit(0)


def tail_log(path: str) -> None:
    """把日志文件的新增内容实时打印到终端。"""
    with open(path) as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if line:
                print(f"[{os.path.basename(path)}] {line}", end="")
            else:
                time.sleep(0.2)


def main() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    # 清空旧日志，开始干净会话
    blender_log = open(os.path.join(LOG_DIR, "blender.log"), "w")  # noqa: SIM115
    mcp_log = open(os.path.join(LOG_DIR, "mcp.log"), "w")  # noqa: SIM115

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    print(f"==> 启动 Blender (无头): {BLEND_FILE}")
    procs.append(
        subprocess.Popen(
            [BLENDER, "-b", BLEND_FILE, "--python", ADDON],
            stdout=blender_log,
            stderr=subprocess.STDOUT,
        )
    )

    # 等待桥就绪（最多 30 秒）
    for _ in range(30):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=1) as resp:  # noqa: S310
                print(f"==> Blender 桥就绪: {resp.read().decode()}")
                break
        except Exception:  # noqa: BLE001
            time.sleep(1)
    else:
        print("==> ⚠️ Blender 桥未就绪，请查看日志")

    print(f"==> 启动 MCP Server (HTTP 调试模式 :{HTTP_PORT})")
    env = dict(os.environ, BLENDER_MCP_TRANSPORT="http", BLENDER_MCP_HTTP_PORT=str(HTTP_PORT))
    procs.append(
        subprocess.Popen(
            [VENV_PY, "-m", "subhuti_blender_mcp"],
            stdout=mcp_log,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=ROOT,
        )
    )

    threading.Thread(target=tail_log, args=(os.path.join(LOG_DIR, "blender.log"),), daemon=True).start()
    threading.Thread(target=tail_log, args=(os.path.join(LOG_DIR, "mcp.log"),), daemon=True).start()

    print("==> 全部就绪 ✅ 日志实时输出中，Ctrl+C 退出\n")

    try:
        while True:
            time.sleep(0.5)
            if any(p.poll() is not None for p in procs):
                print("==> 有进程退出，结束整个会话")
                cleanup()
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
