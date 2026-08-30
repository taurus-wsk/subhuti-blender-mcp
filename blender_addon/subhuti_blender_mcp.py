"""
Subhuti Blender MCP — Blender 侧插件（HTTP 桥）

作用：在本机启动一个 HTTP 服务，接收 MCP Server 转发的 Python 代码，
并把执行调度到 Blender 主线程（bpy 只能在主线程安全操作）。

- GUI 模式：通过 bpy.app.timers 在主线程轮询队列
- 无头模式（-b）：脚本主循环直接轮询队列

端点：
  GET  /health    → 连通性检查
  POST /rpc       → {"code": "..."} 在主线程 exec，返回 stdout/stderr

环境变量：
  BLENDER_MCP_HOST  默认 127.0.0.1
  BLENDER_MCP_PORT  默认 9876

用法：
  作为 Addon 安装（推荐）：复制本文件到
    ~/Library/Application Support/Blender/4.3/scripts/addons/
  然后在 Blender 偏好设置 → 插件 中启用，或命令行启用：
    Blender -b -y --python-expr "import addon_utils; addon_utils.enable('subhuti_blender_mcp', default_set=True, persistent=True); bpy.ops.wm.save_userpref()"
  无头模式直接运行：
    /Applications/Blender.app/Contents/MacOS/Blender -b file.blend --python 本文件
"""

bl_info = {
    "name": "Subhuti Blender MCP",
    "author": "861522196@qq.com",
    "version": (0, 0, 0),  # 占位符：make package 时由 pyproject.toml 自动注入
    "blender": (3, 6, 0),
    "location": "System",
    "description": "HTTP bridge for MCP: execute Python in Blender's main thread",
    "category": "System",
}

import bpy  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import queue  # noqa: E402
import shutil  # noqa: E402
import threading  # noqa: E402
import traceback  # noqa: E402
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # noqa: E402

