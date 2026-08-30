"""核心应用服务：MCP Server 定义与 Blender 控制工具。

所有工具通过 utils.http_client 转发到 Blender 插件（HTTP 桥），
由插件在 Blender 主线程执行实际的 bpy 操作。
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from .. import config
from ..utils.http_client import request

mcp = MCPServer(
    "blender-mcp",
    instructions=(
        "通过本服务可控制本机正在运行的 Blender。"
        "所有代码在 Blender 主线程执行，可直接使用 bpy / C(bpy.context) / D(bpy.data)。"
    ),
)


@mcp.tool()
def blender_status() -> str:
    """检查与 Blender 的连接状态，返回 Blender 版本等基本信息。"""
    try:
        info = request("GET", "/health", timeout=5)
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
        res = request("POST", "/rpc", {"code": code}, timeout=config.RPC_TIMEOUT)
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
