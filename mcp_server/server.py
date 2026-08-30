"""
Subhuti Blender MCP — MCP Server（stdio 模式）

通过 HTTP 桥转发到正在运行的 Blender 进程。由 MCP 客户端（如 WorkBuddy、
Claude Desktop、mcp inspector）以子进程方式启动。

运行：  python mcp_server/server.py
测试：  python test_client.py
"""

import json
import os
import urllib.request

from mcp.server.mcpserver import MCPServer

HOST = os.environ.get("BLENDER_MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("BLENDER_MCP_PORT", "9876"))
BASE = f"http://{HOST}:{PORT}"
RPC_TIMEOUT = 180  # Blender 长操作（如渲染）需要更久

mcp = MCPServer(
    "blender-mcp",
    instructions=(
        "通过本服务可控制本机正在运行的 Blender。"
        "所有代码在 Blender 主线程执行，可直接使用 bpy / C(bpy.context) / D(bpy.data)。"
    ),
)


def _http(method: str, path: str, payload: dict | None = None, timeout: float = 30.0) -> dict:
    if method == "GET":
        req = urllib.request.Request(f"{BASE}{path}", method="GET")
    else:
        req = urllib.request.Request(
            f"{BASE}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


@mcp.tool()
def blender_status() -> str:
    """检查与 Blender 的连接状态，返回 Blender 版本等基本信息。"""
    try:
        info = _http("GET", "/health", timeout=5)
        return (
            f"✅ 已连接 Blender {info['blender']} "
            f"(无头模式={info['background']}, 端口={info['port']})"
        )
    except Exception as e:  # noqa: BLE001
        return f"❌ 无法连接 Blender: {e}"


@mcp.tool()
def blender_run_code(code: str) -> str:
    """在 Blender 主线程执行一段 Python 代码（可直接使用 bpy、C、D），返回标准输出。

    示例：创建立方体并移动
      import bpy
      bpy.ops.mesh.primitive_cube_add(size=2, location=(1, 0, 0))
      print('created:', bpy.context.object.name)
    """
    try:
        res = _http("POST", "/rpc", {"code": code}, timeout=RPC_TIMEOUT)
    except Exception as e:  # noqa: BLE001
        return f"请求失败: {e}"
    if not res.get("ok"):
        return f"执行出错: {res.get('error', 'unknown')}\n{res.get('traceback', '')}"
    data = res.get("data", {})
    out, err = data.get("stdout", ""), data.get("stderr", "")
    if out and err:
        return f"[stdout]\n{out}\n[stderr]\n{err}"
    return out or err or "(执行成功，无输出)"


@mcp.tool()
def blender_scene_summary() -> str:
    """返回 Blender 当前场景的对象清单（名称 / 类型 / 可见性）。"""
    code = (
        "import bpy\n"
        "print('场景:', bpy.context.scene.name)\n"
        "print('对象数:', len(bpy.data.objects))\n"
        "for o in bpy.data.objects:\n"
        "    print(f'- {o.name} [{o.type}] visible={o.visible_get()}')\n"
    )
    return blender_run_code(code)


@mcp.tool()
def blender_object_info(object_name: str) -> str:
    """查询指定对象的属性：位置、旋转、缩放、网格顶点/面数、材质。"""
    code = (
        "import bpy\n"
        "o = bpy.data.objects.get(%r)\n"
        "if o is None:\n"
        "    print('对象不存在:', %r)\n"
        "else:\n"
        "    print('name:', o.name)\n"
        "    print('type:', o.type)\n"
        "    print('location:', tuple(round(v,4) for v in o.location))\n"
        "    print('rotation:', tuple(round(v,4) for v in o.rotation_euler))\n"
        "    print('scale:', tuple(round(v,4) for v in o.scale))\n"
        "    if o.type == 'MESH':\n"
        "        m = o.data\n"
        "        print('verts:', len(m.vertices), 'faces:', len(m.polygons))\n"
        "    if o.data and hasattr(o.data, 'materials'):\n"
        "        print('materials:', [m.name if m else None for m in o.data.materials])\n"
    ) % (object_name, object_name)
    return blender_run_code(code)


if __name__ == "__main__":
    # 传输模式切换（供开发调试）：
    #   stdio  -> 生产默认，由 MCP 客户端以子进程方式启动
    #   http   -> 开发调试，PyCharm 里直接 F5 运行可打断点，
    #             配合 debug_client.py / mcp inspector 触发调用
    transport = os.environ.get("BLENDER_MCP_TRANSPORT", "stdio")
    if transport == "http":
        http_port = int(os.environ.get("BLENDER_MCP_HTTP_PORT", "8100"))
        print(f"[blender-mcp] HTTP 调试模式: http://127.0.0.1:{http_port}/mcp")
        mcp.run(
            transport="streamable-http",
            host="127.0.0.1",
            port=http_port,
        )
    else:
        mcp.run()  # 默认 stdio