HOST = os.environ.get("BLENDER_MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("BLENDER_MCP_PORT", "9876"))

# ---------------------------------------------------------------------------
# MCP Server 环境自检与自动安装
# 插件装上后自动确保"翻译官"也装好。优先级：
#   1. 全局命令已就绪且版本与本地源码一致 → 就绪
#   2. 插件 zip 附带的本地源码（mcp_server/）→ uv tool install 本地源码
#   3. 回退：SUBHUTI_MCP_PACKAGE（PyPI 包名等）
# ---------------------------------------------------------------------------
MCP_CMD = "subhuti-blender-mcp"
# 包来源回退：发布到 PyPI 后默认即包名；本地开发可设 SUBHUTI_MCP_PACKAGE 指向项目目录
MCP_PACKAGE = os.environ.get("SUBHUTI_MCP_PACKAGE", "subhuti-blender-mcp")
AUTO_SETUP = os.environ.get("SUBHUTI_MCP_AUTO_SETUP", "1") != "0"


def _find_mcp_cmd() -> str | None:
    """定位 MCP server 全局命令（兼容 ~/.local/bin 未加入 PATH 的情况）。"""
    found = shutil.which(MCP_CMD)
    if found:
        return found
    local = os.path.expanduser(f"~/.local/bin/{MCP_CMD}")
    return local if os.path.exists(local) else None


def _local_src_dir() -> str | None:
    """插件 zip 附带的 MCP Server 源码目录（插件同级 mcp_server/）。"""
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_server")
    if os.path.exists(os.path.join(d, "pyproject.toml")):
        return d
    return None


def _local_src_version() -> str | None:
    """读取本地源码的 __version__。"""
    import re
    init = os.path.join(_local_src_dir() or "", "src", "subhuti_blender_mcp", "__init__.py")
    if not os.path.exists(init):
        return None
    try:
        with open(init) as f:
            m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', f.read())
        return m.group(1) if m else None
    except Exception:  # noqa: BLE001
        return None


def _installed_version() -> str | None:
    """查询已安装全局命令的版本（uv tool list）。"""
    import subprocess
    uv = shutil.which("uv") or os.path.expanduser("~/.local/bin/uv")
    if not os.path.exists(uv):
        return None
    try:
        out = subprocess.run([uv, "tool", "list"], capture_output=True,
                             text=True, timeout=10).stdout
        for line in out.splitlines():
            if line.strip().startswith(MCP_CMD):
                # 形如 "subhuti-blender-mcp v0.2.0"
                return line.split("v")[-1].strip()
    except Exception:  # noqa: BLE001
        pass
    return None


def _install_async(target: str, reason: str) -> str:
    """后台线程执行 uv tool install <target>（不阻塞 Blender 启动）。"""
    import subprocess
    uv = shutil.which("uv") or os.path.expanduser("~/.local/bin/uv")

    def _install():
        try:
            proc = subprocess.run(
                [uv, "tool", "install", target],
                capture_output=True, text=True, timeout=300,
            )
            if proc.returncode == 0:
                print(f"[Subhuti-Blender-MCP] ✅ MCP Server 安装成功: {target}")
            else:
                detail = (proc.stderr or proc.stdout or "")[-300:]
                print(f"[Subhuti-Blender-MCP] ❌ MCP Server 安装失败: {detail}")
        except Exception as e:  # noqa: BLE001
            print(f"[Subhuti-Blender-MCP] ❌ MCP Server 安装异常: {e}")

    threading.Thread(target=_install, daemon=True).start()
    return f"MCP Server {reason}，正在后台安装 ({target})..."


def _ensure_mcp_env() -> str:
    """检测 MCP Server 全局命令，缺失或版本落后时后台安装（不阻塞 Blender）。"""
    src_dir = _local_src_dir()
    src_ver = _local_src_version()

    if _find_mcp_cmd():
        # 已装：若附带本地源码且版本不同 → 后台更新（插件更新带动翻译官更新）
        if src_dir and src_ver and src_ver != _installed_version():
            return _install_async(src_dir, f"本地源码版本 {src_ver} 与已装不一致")
        return f"MCP Server 已就绪 ({MCP_CMD})"

    if not AUTO_SETUP:
        return (f"MCP Server 未安装（自动安装已关闭）。"
                f"请手动运行: uv tool install {MCP_PACKAGE}")

    uv = shutil.which("uv") or os.path.expanduser("~/.local/bin/uv")
    if not os.path.exists(uv):
        return (f"MCP Server 未安装且未找到 uv，无法自动安装。"
                f"请先安装 uv (https://docs.astral.sh/uv/) 后运行: uv tool install {MCP_PACKAGE}")

    # 本地源码优先（zip 附带），否则回退包名
    target = src_dir if src_dir else MCP_PACKAGE
    return _install_async(target, "未安装")

# ---------------------------------------------------------------------------
# 主线程调度：请求入队 → GUI 用 timer 轮询 / 无头用主循环轮询 → 执行并回填
# ---------------------------------------------------------------------------
_rpc_queue: "queue.Queue" = queue.Queue()
_msg_counter = 0
_lock = threading.Lock()
# 共享执行环境：跨多次 RPC 调用保留变量
_globals = {"bpy": bpy, "C": bpy.context, "D": bpy.data}
_server = None


def _next_id() -> int:
    global _msg_counter
    with _lock:
        _msg_counter += 1
        return _msg_counter


def _run_func(func) -> dict:
    """在当前线程执行 func，返回统一结果字典。"""
    try:
        data = func()
        return {"ok": True, "data": data}
    except Exception as e:  # noqa: BLE001
        return {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "traceback": traceback.format_exc(),
        }


def _dispatch(func, timeout: float = 120.0) -> dict:
    """把 func 调度到 Blender 主线程执行并等待结果。"""
    if bpy.app.background:
        # 无头模式：本脚本的主循环就是主线程，直接执行
        return _run_func(func)
    # GUI 模式：入队，等 timer 在主线程取走执行
    evt = threading.Event()
    result: dict = {}
    mid = _next_id()
    _rpc_queue.put((mid, func, result, evt))
    if not evt.wait(timeout):
        return {"ok": False, "error": f"timeout: 主线程 {timeout}s 内未响应"}
    return result


def _timer_poll():
    """GUI 模式：由 bpy.app.timers 每帧调用，在主线程消费队列。"""
    try:
        mid, func, result, evt = _rpc_queue.get_nowait()
    except queue.Empty:
        return 0.05
    result.update(_run_func(func))
    evt.set()
    return 0.05


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------
class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # 静默默认日志
        pass

    def _send(self, obj: dict, code: int = 200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path.rstrip("/") == "/health":
            self._send({
                "status": "ok",
                "blender": bpy.app.version_string,
                "background": bpy.app.background,
                "host": HOST,
                "port": PORT,
            })
        else:
            self._send({"error": "not found"}, 404)

    def do_POST(self):  # noqa: N802
        if self.path.rstrip("/") != "/rpc":
            return self._send({"error": "not found"}, 404)
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            code = payload.get("code", "")
            if not code.strip():
                raise ValueError("code 为空")
        except Exception as e:  # noqa: BLE001
            return self._send({"ok": False, "error": f"bad request: {e}"}, 400)

        def run():
            import contextlib
            import io

            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                exec(compile(code, "<blender-mcp>", "exec"), _globals)
            return {"stdout": out.getvalue(), "stderr": err.getvalue()}

        self._send(_dispatch(run))


# ---------------------------------------------------------------------------
# Addon 生命周期
# ---------------------------------------------------------------------------
def register():
    global _server
    print(f"[Subhuti-Blender-MCP] {_ensure_mcp_env()}")
    if _server is not None:
        return
    try:
        _server = ThreadingHTTPServer((HOST, PORT), _Handler)
    except OSError as e:
        # 端口被占用（例如另一个 Blender 实例已在运行）时不能抛异常，
        # 否则会导致 Blender 启动失败
        print(f"[Subhuti-Blender-MCP] ⚠️ 端口 {HOST}:{PORT} 已被占用（{e}），"
              f"可能已有实例在运行，本次跳过启动 HTTP 桥")
        _server = None
        return
    threading.Thread(target=_server.serve_forever, daemon=True).start()
    if not bpy.app.background:
        bpy.app.timers.register(_timer_poll)
    print(f"[Subhuti-Blender-MCP] HTTP bridge listening on http://{HOST}:{PORT}")


def unregister():
    global _server
    if _server is not None:
        _server.shutdown()
        _server = None
    if not bpy.app.background:
        try:
            bpy.app.timers.unregister(_timer_poll)
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    register()
    if bpy.app.background:
        # 无头模式：脚本自身即主线程，循环消费队列
        import time
        print("[Subhuti-Blender-MCP] headless mode, Ctrl+C to quit")
        try:
            while True:
                _timer_poll()
                time.sleep(0.02)
        except KeyboardInterrupt:
            print("[Subhuti-Blender-MCP] shutting down")
