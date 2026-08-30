"""
端到端测试客户端：用官方 MCP SDK 启动 server.py（stdio），
依次调用所有工具验证与 Blender 的连通性。

前置：Blender 已启动并加载插件（见 README）。
运行：.venv/bin/python test_client.py
"""

import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SERVER = os.path.join(ROOT, "mcp_server", "server.py")


async def call(session: ClientSession, name: str, args: dict) -> str:
    res = await session.call_tool(name, args)
    if res.content:
        return res.content[0].text
    return str(res)


async def main() -> None:
    params = StdioServerParameters(command=sys.executable, args=[SERVER])

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("可用工具:", [t.name for t in tools.tools])

            print("\n=== 1. blender_status ===")
            print(await call(session, "blender_status", {}))

            print("\n=== 2. blender_scene_summary ===")
            print(await call(session, "blender_scene_summary", {}))

            print("\n=== 3. blender_run_code（新建一个立方体并保存）===")
            code = (
                "import bpy\n"
                "bpy.ops.mesh.primitive_cube_add(size=1.5, location=(2, 0, 0))\n"
                "created = bpy.context.view_layer.objects.active\n"
                "print('created:', created.name if created else 'unknown')\n"
                "bpy.ops.wm.save_mainfile()\n"
                "print('saved OK')\n"
            )
            print(await call(session, "blender_run_code", {"code": code}))

            print("\n=== 4. blender_object_info（查刚才的立方体）===")
            print(await call(session, "blender_object_info", {"object_name": "Cube"}))

            print("\n全部测试完成 ✅")


if __name__ == "__main__":
    asyncio.run(main())
